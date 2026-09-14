#!/usr/bin/env python3
"""Shared append-to-cell mechanism for the two workbook writers.

Why this exists
---------------
Two historical workbook writers needed "add to this cell without destroying
what is there" and had drifted apart:

  * write_tracker hardcoded the behaviour for ONE column, `Comentarios`, joined
    with a single newline, deduplicated by batch tag.
  * the other writer had no append operation. `set` could silently clobber
    existing notes; dry-run comparison exposed the risk.

This module is the single implementation. It keeps BOTH dedup strategies,
because they are genuinely different and both are correct in their place:

  * dedup by MARKER (write_tracker's `Comentarios`): re-running the same batch
    must not add a second line even if the note text was edited. The marker is
    the dated batch tag.
  * dedup by TEXT (BossHunt free-text columns): there is no batch tag, so the
    addition itself is the identity.

Separator is per-caller: `Comentarios` is a one-line-per-event log ("\\n"),
BossHunt free-text columns are prose paragraphs ("\\n\\n"). Changing either
would rewrite the look of years of existing cells, so neither is normalised.

Nothing here touches a workbook. Callers own load, formula checks, and save.
"""

from __future__ import annotations

SEP_PARAGRAPH = "\n\n"   # prose columns: blank line between blocks
SEP_LINE = "\n"          # log columns: one entry per line


class AppendError(ValueError):
    """Raised on an append request that must not be attempted."""


def append_value(current, addition: str, sep: str = SEP_PARAGRAPH,
                 dedup_marker: str | None = None) -> tuple[str, bool]:
    """Return (new_value, changed).

    `changed` is False when the addition is already represented, which is what
    makes a re-run a no-op instead of a duplicated audit line. When
    `dedup_marker` is given, presence of THAT string decides; otherwise the
    addition text itself decides.

    An empty existing cell yields the addition alone, with no leading
    separator.
    """
    addition = "" if addition is None else str(addition).strip()
    if not addition:
        return ("" if current in (None, "") else str(current)), False
    existing = "" if current in (None, "") else str(current)
    probe = dedup_marker if dedup_marker is not None else addition
    if probe and probe in existing:
        return existing, False
    return (existing + sep + addition if existing else addition), True


def validate_append_block(row_id: str, set_cols, append_cols, allowed) -> None:
    """Fail loudly before any cell is touched.

    Two ways an append request is wrong regardless of the data:
      * the same column in both `set` and `append` — ambiguous intent, and
        whichever ran last would silently win;
      * an append onto a controlled column (status, date, id) — the cell would
        stop parsing as what it is.
    """
    both = {str(c).strip() for c in set_cols} & {str(c).strip() for c in append_cols}
    if both:
        raise AppendError(
            f"{row_id}: column(s) {sorted(both)} appear in both 'set' and 'append'. "
            f"Intent is ambiguous; pick one.")
    for c in append_cols:
        if str(c).strip() not in allowed:
            raise AppendError(
                f"{row_id}: 'append' is not allowed on {str(c).strip()!r}. Appending to a "
                f"controlled column would corrupt it. Allowed: {sorted(allowed)}. Use 'set'.")
