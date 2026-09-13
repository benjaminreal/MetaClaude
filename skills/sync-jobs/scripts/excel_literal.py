"""Safe Excel writes for text originating outside the workbook.

OpenPyXL guesses a leading ``=`` string is a formula.  Force untrusted text to
the string cell type, and prefix formula-shaped values with Excel's literal
marker so whitespace/control-prefixed variants remain inert after reload.
"""
from __future__ import annotations

import re
import unicodedata


_INVALID_XML_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _formula_shaped(value: str) -> bool:
    for character in value:
        if character in "=+-@":
            return True
        if character.isspace() or unicodedata.category(character) in {"Cc", "Cf"}:
            continue
        return False
    return False


def normalize_literal_text(value: str) -> str:
    """Return an XML-safe, formula-inert representation of untrusted text."""
    if not isinstance(value, str):
        raise TypeError("literal Excel text must be a string")
    dangerous = _formula_shaped(value)
    value = _INVALID_XML_CONTROL.sub("\ufffd", value)
    return "'" + value if dangerous else value


def write_literal_text(cell, value: str) -> str:
    """Write untrusted text and force OpenPyXL to serialize a string cell."""
    normalized = normalize_literal_text(value)
    cell.value = normalized
    cell.data_type = "s"
    return normalized
