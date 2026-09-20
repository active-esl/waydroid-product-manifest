#!/usr/bin/env python3
"""Send one signed, bounded FRDM failure event to the Jev advisory gateway."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from ci_failure_envelope import EnvelopeError, extract_envelope


ENDPOINT = "https://ci-advisory.dynamicdevices.co.uk/v1/jev-ci-triage"
MAX_RESPONSE_BYTES = 128 * 1024


def build_request_body(log: str, context: dict[str, Any], request_id: str) -> bytes:
    extracted = extract_envelope(log, context, origin="github_failure_only_advisory")
    payload = {
        "schema_version": 1,
        "request_id": request_id,
        "lane": "android-frdm",
        "envelope": extracted["mcp_envelope"],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate_response(value: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(value, dict) or set(value) != {"advisory", "markdown"}:
        raise ValueError("gateway response has unexpected fields")
    advisory = value["advisory"]
    markdown = value["markdown"]
    if not isinstance(advisory, dict) or not isinstance(markdown, str):
        raise ValueError("gateway response has invalid artifact types")
    for field in ("changes_execution", "can_authorize", "can_mark_ci_green", "can_retry_ci"):
        if advisory.get(field) is not False:
            raise ValueError("gateway response violated the read-only contract")
    if advisory.get("mode") != "failure_only_non_required_advisory":
        raise ValueError("gateway response has an unexpected mode")
    return advisory, markdown


def request_advisory(body: bytes, secret: bytes, timeout_seconds: int) -> tuple[dict[str, Any], str]:
    signature = "sha256:" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "dd-waydroid-frdm-ci/1",
            "X-DD-CI-Signature": signature,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("gateway response exceeded the artifact boundary")
    return validate_response(json.loads(data))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=75)
    args = parser.parse_args()
    try:
        log = args.log.read_text(encoding="utf-8", errors="replace") if args.log.is_file() else "CI log unavailable"
        context = json.loads(args.context.read_text(encoding="utf-8"))
        secret = os.environ["JEV_CI_ADVISORY_HMAC_SECRET"].encode("utf-8")
        if not secret:
            raise ValueError("empty advisory HMAC secret")
        body = build_request_body(log, context, args.request_id)
        advisory, markdown = request_advisory(body, secret, args.timeout_seconds)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "jev-ci-advisory.json").write_text(
            json.dumps(advisory, indent=2) + "\n", encoding="utf-8"
        )
        (args.output_dir / "jev-ci-advisory.md").write_text(markdown, encoding="utf-8")
    except (
        EnvelopeError, KeyError, OSError, ValueError, json.JSONDecodeError,
        urllib.error.URLError, TimeoutError,
    ) as exc:
        print(f"Jev advisory unavailable ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("Jev failure advisory artifact created")
    return 0


if __name__ == "__main__":
    sys.exit(main())
