"""Authenticate CPU mask-derived points for a point-only native diagnostic."""

import argparse
import hashlib
import json
import math
from pathlib import Path


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_request_data(receipt):
    """Pure stdlib structural validation; source authentication is prepare's job."""
    if (
        receipt.get("status") != "CPU_XY_PROBES_ONLY"
        or receipt.get("placement") is not False
        or receipt.get("qualified_assets") != []
    ):
        raise ValueError("Explicit unqualified CPU diagnostic required")
    unsigned = {key: value for key, value in receipt.items() if key != "fingerprint"}
    if digest(canonical(unsigned)) != receipt.get("fingerprint"):
        raise ValueError("Candidate fingerprint drift")
    seed = receipt["recipe"]["seed"]
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValueError("Invalid recipe seed")
    selected = []
    for row in receipt["candidates"]:
        if type(row["selected"]) is not bool:
            raise ValueError("Invalid selection state")
        if not row["selected"]:
            continue
        identity, cell, xy = row["candidate_id"], row["source_cell"], row["world_xy_cm"]
        if (
            not isinstance(identity, str)
            or len(identity) != 64
            or any(c not in "0123456789abcdef" for c in identity)
        ):
            raise ValueError("Invalid candidate identity")
        if (
            not isinstance(cell, list)
            or len(cell) != 2
            or any(type(v) is not int or v < 0 for v in cell)
        ):
            raise ValueError("Invalid source cell")
        if (
            not isinstance(xy, list)
            or len(xy) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in xy)
            or xy != [cell[1] * 50, cell[0] * 50]
        ):
            raise ValueError("Invalid source XY mapping")
        if type(row["band"]) is not int or row["band"] not in (0, 1, 2):
            raise ValueError("Invalid selector band")
        if (
            type(row["point_seed"]) is not int
            or not 0 < row["point_seed"] <= 2147483647
        ):
            raise ValueError("Invalid or zero native point seed")
        selected.append(
            {
                key: row[key]
                for key in (
                    "candidate_id",
                    "source_cell",
                    "band",
                    "point_seed",
                    "world_xy_cm",
                )
            }
        )
    if not 1 <= len(selected) <= 16:
        raise ValueError("One to sixteen selected points required")
    for key in ("candidate_id", "world_xy_cm", "point_seed"):
        values = [
            tuple(row[key]) if key == "world_xy_cm" else row[key] for row in selected
        ]
        if len(set(values)) != len(values):
            raise ValueError("Duplicate selected " + key)
    return sorted(selected, key=lambda row: row["candidate_id"])


def prepare(root, config, candidates_path, expected_sha, scratch_parent):
    # Raster dependencies intentionally loaded only for authenticated preparation.
    import sa_calobra_world_graph_candidates as cpu

    raw = candidates_path.read_bytes()
    if digest(raw) != expected_sha:
        raise ValueError("Candidate file identity drift")
    receipt = json.loads(raw)
    points = validate_request_data(receipt)
    producer = digest(Path(cpu.__file__).read_bytes().replace(b"\r\n", b"\n"))
    if receipt.get("producer_sha256_lf") != producer:
        raise ValueError("Candidate producer identity drift")
    source, arrays = cpu.authenticated_inputs(root, config, scratch_parent)
    if receipt["recipe"]["seed"] != source["configuration"]["seed"]:
        raise ValueError("Authenticated configuration seed drift")
    recipe_data = dict(receipt["recipe"])
    recipe_data["band_priority"] = tuple(recipe_data["band_priority"])
    rebuilt = cpu.candidates(*arrays, cpu.LatticeRecipe(**recipe_data))
    rebuilt["authenticated_inputs"] = source
    rebuilt["producer_sha256_lf"] = producer
    if canonical(rebuilt) != canonical(
        {k: v for k, v in receipt.items() if k != "fingerprint"}
    ):
        raise ValueError("Authenticated candidate reconstruction drift")
    if digest(candidates_path.read_bytes()) != expected_sha:
        raise ValueError("Candidate file changed during preparation")
    return {
        "schema_version": 1,
        "status": "MASK_DERIVED_XY_GRAPH_REQUEST_ONLY",
        "placement": False,
        "qualified_assets": [],
        "terrain_contact": "REQUIRED_UNSET",
        "source_bindings": {
            "candidate_sha256": expected_sha,
            "candidate_fingerprint": receipt["fingerprint"],
            "producer_sha256_lf": producer,
            "authenticated_inputs": source,
        },
        "recipe_seed": receipt["recipe"]["seed"],
        "z_carrier_cm": 0,
        "z_semantics": "DIAGNOSTIC_CARRIER_ONLY_NOT_SOURCE_OR_GROUND_HEIGHT",
        "native_consumption": "CPU_AUTHENTICATED_POINTS_NOT_NATIVE_RASTER_SAMPLING",
        "points": points,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "config", "candidates", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-candidates-sha", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve existing request")
    result = prepare(
        args.root,
        args.config,
        args.candidates,
        args.expected_candidates_sha,
        args.output.parent,
    )
    with args.output.open("xb") as stream:
        stream.write(canonical(result))


if __name__ == "__main__":
    main()
