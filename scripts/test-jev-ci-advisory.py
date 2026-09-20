#!/usr/bin/env python3
"""Deterministic boundary tests for the FRDM Jev advisory client."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("request-jev-ci-advisory.py")
SPEC = importlib.util.spec_from_file_location("request_jev_ci_advisory", SCRIPT)
advisory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(advisory)
COMPLETION_SCRIPT = Path(__file__).with_name("emit-ci-completion.py")
COMPLETION_SPEC = importlib.util.spec_from_file_location("emit_ci_completion", COMPLETION_SCRIPT)
completion = importlib.util.module_from_spec(COMPLETION_SPEC)
assert COMPLETION_SPEC.loader is not None
COMPLETION_SPEC.loader.exec_module(completion)


class JevCiAdvisoryClientTests(unittest.TestCase):
    def context(self):
        return {
            "failed_job": "Android R16 / LineageOS 23.2 - FRDM i.MX95 standard vendor",
            "failed_step": "Build Android R16 / LineageOS 23.2 image scope",
            "build_system": "android-soong-ninja",
            "board": "imx95-frdm",
            "build_target": "imx95_frdm",
            "tuple": "android-r16:lineageos-23.2:imx95-frdm:standard:arm64",
            "artifact_name": "android-r16-frdm-12345-1",
        }

    def test_request_contains_only_the_bounded_envelope(self):
        body = advisory.build_request_body(
            "Authorization: Bearer should-not-cross\nFAILED: out/soong/vendor.img",
            self.context(),
            "github:active-esl/waydroid-product-manifest:12345:1",
        )
        payload = json.loads(body)
        self.assertEqual(set(payload), {"schema_version", "request_id", "lane", "envelope"})
        self.assertNotIn("raw_log", payload["envelope"])
        self.assertNotIn("should-not-cross", body.decode())
        self.assertEqual(payload["envelope"]["target"]["board"], "imx95-frdm")

    def test_accepts_only_a_read_only_artifact(self):
        value = {
            "advisory": {
                "mode": "failure_only_non_required_advisory",
                "changes_execution": False,
                "can_authorize": False,
                "can_mark_ci_green": False,
                "can_retry_ci": False,
            },
            "markdown": "# Jev CI advisory\n",
        }
        parsed, markdown = advisory.validate_response(value)
        self.assertFalse(parsed["changes_execution"])
        self.assertTrue(markdown.startswith("# Jev"))

    def test_rejects_execution_authority(self):
        value = {
            "advisory": {
                "mode": "failure_only_non_required_advisory",
                "changes_execution": True,
                "can_authorize": False,
                "can_mark_ci_green": False,
                "can_retry_ci": False,
            },
            "markdown": "unsafe",
        }
        with self.assertRaises(ValueError):
            advisory.validate_response(value)

    def test_success_event_is_bounded_and_resumable(self):
        event = completion.build_event(12345, 2, "a" * 40)
        self.assertEqual(event["status"], "PASSED")
        self.assertEqual(event["lane"], "android-frdm")
        self.assertEqual(
            event["build"]["evidence_location"],
            "/yocto/android-16-artifacts/12345-2",
        )
        self.assertNotIn("log", event)


if __name__ == "__main__":
    unittest.main()
