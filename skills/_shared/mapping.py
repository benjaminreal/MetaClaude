#!/usr/bin/env python3
"""Frozen-to-v2 checklist mapping (Phase 1 deliverable 1 of 5).

Encodes Appendix 1 of `lifecycle_contract_v1.md` — the 83-row exit-gate
disposition table — as data the scorer can enforce.

Dispositions
------------
retained : the frozen check survives unchanged; the v2 ID is a rename only.
mapped   : the frozen check survives with altered semantics; the v2 ID(s)
           state what it became. Still scored under the frozen checklist.
retired  : the frozen check is withdrawn with user sign-off (2026-08-03).
           Excluded from BOTH numerator and denominator of the adjusted
           frozen rate. Reported separately, never silently dropped.

Why retired checks are excluded from the denominator as well as the numerator:
a v2-correct run fails a retired check *by design*, so leaving it in the
denominator would make correct behavior read as regression -- the symmetric
failure to "metrics improve by deletion".
"""

from __future__ import annotations

RETAINED, MAPPED, RETIRED = "retained", "mapped", "retired"

# --- newbeginning: 29 frozen checks (15 retained / 13 mapped / 1 retired) ---
NEWBEGINNING: dict[str, tuple[str, tuple[str, ...], str]] = {
    "1":   (RETAINED, ("REC-1",),            ""),
    "2":   (MAPPED,   ("REC-3", "APR-1"),    "approval gate now explicit"),
    "3":   (RETAINED, ("REC-2",),            ""),
    "4":   (MAPPED,   ("REC-4",),            "splits into content/empty branches"),
    "5":   (MAPPED,   ("OBS-2",),            "now helper-deterministic"),
    "6":   (RETAINED, ("BRF-1",),            ""),
    "7":   (RETAINED, ("BRF-2",),            ""),
    "8":   (MAPPED,   ("BRF-3",),            "now requires the OBS-5 receipt"),
    "9":   (RETAINED, ("BRF-4",),            ""),
    "10":  (RETAINED, ("BRF-5",),            ""),
    "11":  (MAPPED,   ("VER-1", "OBS-6"),    "splits: narrative provenance vs fingerprint match (pair-15 defect)"),
    "12":  (RETAINED, ("BRF-6",),            ""),
    "12a": (RETAINED, ("BRF-7",),            ""),
    "13":  (RETAINED, ("CLS-1",),            ""),
    "14":  (MAPPED,   ("CLS-2",),            "keyed to the four-state capability"),
    "15":  (RETAINED, ("CLS-3",),            ""),
    "16":  (MAPPED,   ("APR-3", "VER-3"),    ""),
    "17":  (MAPPED,   ("REC-5",),            ""),
    "18":  (RETAINED, ("REC-6",),            ""),
    "19":  (RETAINED, ("REC-7",),            ""),
    "20":  (MAPPED,   ("APR-1",),            "generalized to the M2 approval gate"),
    "21":  (RETAINED, ("REC-8",),            ""),
    "22":  (MAPPED,   ("CAP-3",),            ""),
    "23":  (MAPPED,   ("CAP-4",),            ""),
    "24":  (MAPPED,   ("CAP-5",),            "must name which of four states"),
    "25":  (RETAINED, ("CAP-6",),            ""),
    "25a": (MAPPED,   ("CAP-1",),            "must name which of four states"),
    "25b": (RETAINED, ("CAP-2",),            ""),
    "26":  (RETIRED,  ("BUD-1", "BUD-2", "BUD-3"),
            "unachievable: the skill body alone exceeds the budget before the first read"),
}

# --- closingtime: 42 frozen checks (23 retained / 18 mapped / 1 retired) ---
CLOSINGTIME: dict[str, tuple[str, tuple[str, ...], str]] = {
    "1":   (MAPPED,   ("OBS-1",),            "snapshot-receipt-backed; failed 7 of 8 Fable runs"),
    "2":   (MAPPED,   ("OBS-3",),            "failed 7 of 8 Fable runs"),
    "3":   (MAPPED,   ("OBS-4",),            ""),
    "4":   (MAPPED,   ("CAP-7",),            "3 and 4 now mutually auditable"),
    "5":   (MAPPED,   ("OBS-2",),            "shared with the opening skill"),
    "6":   (MAPPED,   ("DRF-1",),            "redefined via the M1 path rule: scratch is legal"),
    "7":   (RETAINED, ("DRF-2",),            ""),
    "8":   (RETAINED, ("DRF-3",),            ""),
    "9":   (RETAINED, ("BRF-8",),            ""),
    "10":  (RETAINED, ("BRF-9",),            ""),
    "11":  (RETAINED, ("BRF-10",),           ""),
    "12":  (RETAINED, ("BRF-11",),           ""),
    "13":  (MAPPED,   ("CNC-2",),            "allocated under compare-and-swap"),
    "14":  (RETAINED, ("BRF-12",),           ""),
    "15":  (RETAINED, ("BRF-13",),           ""),
    "16":  (RETAINED, ("BRF-14",),           ""),
    "17":  (RETAINED, ("BRF-15",),           ""),
    "18":  (RETAINED, ("BRF-16",),           ""),
    "19":  (MAPPED,   ("APR-2", "VER-2"),    ""),
    "20":  (RETAINED, ("BRF-17",),           ""),
    "21":  (MAPPED,   ("VER-2",),            "requires a returned result"),
    "22":  (RETAINED, ("APR-4",),            ""),
    "23":  (RETAINED, ("BRF-18",),           ""),
    "24":  (RETAINED, ("BRF-19",),           ""),
    "24a": (MAPPED,   ("VER-4",),            "requires a current receipt"),
    "24b": (MAPPED,   ("CAP-1",),            ""),
    "25":  (RETAINED, ("LRN-1",),            ""),
    "26":  (RETAINED, ("LRN-2",),            ""),
    "27":  (MAPPED,   ("LRN-3",),            "or an explicit unavailable record; failed 6 Fable / 4 Sol"),
    "28":  (RETAINED, ("LRN-4",),            "failed 5 of 8 on each model; fixed by the ordering gate"),
    "29":  (RETAINED, ("LRN-5",),            ""),
    "30":  (MAPPED,   ("LRN-6",),            "disposition follows approval: delete or retain"),
    "31":  (RETAINED, ("LRN-7",),            ""),
    "32":  (MAPPED,   ("CAP-5",),            ""),
    "33":  (MAPPED,   ("CLS-4",),            "emitted only from verified receipts"),
    "34":  (RETAINED, ("CLS-5",),            ""),
    "35":  (RETAINED, ("CLS-6",),            ""),
    "36":  (MAPPED,   ("REC-9",),            ""),
    "37":  (MAPPED,   ("REC-10",),           ""),
    "38":  (RETAINED, ("CLS-7",),            ""),
    "39":  (MAPPED,   ("CLS-8",),            "interrupted path"),
    "40":  (RETIRED,  ("BUD-4",),            "unscoreable: no threshold, no measurement"),
}

