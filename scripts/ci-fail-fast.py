#!/usr/bin/env python3
"""Stop a controlled Android CI command on its first deterministic fatal signal."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from typing import Any, BinaryIO

from ci_failure_envelope import sanitize_text


MAX_LINE_BYTES = 16 * 1024
MAX_SIGNAL_CHARS = 1_000
FAIL_FAST_EXIT = 86
ANDROID_FATAL = re.compile(
    r"(?i)(?:^FAILED:\s+|^ninja:\s+(?:error|build stopped):|"
    r"^error:\s+(?!process completed)|:\d+(?::\d+)?:\s+(?:fatal\s+)?error:|"
    r"\bsoong(?:_build)?\b.*\b(?:error|failed)\b|"
    r"\b(?:lpmake|avbtool)\b.*\b(?:error|failed)\b)"
)


def detect_failure(line: str, *, truncated: bool = False) -> dict[str, Any] | None:
    cleaned, redactions = sanitize_text(line.strip())
    compact = " ".join(cleaned.split())[:MAX_SIGNAL_CHARS]
    if not compact or not ANDROID_FATAL.search(compact):
        return None
    return {
        "schema_version": 1,
        "kind": "android",
        "reason": "android_actionable_failure",
        "signal": compact,
        "input_truncated": truncated or len(cleaned) > MAX_SIGNAL_CHARS,
        "redaction_count": redactions,
        "action": "terminate_controlled_ci_process",
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def run_command(
    command: list[str], *, evidence_output: Path,
    output: BinaryIO | None = None, terminate_timeout: float = 10.0,
) -> int:
    if not command:
        raise ValueError("command is required")
    output = sys.stdout.buffer if output is None else output
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    assert process.stdout is not None
    try:
        while True:
            chunk = process.stdout.readline(MAX_LINE_BYTES + 1)
            if not chunk:
                break
            output.write(chunk)
            output.flush()
            failure = detect_failure(
                chunk.decode("utf-8", errors="replace"),
                truncated=len(chunk) > MAX_LINE_BYTES and not chunk.endswith(b"\n"),
            )
            if failure is not None:
                _write_json_atomic(evidence_output, failure)
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=terminate_timeout)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                return FAIL_FAST_EXIT
        return process.wait()
    finally:
        process.stdout.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        return run_command(command, evidence_output=args.evidence_output)
    except (OSError, ValueError) as exc:
        print(json.dumps({"result": "rejected", "error": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
