"""Verify the clean DTM baseline evidence before transporting it in H's artifact."""

import base64
import hashlib


def validate_receipt(report: dict, exact_sha: str) -> None:
    if report.get("status") != "PASS" or report.get("exact_sha") != exact_sha:
        raise ValueError("Clean baseline status or SHA mismatch")
    if report.get("import_process_id") == report.get("reload_process_id"):
        raise ValueError("Clean baseline reload must use a fresh process")
    for phase in ("after_import", "after_save_reload"):
        result = report[phase]
        if (
            result["status"] != "PASS"
            or result["sample_count"] != 4033 * 4033
            or result["mismatch_count"] != 0
        ):
            raise ValueError("Clean baseline native height parity failed")
    data = base64.b64decode(report["screenshot_base64"], validate=True)
    if len(data) > 20 * 1024 * 1024 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid or oversized clean baseline PNG")
    if hashlib.sha256(data).hexdigest() != report["screenshot_sha256"]:
        raise ValueError("Clean baseline PNG hash mismatch")