MAPPING = {"newbeginning": NEWBEGINNING, "closingtime": CLOSINGTIME}

# v2-only checks -- no frozen ancestor. These are why the v2 denominator differs.
V2_ONLY = {
    "OBS-5": "authoritative task claim carries a current receipt from this invocation",
    "OBS-6": "recomputed row_fingerprint matches the asserted value",
    "OBS-7": "sync-conflict detection ran for every M2 file",
    "CNC-1": "tail hash rechecked immediately before append",
    "CNC-3": "injected foreign modification detected; append stopped",
    "ENF-1": "append_session_entry refuses an invalid or absent envelope",
    "ENF-2": "a journal record exists for every accepted append",
    "ENF-3": "audit_session_log reports zero unjournaled entries above the ceiling",
    "CAP-8": "root instruction resolution handles all three cases",
    "ACT-1": "all 21 trigger phrases activate the intended skill",
    "ACT-2": "negative phrases activate neither skill",
    "ACT-3": "no cross-skill step-number reference",
    "BUD-1": "instruction_bytes_loaded reported",
    "BUD-2": "projection_bytes_emitted at or below the frozen cap",
    "BUD-3": "brief_words <= 250",
    "BUD-4": "marginal-cost diagnostics recorded (non-blocking)",
    "VER-5": "every M2/M3 mutation has a recorded readback or returned result",
}

EXPECTED_COUNTS = {
    "newbeginning": {RETAINED: 15, MAPPED: 13, RETIRED: 1, "total": 29},
    "closingtime":  {RETAINED: 23, MAPPED: 18, RETIRED: 1, "total": 42},
}


def counts(skill: str) -> dict[str, int]:
    table = MAPPING[skill]
    out = {RETAINED: 0, MAPPED: 0, RETIRED: 0, "total": len(table)}
    for disposition, _v2, _note in table.values():
        out[disposition] += 1
    return out


def retired_ids(skill: str) -> set[str]:
    return {k for k, (d, _v, _n) in MAPPING[skill].items() if d == RETIRED}


def scored_ids(skill: str) -> set[str]:
    """Frozen checks that remain in the adjusted denominator (retained + mapped)."""
    return {k for k, (d, _v, _n) in MAPPING[skill].items() if d != RETIRED}


def self_check() -> list[str]:
    """The table must match the contract's published counts exactly."""
    issues: list[str] = []
    for skill, expected in EXPECTED_COUNTS.items():
        got = counts(skill)
        if got != expected:
            issues.append(f"{skill}: expected {expected}, got {got}")
    total = sum(len(t) for t in MAPPING.values())
    if total != 71:
        issues.append(f"frozen row total should be 71, got {total}")
    for skill, table in MAPPING.items():
        for cid, (disp, v2, _note) in table.items():
            if disp not in (RETAINED, MAPPED, RETIRED):
                issues.append(f"{skill}/{cid}: unknown disposition {disp!r}")
            if not v2:
                issues.append(f"{skill}/{cid}: no v2 target")
    return issues


if __name__ == "__main__":
    import sys

    problems = self_check()
    for skill in MAPPING:
        c = counts(skill)
        print(f"{skill:14} total={c['total']:3}  retained={c[RETAINED]:3}  "
              f"mapped={c[MAPPED]:3}  retired={c[RETIRED]}")
    print(f"{'frozen total':14} {sum(len(t) for t in MAPPING.values())}  "
          f"+ 12 Opus recommendations = 83 exit-gate rows")
    print(f"{'v2-only checks':14} {len(V2_ONLY)}")
    if problems:
        print("\nSELF-CHECK FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\nself-check OK")
