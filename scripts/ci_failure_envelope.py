#!/usr/bin/env python3
"""Extract a bounded, secret-safe CI failure envelope for Jev shadow triage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


MAX_LOG_CHARS = 200_000
MAX_ERROR_CHARS = 1_000
MAX_TEXT_CHARS = 3_000
MAX_CHANGED_PATHS = 12

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s]+"),
    re.compile(
        r"(?i)\b((?:api[_-]?key|token|password|passwd|secret)\s*(?:=|:\s*))"
        r"(?!(?:write|read|none)\b)[^\s,;]+"
    ),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.DOTALL),
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
WORKSPACE_RE = re.compile(r"/(?:home/runner/work/[^/\s]+/[^/\s]+|github/workspace|workspace)(?=/|\b)")
YOCTO_ROOT_RE = re.compile(r"/(?:yocto|srv/yocto)(?:/[A-Za-z0-9_.-]+)*(?=/(?:tmp|build|downloads|sstate-cache)\b)")
SHA256_RE = re.compile(r"(?i)\b(?:sha256[:= ]+)?([0-9a-f]{64})\b")

GENERIC_ERROR_RE = re.compile(
    r"(?i)^(?:error:\s*)?(?:process completed with exit code \d+\.?|"
    r"command failed with exit code \d+\.?|ninja: build stopped: subcommand failed\.?|"
    r"make(?:\[\d+\])?: \*\*\* .*error \d+|error: task .* failed(?: with exit code .*)?)$"
)
SPECIFIC_ERROR_PATTERNS = (
    re.compile(r"(?i)undefined reference|fatal error: .*: no such file|\berror: .*undeclared|"
               r"no member named|multiple definition"),
    re.compile(r"(?i)devicetree error|\.dts:\d+.*(?:syntax error|parse error)|"
               r"undefined node label|kconfig (?:error|warning)|(?:undefined|unknown) symbol|missing dependency"),
    re.compile(r"(?i)nothing provides|hunk #\d+ failed|does not apply|revision .* not found|"
               r"unable to find revision|manifest .* (?:invalid|missing)|no platform target"),
    re.compile(r"(?i)no space left on device|out of memory|oom-kill|killed process|"
               r"no matching online runner|requested labels.*no matching"),
    re.compile(r"(?i)assert(?:ion)? failed|test(?: suite)? .* failed|timed out waiting|"
               r"boot banner.*(?:missing|timeout)|flash verification failed"),
    re.compile(r"(?i)artifact .* (?:does not exist|missing)|hash mismatch|sha256 .* differs|"
               r"sbom .* missing|signature verification failed"),
    re.compile(r"(?i)invalid workflow|yaml syntax|action uses node\.js|deprecated on this runner|"
               r"workflow .* permission"),
    re.compile(r"(?i)(?:ERROR: )?.*do_(?:fetch|unpack|patch|configure|compile|install|package|rootfs|image).*failed|"
               r"bitbake.*(?:parse|expansion).*error|nothing rprovides|no eligible provider|"
               r"preferred_provider.*(?:unavailable|not found)|layer .* is not compatible"),
    re.compile(r"(?i)(?:drm|lcdif|mipi[-_ ]?dsi|panel|backlight).*(?:error|failed|timeout)|"
               r"weston.*(?:error|failed|cannot)|libinput.*(?:touch|calibration).*(?:error|failed)|"
               r"touchscreen.*(?:axis|range|transform).*(?:invalid|mismatch|failed)"),
    re.compile(r"(?i)soong.*(?:error|failed)|FAILED: .*out/|ninja: error:|"
               r"meson\.build:\d+:\d+: ERROR:|mesa.*(?:configure|compile).*(?:error|failed)|"
               r"repo sync.*(?:error|failed)|lpmake.*(?:error|failed)|avbtool.*(?:error|failed)|"
               r"(?:super|system|vendor) image.*(?:assembly|generation).*(?:error|failed)"),
    re.compile(r"(?i)\b(?:error|fatal|failed|failure):\s+.+"),
)


class EnvelopeError(ValueError):
    """Invalid or unsafe envelope input."""


def sanitize_text(value: str) -> tuple[str, int]:
    """Remove common secret material and local identifiers from a string."""
    text = ANSI_RE.sub("", value.replace("\x00", ""))
    redactions = 0
    for pattern in SECRET_PATTERNS:
        if pattern.groups:
            text, count = pattern.subn(r"\1[REDACTED]", text)
        else:
            text, count = pattern.subn("[REDACTED]", text)
        redactions += count
    text, count = EMAIL_RE.subn("[REDACTED_EMAIL]", text)
    redactions += count
    text = WORKSPACE_RE.sub("<workspace>", text)
    text = YOCTO_ROOT_RE.sub("<yocto-root>", text)
    return text, redactions


def _clean_scalar(value: Any, name: str, limit: int = 200) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise EnvelopeError(f"{name} must be a string")
    cleaned, _ = sanitize_text(value.strip())
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit] or None


def _clean_paths(values: Any) -> tuple[list[str], bool]:
    if values is None:
        return [], False
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise EnvelopeError("changed_paths must be a list of strings")
    cleaned: list[str] = []
    for item in values:
        path, _ = sanitize_text(item.strip())
        path = (path[2:] if path.startswith("./") else path)[:300]
        if path and path not in cleaned:
            cleaned.append(path)
    return cleaned[:MAX_CHANGED_PATHS], len(cleaned) > MAX_CHANGED_PATHS


def first_specific_error(log: str) -> str | None:
    """Return the first causal-looking line, ignoring generic terminal summaries."""
    lines = [" ".join(line.strip().split()) for line in log.splitlines()]
    lines = [line for line in lines if line and not line.startswith("##[")]
    for line in lines:
        if GENERIC_ERROR_RE.fullmatch(line):
            continue
        if any(pattern.search(line) for pattern in SPECIFIC_ERROR_PATTERNS[:-1]):
            return line[:MAX_ERROR_CHARS]
    for line in lines:
        if not GENERIC_ERROR_RE.fullmatch(line) and SPECIFIC_ERROR_PATTERNS[-1].search(line):
            return line[:MAX_ERROR_CHARS]
    return None


def _artifact_identity(context: dict[str, Any], log: str) -> dict[str, str] | None:
    name = _clean_scalar(context.get("artifact_name"), "artifact_name", 200)
    sha = _clean_scalar(context.get("artifact_sha256"), "artifact_sha256", 64)
    if sha and not re.fullmatch(r"(?i)[0-9a-f]{64}", sha):
        raise EnvelopeError("artifact_sha256 must be a 64-character hexadecimal digest")
    if not sha:
        match = SHA256_RE.search(log)
        sha = match.group(1).lower() if match else None
    if not name and not sha:
        return None
    result = {}
    if name:
        result["name"] = name
    if sha:
        result["sha256"] = sha.lower()
    return result


def render_jev_text(envelope: dict[str, Any]) -> str:
    """Render only bounded envelope fields, never the original log."""
    lines = [
        f"Failed job: {envelope.get('failed_job') or 'unknown'}",
        f"Failed step: {envelope.get('failed_step') or 'unknown'}",
        f"First specific error: {envelope.get('first_specific_error') or 'not found; only a generic failure summary was available'}",
    ]
    target = envelope.get("target") or {}
    if target:
        lines.append("Target: " + ", ".join(f"{key}={value}" for key, value in sorted(target.items())))
    if envelope.get("changed_paths"):
        lines.append("Changed paths: " + ", ".join(envelope["changed_paths"]))
    artifact = envelope.get("artifact_identity") or {}
    if artifact:
        lines.append("Artifact: " + ", ".join(f"{key}={value}" for key, value in sorted(artifact.items())))
    if envelope.get("input_truncated"):
        lines.append("Input note: source log or changed-path list was deterministically truncated.")
    return "\n".join(lines)[:MAX_TEXT_CHARS]


def to_mcp_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return the only fields permitted to cross the Preloop MCP boundary."""
    return {
        "failed_job": envelope.get("failed_job"),
        "failed_step": envelope.get("failed_step"),
        "first_specific_error": envelope.get("first_specific_error"),
        "target": envelope.get("target") or {},
        "changed_paths": envelope.get("changed_paths") or [],
        "artifact_identity": envelope.get("artifact_identity"),
        "input_truncated": bool(envelope.get("input_truncated")),
    }


