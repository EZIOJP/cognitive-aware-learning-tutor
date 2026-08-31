"""CLI: python -m backend.behavior.device_block_cli apply|remove|status"""

from __future__ import annotations

import argparse
import json
import sys

from backend.behavior.device_block import apply_from_settings, remove_all, status, verify_hostname_blocked


def main() -> int:
    parser = argparse.ArgumentParser(description="CALT device-wide hosts block")
    parser.add_argument("action", choices=["apply", "remove", "status", "verify"])
    parser.add_argument("--enable", action="store_true", help="Set enabled=true before apply")
    args = parser.parse_args()

    if args.action == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if args.action == "verify":
        print(json.dumps(verify_hostname_blocked("pornhub.com"), indent=2))
        return 0
    if args.action == "remove":
        out = remove_all()
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    out = apply_from_settings(enable=args.enable or True)
    print(json.dumps(out, indent=2))
    if not out.get("ok"):
        return 1
    if out.get("applied") and not out.get("effective", True):
        print("WARNING: hosts written but youtube.com still resolves to real IPs — restart browsers.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
