#!/usr/bin/env python3
"""Fail closed on incomplete or contradictory AESL board lifecycle records."""

from __future__ import annotations

import json
import sys
from pathlib import Path


path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config/board-support.json")
data = json.loads(path.read_text(encoding="utf-8"))

if data.get("schema_version") != 1:
    raise SystemExit("unsupported board-support schema")
platform = data.get("platform", {})
if platform.get("minimum_support_years", 0) < 5:
    raise SystemExit("platform support floor must be at least five years")

required = {
    "id",
    "role",
    "android_product",
    "status",
    "cra_product_classification",
    "support_start",
    "support_end",
    "gpu_stack",
    "media_stack",
    "vendor_source",
}
seen_ids: set[str] = set()
seen_products: set[str] = set()
for board in data.get("boards", []):
    missing = sorted(required - board.keys())
    if missing:
        raise SystemExit(f"{board.get('id', '<unknown>')}: missing {', '.join(missing)}")
    if board["id"] in seen_ids:
        raise SystemExit(f"duplicate board id: {board['id']}")
    if board["android_product"] in seen_products:
        raise SystemExit(f"duplicate Android product: {board['android_product']}")
    seen_ids.add(board["id"])
    seen_products.add(board["android_product"])

    if board["role"] == "product-candidate" and board.get("expected_lifetime_years") is not None:
        if board["expected_lifetime_years"] < platform["minimum_support_years"]:
            raise SystemExit(f"{board['id']}: expected lifetime is below support floor")
    if board["status"] == "supported":
        for field in ("support_start", "support_end", "expected_lifetime_years"):
            if board.get(field) in (None, ""):
                raise SystemExit(f"{board['id']}: supported board has no {field}")
        if board["cra_product_classification"].startswith("pending-"):
            raise SystemExit(f"{board['id']}: supported board still has pending CRA classification")
        if board.get("blocked_release_gates"):
            raise SystemExit(f"{board['id']}: supported board still has blocked release gates")

if not data.get("boards"):
    raise SystemExit("board-support matrix is empty")

print(f"board support matrix valid: {len(data['boards'])} entries")
