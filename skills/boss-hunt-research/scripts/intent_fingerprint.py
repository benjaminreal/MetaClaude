#!/usr/bin/env python3
"""Compute the canonical V3 fingerprint for one structured hook intent."""

from __future__ import annotations

import argparse
import hashlib
import json


def fingerprint(subject: str, claim: str, surface_family: str) -> str:
    signature = {"subject": " ".join(subject.lower().split()), "claim": " ".join(claim.lower().split()),
                 "surface_family": " ".join(surface_family.lower().split())}
    payload = json.dumps(signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--surface-family", required=True)
    args = parser.parse_args()
    print(fingerprint(args.subject, args.claim, args.surface_family))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
