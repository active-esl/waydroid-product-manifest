#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True)
parser.add_argument("--source-lock", required=True)
parser.add_argument("--targets", nargs="+", required=True)
parser.add_argument("--arm64-variant", choices=("user", "userdebug"), required=True)
args = parser.parse_args()

lock = Path(args.source_lock)
source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
if not source_date_epoch:
    raise SystemExit("SOURCE_DATE_EPOCH is required")

document = {
    "schema": 1,
    "owner": "Active ESL",
    "android_release": "r16",
    "lineage_release": "23.2",
    "maintenance_class": "maintained-5-plus-years",
    "targets": args.targets,
    "product_profiles": [
        {
            "target": target,
            "memory_profile": "2gb" if "aesl_2gb" in target else "standard",
            "board_profile": "imx95_frdm" if "aesl_imx95" in target else (
                "imx8mm" if "arm64" in target else "framework"
            ),
        }
        for target in args.targets
        if "arm64" in target
    ],
    "arm64_variant": args.arm64_variant,
    "release_class": "production" if args.arm64_variant == "user" else "integration",
    "selinux_gate": "production" if args.arm64_variant == "user" else "inventory",
    "source_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
    "source_date_epoch": int(source_date_epoch),
    "ci_revision": os.environ.get("GITHUB_SHA"),
    "generated_utc": datetime.datetime.fromtimestamp(
        int(source_date_epoch), datetime.timezone.utc
    ).isoformat(),
}
Path(args.output).write_text(json.dumps(document, indent=2) + "\n")
