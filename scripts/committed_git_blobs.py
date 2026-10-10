"""Private bounded reads of immutable, unsmudged Git blobs.

Only trusted repository callers select the root, closed paths and limits. This
module has no CLI, engine imports, MCP tool or admission policy. Callers retain
fresh HEAD, worktree, executing-file and provenance checks at every boundary.
"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import math
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time


SOURCE_PATH = "scripts/committed_git_blobs.py"
GIT_BATCH_OBJECTS = 512
GIT_BATCH_PATH_BYTES = 1024
GIT_BATCH_BYTES = 32 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


def _require(value, message: str) -> None:
    if not value:
        raise ValueError(message)


def _deadline(seconds: float) -> float:
    _require(
        type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 120,
        "committed Git process timeout is invalid",
    )
    return time.monotonic() + seconds


def _path(root: Path, relative: str, validator: Callable[[Path, str], Path]) -> None:
    _require(
        isinstance(relative, str)
        and relative
        and not Path(relative).is_absolute()
        and not any(c in relative for c in "\\:\x00\r\n\t")
        and all(part not in {"", ".", ".."} for part in relative.split("/")),
        "committed Git path is not canonical",
    )
    validator(root, relative)


def _git_bounded(
    root: Path,
    args: tuple[str, ...],
    output_limit: int,
    *,
    request: bytes = b"",
    deadline: float,
) -> bytes:
    """Read at most cap+1 bytes, with bounded input and no captured stderr.

    A reader thread keeps the pipe draining on Windows too. The main thread's
    deadline covers process and pipe completion; overflow kills the process.
    Only this private raw-object reader uses this boundary, never a shell.
    """
    _require(
        0 < output_limit <= GIT_BATCH_BYTES + GIT_BATCH_OBJECTS * 128
        and len(request) <= GIT_BATCH_OBJECTS * (GIT_BATCH_PATH_BYTES + 64),
        "committed Git batch exceeds its acquisition bound",
    )
    _require(
        time.monotonic() < deadline,
        "committed Git batch exceeded its existing process deadline",
    )
    output = bytearray()
    errors = []
    with tempfile.TemporaryFile() as input_file:
        input_file.write(request)
        input_file.seek(0)
        process = subprocess.Popen(
            ["git", "-C", str(root), *args],
            stdin=input_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

        def read_output():
            try:
                while len(output) <= output_limit:
                    block = process.stdout.read(
                        min(65536, output_limit + 1 - len(output))
                    )
                    if not block:
                        break
                    output.extend(block)
                if len(output) > output_limit:
                    process.kill()
            except OSError as exc:
                errors.append(exc)
            finally:
                process.stdout.close()

        reader = None
        try:
            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            process.wait(timeout=max(0, deadline - time.monotonic()))
            reader.join(timeout=max(0, deadline - time.monotonic()))
            _require(
                not reader.is_alive()
                and not errors
                and process.returncode == 0
                and len(output) <= output_limit
                and time.monotonic() <= deadline,
                "committed Git batch output is incomplete or exceeds its bound",
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                "committed Git batch exceeded its existing process deadline"
            ) from exc
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            if reader is not None and reader.ident is not None:
                reader.join(timeout=1)
            else:
                process.stdout.close()
    return bytes(output)


def _git_blob_inventory(
    root: Path,
    exact_sha: str,
    paths: tuple[str, ...],
    *,
    path_validator: Callable[[Path, str], Path],
    timeout_seconds: float,
) -> dict[str, str]:
    _require(
        isinstance(exact_sha, str)
        and SHA40.fullmatch(exact_sha)
        and 0 < len(paths) <= GIT_BATCH_OBJECTS
        and len(set(paths)) == len(paths),
        "committed Git path inventory is invalid",
    )
    for path in paths:
        _path(root, path, path_validator)
        _require(
            len(path.encode()) <= GIT_BATCH_PATH_BYTES
            and not any(c in path for c in "\r\n\t"),
            "committed Git path is not canonical",
        )
    raw = _git_bounded(
        root,
        ("--literal-pathspecs", "ls-tree", "-rz", exact_sha, "--", *paths),
        GIT_BATCH_OBJECTS * (GIT_BATCH_PATH_BYTES + 64),
        deadline=_deadline(timeout_seconds),
    )
    _require(raw.endswith(b"\0"), "committed Git inventory framing is invalid")
    entries = raw[:-1].split(b"\0")
    _require(
        0 < len(entries) <= GIT_BATCH_OBJECTS,
        "committed Git inventory exceeds its bound",
    )
    inventory = {}
    for entry in entries:
        match = re.fullmatch(rb"100(?:644|755) blob ([0-9a-f]{40})\t([^\0]+)", entry)
        _require(match is not None, "committed Git inventory requires regular blobs")
        path = match[2].decode("utf-8")
        _path(root, path, path_validator)
        _require(
            len(match[2]) <= GIT_BATCH_PATH_BYTES
            and not any(c in path for c in "\r\n\t")
            and path not in inventory
            and any(
                path == selected or path.startswith(selected + "/")
                for selected in paths
            ),
            "committed Git inventory path is invalid or duplicated",
        )
        inventory[path] = match[1].decode()
    return inventory


def _git_blobs(
    root: Path,
    inventory: dict[str, str],
    *,
    blob_limit: int,
    total_limit: int,
    timeout_seconds: float,
    path_validator: Callable[[Path, str], Path],
) -> dict[str, bytes]:
    """Authenticate raw blobs against exact-commit tree OIDs, without smudging.

    Metadata is bounded before any payload acquisition. Only proven immutable
    blob OIDs reach the second process; its stdout cap is the exact sum of their
    declared sizes and framing. Both processes share the caller deadline.
    Callers independently reread their worktree; this helper caches nothing.
    """
    _require(
        0 < len(inventory) <= GIT_BATCH_OBJECTS
        and 0 < blob_limit <= GIT_BATCH_BYTES
        and 0 < total_limit <= GIT_BATCH_BYTES,
        "committed Git blob inventory exceeds its bound",
    )
    for path, oid in inventory.items():
        _path(root, path, path_validator)
        _require(
            len(path.encode()) <= GIT_BATCH_PATH_BYTES
            and not any(c in path for c in "\r\n\t")
            and isinstance(oid, str)
            and SHA40.fullmatch(oid) is not None,
            "committed Git path or object ID is invalid",
        )
    deadline = _deadline(timeout_seconds)
    request = b"".join(
        f"{oid} {index}\n".encode() for index, oid in enumerate(inventory.values())
    )
    metadata = _git_bounded(
        root,
        ("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)"),
        len(inventory) * 128,
        request=request,
        deadline=deadline,
    )
    _require(metadata.endswith(b"\n"), "committed Git metadata framing is invalid")
    lines = metadata[:-1].split(b"\n")
    _require(len(lines) == len(inventory), "committed Git metadata inventory differs")
    sizes = []
    for index, ((path, oid), line) in enumerate(zip(inventory.items(), lines)):
        match = re.fullmatch(
            rb"([0-9a-f]{40}) blob (0|[1-9][0-9]*) (0|[1-9][0-9]*)", line
        )
        _require(
            match is not None
            and match[1].decode() == oid
            and match[3] == str(index).encode(),
            "committed Git metadata identity or order differs",
        )
        size = int(match[2])
        _require(size <= blob_limit, "committed Git blob exceeds its file bound")
        sizes.append(size)
    _require(sum(sizes) <= total_limit, "committed Git blobs exceed their total bound")
    headers = [
        f"{oid} blob {size}\n".encode() for oid, size in zip(inventory.values(), sizes)
    ]
    raw = _git_bounded(
        root,
        ("cat-file", "--batch"),
        sum(len(header) + size + 1 for header, size in zip(headers, sizes)),
        request=b"".join((oid + "\n").encode() for oid in inventory.values()),
        deadline=deadline,
    )
    blobs, offset = {}, 0
    for (path, oid), size, header in zip(inventory.items(), sizes, headers):
        _require(
            raw[offset : offset + len(header)] == header,
            "committed Git blob header or order differs",
        )
        offset += len(header)
        body = raw[offset : offset + size]
        offset += size
        _require(
            len(body) == size and raw[offset : offset + 1] == b"\n",
            "committed Git blob payload is truncated or has invalid framing",
        )
        # Git's admitted repository object format is SHA-1; policy/file proofs
        # continue to use SHA-256. A response header cannot authenticate itself.
        _require(
            hashlib.sha1(f"blob {size}\0".encode() + body).hexdigest() == oid,
            "committed Git blob bytes differ from their tree object ID",
        )
        blobs[path] = body
        offset += 1
    _require(
        offset == len(raw) and time.monotonic() <= deadline,
        "committed Git blobs contain trailing output or exceeded their deadline",
    )
    return blobs


def _read_exact_blobs(
    root: Path,
    exact_sha: str,
    paths: tuple[str, ...],
    *,
    blob_limit: int,
    total_limit: int,
    timeout_seconds: float,
    path_validator: Callable[[Path, str], Path],
) -> dict[str, bytes]:
    """Read one closed tuple of exact file paths, never directory expansion."""
    inventory = _git_blob_inventory(
        root,
        exact_sha,
        paths,
        path_validator=path_validator,
        timeout_seconds=timeout_seconds,
    )
    _require(set(inventory) == set(paths), "committed Git exact path inventory differs")
    return _git_blobs(
        root,
        inventory,
        blob_limit=blob_limit,
        total_limit=total_limit,
        timeout_seconds=timeout_seconds,
        path_validator=path_validator,
    )
