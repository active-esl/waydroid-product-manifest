#!/usr/bin/env python3
"""Emit one signed FRDM build-success event for downstream test continuation."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
from typing import Any
import urllib.error
import urllib.request


ENDPOINT = "https://ci-advisory.dynamicdevices.co.uk/v1/ci-completion"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_RESPONSE_BYTES = 32 * 1024


def build_event(run_id: int, run_attempt: int, commit_sha: str) -> dict[str, Any]:
    if run_id <= 0 or not 1 <= run_attempt <= 999999 or not SHA_RE.fullmatch(commit_sha):
        raise ValueError("invalid build identity")
    event_id = f"github:active-esl/waydroid-product-manifest:{run_id}:{run_attempt}"
    return {
        "schema_version": 1,
        "event_id": event_id,
        "lane": "android-frdm",
        "status": "PASSED",
        "build": {
            "run_id": run_id,
            "run_attempt": run_attempt,
            "commit_sha": commit_sha,
            "web_url": f"https://github.com/active-esl/waydroid-product-manifest/actions/runs/{run_id}",
            "evidence_location": f"/yocto/android-16-artifacts/{run_id}-{run_attempt}",
        },
    }


def emit(event: dict[str, Any], secret: bytes, timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = "sha256:" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "dd-waydroid-frdm-ci/1",
            "X-DD-CI-Signature": signature,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("completion response exceeded the boundary")
    received = json.loads(data)
    if not isinstance(received, dict) or received.get("event_id") != event["event_id"]:
        raise ValueError("completion response identity mismatch")
    if received.get("status") != "PASSED" or received.get("action") != "resume_waiting_test_lane":
        raise ValueError("completion response omitted the continuation contract")
    return received


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    args = parser.parse_args()
    try:
        secret = os.environ["JEV_CI_ADVISORY_HMAC_SECRET"].encode("utf-8")
        if not secret:
            raise ValueError("empty completion HMAC secret")
        event = build_event(args.run_id, args.run_attempt, args.commit_sha)
        emit(event, secret, args.timeout_seconds)
    except (
        KeyError, OSError, ValueError, json.JSONDecodeError,
        urllib.error.URLError, TimeoutError,
    ) as exc:
        print(f"CI completion event unavailable ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("FRDM build completion event accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