def extract_envelope(log: str, context: dict[str, Any], origin: str = "sanitized_ci_excerpt") -> dict[str, Any]:
    if not isinstance(log, str) or not isinstance(context, dict):
        raise EnvelopeError("log must be text and context must be an object")
    bounded_log = log[:MAX_LOG_CHARS]
    sanitized_log, redactions = sanitize_text(bounded_log)
    changed_paths, paths_truncated = _clean_paths(context.get("changed_paths"))
    target = {}
    for key in ("build_system", "board", "build_target", "tuple"):
        value = _clean_scalar(context.get(key), key)
        if value:
            target[key] = value
    envelope = {
        "schema_version": 1,
        "kind": "ci_failure",
        "origin": _clean_scalar(origin, "origin") or "sanitized_ci_excerpt",
        "failed_job": _clean_scalar(context.get("failed_job"), "failed_job"),
        "failed_step": _clean_scalar(context.get("failed_step"), "failed_step"),
        "first_specific_error": first_specific_error(sanitized_log),
        "target": target,
        "changed_paths": changed_paths,
        "artifact_identity": _artifact_identity(context, sanitized_log),
        "input_truncated": len(log) > MAX_LOG_CHARS or paths_truncated,
        "redaction_count": redactions,
    }
    envelope["jev_state"] = {
        "kind": "ci_failure",
        "origin": envelope["origin"],
        "text": render_jev_text(envelope),
    }
    envelope["mcp_envelope"] = to_mcp_envelope(envelope)
    return envelope


def build_holdout_corpus(fixtures: dict[str, Any]) -> dict[str, Any]:
    if fixtures.get("schema_version") != 1 or not isinstance(fixtures.get("cases"), list):
        raise EnvelopeError("unsupported CI fixture schema")
    cases = []
    for case in fixtures["cases"]:
        envelope = extract_envelope(case.get("log"), case.get("context", {}), case.get("origin", "sanitized_ci_excerpt"))
        cases.append({
            "id": case["id"],
            "state": envelope["jev_state"],
            "expected": case["expected"],
        })
    return {
        "schema_version": 2,
        "corpus_id": fixtures["corpus_id"],
        "corpus_role": "holdout",
        "source_fixture_id": fixtures["fixture_id"],
        "cases": cases,
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise EnvelopeError("JSON input must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract = subparsers.add_parser("extract", help="extract one envelope")
    extract.add_argument("--log", type=Path, required=True)
    extract.add_argument("--context", type=Path, required=True)
    extract.add_argument("--origin", default="sanitized_ci_excerpt")
    build = subparsers.add_parser("build-corpus", help="build a frozen hold-out corpus")
    build.add_argument("--fixtures", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "extract":
            result = extract_envelope(args.log.read_text(encoding="utf-8", errors="replace"), _read_json(args.context), args.origin)
            print(json.dumps(result, indent=2))
            return 0
        result = build_holdout_corpus(_read_json(args.fixtures))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(result['cases'])} hold-out cases to {args.output}")
        return 0
    except (EnvelopeError, OSError, json.JSONDecodeError) as exc:
        print(f"CI envelope error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

