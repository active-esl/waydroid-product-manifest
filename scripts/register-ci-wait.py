#!/usr/bin/env python3
"""Durably register this GitHub run with one exact Codex continuation task."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.request


ENDPOINT = "https://ci-advisory.dynamicdevices.co.uk/v1/ci-wait-registration"
THREAD_ID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
MAX_RESPONSE_BYTES = 16 * 1024


def build_registration(
    run_id: int, run_attempt: int, thread_id: str, *, now: int | None = None,
) -> dict[str, Any]:
    now = int(time.time()) if now is None else now
    if run_id <= 0 or not 1 <= run_attempt <= 999999:
        raise ValueError("invalid GitHub run identity")
    if not THREAD_ID_RE.fullmatch(thread_id):
        raise ValueError("invalid Codex task identity")
    return {
        "schema_version": 1,
        "provider": "github",
        "lane": "android-frdm",
        "correlation_id": (
            f"github:active-esl/waydroid-product-manifest:{run_id}:{run_attempt}"
        ),
        "thread_id": thread_id,
        "expires_at": now + 7 * 86400 - 60,
    }


def register(payload: dict[str, Any], secret: bytes, timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
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
        raise ValueError("registration response exceeded the boundary")
    received = json.loads(data)
    if not isinstance(received, dict) or received.get("result") != "registration_accepted":
        raise ValueError("registration response omitted acceptance")
    if received.get("correlation_id") != payload["correlation_id"] or received.get("durable") is not True:
        raise ValueError("registration response identity mismatch")
    return received


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    args = parser.parse_args()
    try:
        secret = os.environ["JEV_CI_ADVISORY_HMAC_SECRET"].encode("utf-8")
        if not secret:
            raise ValueError("empty registration HMAC secret")
        payload = build_registration(args.run_id, args.run_attempt, args.thread_id)
        register(payload, secret, args.timeout_seconds)
    except (
        KeyError, OSError, ValueError, json.JSONDecodeError,
        urllib.error.URLError, TimeoutError,
    ) as exc:
        print(f"CI wait registration unavailable ({type(exc).__name__})", file=sys.stderr)
        return 1
    print("FRDM build wait registered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
