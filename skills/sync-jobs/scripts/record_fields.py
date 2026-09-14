"""Shared normalization for source record field aliases."""
from __future__ import annotations


DESCRIPTION_ALIASES = ("description", "descriptionText", "jobDescriptionText", "about")


def description_value(record: dict) -> str:
    values = [(key, value) for key in DESCRIPTION_ALIASES
              if isinstance((value := record.get(key)), str) and value.strip()]
    if not values:
        return ""
    if len({value.strip() for _, value in values}) > 1:
        raise ValueError(f"conflicting nonempty description aliases: {[key for key, _ in values]}")
    return values[0][1]


def normalize_description(record: dict) -> dict:
    normalized = dict(record)
    normalized["description"] = description_value(normalized)
    for alias in DESCRIPTION_ALIASES[1:]:
        normalized.pop(alias, None)
    return normalized
