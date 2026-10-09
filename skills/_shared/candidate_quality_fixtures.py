#!/usr/bin/env python3
"""Bilingual fixture catalog for the learning-candidate quality amendment.

Deterministic checks cover only mechanically observable defects. The fixture
catalog also declares the semantic verdict expected from a blinded human
scorecard; this script verifies that the rubric is complete, not that regexes
can judge plainness or standalone meaning.
"""

from __future__ import annotations

import re


RUBRIC_DIMENSIONS = (
    "plain_language",
    "standalone_meaning",
    "language_match",
    "one_central_insight",
    "uncertainty_fidelity",
)

FIXTURES = (
    {
        "id": "CQ-EN-POS",
        "language": "English",
        "polarity": "positive",
        "source_certainty": "observed",
        "candidate_certainty": "observed",
        "insight": (
            "Before deleting an original archive, verify that every source file "
            "has a retained copy and a matching content hash. Organizing the copy "
            "for retrieval does not replace provenance evidence."
        ),
        "expected_deterministic_issues": (),
        "expected_human_issues": (),
    },
    {
        "id": "CQ-EN-NEG",
        "language": "English",
        "polarity": "negative",
        "source_certainty": "tentative",
        "candidate_certainty": "certain",
        "insight": (
            "Session #41 proved that EVD-009 in /Volumes/Synthetic/archive always "
            "prevents outreach mistakes, and the dashboard should also change."
        ),
        "expected_deterministic_issues": (
            "ABSOLUTE_PATH",
            "INTERNAL_CODE",
            "SESSION_REFERENCE",
            "UNCERTAINTY_INFLATION",
        ),
        "expected_human_issues": (
            "not_plain_or_standalone",
            "multiple_insights",
        ),
    },
    {
        "id": "CQ-ES-POS",
        "language": "Spanish",
        "polarity": "positive",
        "source_certainty": "observed",
        "candidate_certainty": "observed",
        "insight": (
            "Antes de borrar un archivo original, verifica que cada fuente tenga "
            "una copia conservada y que su contenido coincida mediante una huella "
            "digital. Ordenar la copia para encontrarla mejor no sustituye la "
            "evidencia de procedencia."
        ),
        "expected_deterministic_issues": (),
        "expected_human_issues": (),
    },
    {
        "id": "CQ-ES-NEG",
        "language": "Spanish",
        "polarity": "negative",
        "source_certainty": "tentative",
        "candidate_certainty": "certain",
        "insight": (
            "La Sesión #43 y J-000890 en /Users/example/plan demuestran que esto "
            "siempre funciona, y también hay que cambiar la herramienta."
        ),
        "expected_deterministic_issues": (
            "ABSOLUTE_PATH",
            "INTERNAL_CODE",
            "SESSION_REFERENCE",
            "UNCERTAINTY_INFLATION",
        ),
        "expected_human_issues": (
            "not_plain_or_standalone",
            "multiple_insights",
        ),
    },
)

CERTAINTY = {"tentative": 0, "observed": 1, "certain": 2}


def deterministic_issues(fixture: dict) -> tuple[str, ...]:
    text = fixture["insight"]
    issues: set[str] = set()
    if re.search(r"\b(?:Session|Sesión)\s*#\d+\b", text, re.IGNORECASE):
        issues.add("SESSION_REFERENCE")
    if re.search(r"\b[A-Z]{1,8}-\d{3,}\b", text):
        issues.add("INTERNAL_CODE")
    if re.search(r"(?:^|\s)/(?:Users|Volumes|private|tmp)/\S+", text):
        issues.add("ABSOLUTE_PATH")
    if re.search(r"\b(?:GPT|Claude|Fable|Gemini)-?\d+(?:\.\d+)*\b", text):
        issues.add("MODEL_TOKEN")
    if CERTAINTY[fixture["candidate_certainty"]] > CERTAINTY[fixture["source_certainty"]]:
        issues.add("UNCERTAINTY_INFLATION")
    return tuple(sorted(issues))


def run() -> int:
    failures: list[str] = []
    combinations = {(item["language"], item["polarity"]) for item in FIXTURES}
    expected_combinations = {
        ("English", "positive"),
        ("English", "negative"),
        ("Spanish", "positive"),
        ("Spanish", "negative"),
    }
    if combinations != expected_combinations:
        failures.append(f"fixture matrix mismatch: {sorted(combinations)}")

    for fixture in FIXTURES:
        actual = deterministic_issues(fixture)
        expected = tuple(sorted(fixture["expected_deterministic_issues"]))
        if actual != expected:
            failures.append(f"{fixture['id']}: deterministic {actual} != {expected}")
        human = fixture["expected_human_issues"]
        if fixture["polarity"] == "positive" and human:
            failures.append(f"{fixture['id']}: positive fixture declares semantic defects")
        if fixture["polarity"] == "negative" and not human:
            failures.append(f"{fixture['id']}: negative fixture lacks semantic defects")

    print("Candidate-quality bilingual fixture matrix")
    for fixture in FIXTURES:
        status = "PASS" if not any(item.startswith(fixture["id"]) for item in failures) else "FAIL"
        print(
            f"  [{status}] {fixture['id']} "
            f"deterministic={list(deterministic_issues(fixture))} "
            f"human_expected={list(fixture['expected_human_issues'])}"
        )
    print(
        "  Human scorecard dimensions: "
        + ", ".join(RUBRIC_DIMENSIONS)
        + " (not mechanically inferred)"
    )
    for failure in failures:
        print(f"        └─ {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
