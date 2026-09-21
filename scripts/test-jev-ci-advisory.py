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
REGISTRATION_SCRIPT = Path(__file__).with_name("register-ci-wait.py")
REGISTRATION_SPEC = importlib.util.spec_from_file_location("register_ci_wait", REGISTRATION_SCRIPT)
registration = importlib.util.module_from_spec(REGISTRATION_SPEC)
assert REGISTRATION_SPEC.loader is not None
REGISTRATION_SPEC.loader.exec_module(registration)
FAIL_FAST_SCRIPT = Path(__file__).with_name("ci-fail-fast.py")
FAIL_FAST_SPEC = importlib.util.spec_from_file_location("ci_fail_fast", FAIL_FAST_SCRIPT)
fail_fast = importlib.util.module_from_spec(FAIL_FAST_SPEC)
assert FAIL_FAST_SPEC.loader is not None
FAIL_FAST_SPEC.loader.exec_module(fail_fast)


class JevCiAdvisoryClientTests(unittest.TestCase):
    def test_wait_registration_is_exact_and_bounded(self):
        payload = registration.build_registration(
            12345, 2, "01a0b366-c1d1-7260-860f-e128d360c7d9", now=1_700_000_000,
        )
        self.assertEqual(
            payload["correlation_id"],
            "github:active-esl/waydroid-product-manifest:12345:2",
        )
        self.assertEqual(payload["expires_at"], 1_700_604_740)
        self.assertNotIn("prompt", payload)

    def test_wait_registration_rejects_non_task_identity(self):
        with self.assertRaises(ValueError):
            registration.build_registration(12345, 2, "Plan kiosk browser tuple")

    def test_fail_fast_detects_actionable_android_failure(self):
        evidence = fail_fast.detect_failure(
            "framework.cpp:812:7: error: use of undeclared identifier 'displayMode'"
        )
        self.assertEqual(evidence["reason"], "android_actionable_failure")
        self.assertIsNone(fail_fast.detect_failure("[ 91%] routine build progress"))

    def test_fail_fast_ignores_failed_class_name_in_soong_path(self):
        line = (
            "Warning in ./out-imx95-frdm/soong/.intermediates/packages/modules/"
            "ExtServices/ExtServices-sminus.jar:kotlinx/coroutines/channels/"
            "ChannelResult$Failed.class:"
        )
        self.assertIsNone(fail_fast.detect_failure(line))

    def test_fail_fast_redacts_secret_from_bounded_evidence(self):
        evidence = fail_fast.detect_failure(
            "FAILED: Authorization: Bearer should-not-cross"
        )
        self.assertNotIn("should-not-cross", json.dumps(evidence))

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

    def test_late_failure_is_reduced_without_forwarding_log_noise(self):
        log = "routine build progress\n" * 20_000
        log += "framework.cpp:812:7: error: use of undeclared identifier 'displayMode'\n"
        body = advisory.build_request_body(
            log, self.context(),
            "github:active-esl/waydroid-product-manifest:12345:1",
        )
        payload = json.loads(body)
        evidence = payload["envelope"]["first_specific_error"]
        self.assertIn("displayMode", evidence)
        self.assertLess(len(body), 8_000)
        self.assertNotIn("routine build progress", body.decode())

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
