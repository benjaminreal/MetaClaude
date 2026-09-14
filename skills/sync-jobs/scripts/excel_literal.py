"""Safe Excel writes for text originating outside the workbook.

OpenPyXL guesses a leading ``=`` string is a formula. Force untrusted text to
the string cell type after replacing XML-illegal controls. This preserves the
original valid text value while formula-shaped variants remain inert.
"""
from __future__ import annotations

import re
_INVALID_XML_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_literal_text(value: str) -> str:
    """Return an XML-safe, formula-inert representation of untrusted text."""
    if not isinstance(value, str):
        raise TypeError("literal Excel text must be a string")
    return _INVALID_XML_CONTROL.sub("\ufffd", value)


def write_literal_text(cell, value: str) -> str:
    """Write untrusted text and force OpenPyXL to serialize a string cell."""
    normalized = normalize_literal_text(value)
    cell.value = normalized
    cell.data_type = "s"
    return normalized
