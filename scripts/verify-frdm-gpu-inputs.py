#!/usr/bin/env python3
"""Fail closed on the exact FRDM Mali/allocator input accepted for integration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


GPU_RELEASE = "android-16.0.0_1.2.0"
GPU_REVISION = "r54p1-11eac0"
EXPECTED = {
    "gpu-mali": "b98e01a584f59e3a77a3a4b2aebd266a279369f0ea0fcb01e7e2d01850063410",
    "wsialloc": "3e9b82348d1e08be3e4aecd40927cda55f5f7974afb0d8e04780fca982047b7a",
}
SCR_SHA256 = "28171b2f7f4b78f9c0e2462a2cf220ada9921e5493b1770056daa6b4519035fd"
EULA_SHA256 = "3001cf84018c5cb10d183a678f6ec8a928c797616ba06b398d7ca93c0779aaa2"
MALI_SHA256 = "7f8453a46e2f32432f77607187696d78375fb9f60e72505ad6d5b793e9ca01e4"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: Path) -> tuple[str, int]:
    if not root.is_dir():
        raise ValueError("missing input directory: {}".format(root))
    entries = sorted(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise ValueError("unreviewed symlink in {}".format(root))
    files = [path for path in entries if path.is_file()]
    if not files:
        raise ValueError("empty input directory: {}".format(root))
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update("{}  {}\n".format(file_sha256(path), relative).encode())
    return digest.hexdigest(), len(files)


def verify_hash(path: Path, expected: str) -> None:
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError("unexpected SHA-256 for {}: {}".format(path, actual))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    scr = args.stage / "SCR-android-16.0.0_1.2.0.txt"
    eula = args.stage / "EULA.txt"
    verify_hash(scr, SCR_SHA256)
    verify_hash(eula, EULA_SHA256)
    if "Release - Android {}".format(GPU_RELEASE) not in scr.read_text():
        raise ValueError("staged NXP release marker is incorrect")

    input_paths = {
        "gpu-mali": "vendor/nxp/fsl-proprietary/gpu-mali",
        "wsialloc": "vendor/nxp/wsialloc",
    }
    evidence = {"gpu_blob_release": GPU_RELEASE, "gpu_driver_revision": GPU_REVISION}
    for name, relative in input_paths.items():
        workspace_digest, count = tree_sha256(args.workspace / relative)
        stage_digest, _ = tree_sha256(args.stage / relative)
        if workspace_digest != EXPECTED[name] or stage_digest != EXPECTED[name]:
            raise ValueError("{} input differs from the reviewed tree".format(name))
        evidence[name.replace("-", "_") + "_tree_sha256"] = workspace_digest
        evidence[name.replace("-", "_") + "_file_count"] = count

    mali = args.workspace / "vendor/nxp/fsl-proprietary/gpu-mali/lib64/egl/libGLES_mali.so"
    verify_hash(mali, MALI_SHA256)
    if GPU_REVISION.encode() not in mali.read_bytes():
        raise ValueError("Mali userspace does not identify the reviewed driver revision")
    evidence["libGLES_mali_sha256"] = MALI_SHA256
    evidence["scr_sha256"] = SCR_SHA256
    evidence["eula_sha256"] = EULA_SHA256
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print("verified FRDM Mali {} input and allocator".format(GPU_REVISION))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
