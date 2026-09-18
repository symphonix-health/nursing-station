"""Shared narrative, identifier and attestation text validation.

Pydantic's ``min_length`` counts characters, so a string made only of
ordinary spaces -- or of zero-width Unicode formatting characters that
``str.isspace()``/``str.strip()`` do not recognise as whitespace at all --
satisfies ``Field(min_length=...)`` while carrying no reportable content.
A mandatory narrative field (an incident description, a staffing shortage
reason, a SBAR line, a medication-outcome reason) or an attestation note
must refuse such a value outright: it is not "short", it is empty.

Estate-wide input-validation run, 2026-09-18 (F-IV-000 follow-on): the
native `required`/`minLength` markers this repo already uses are real and
should not be weakened; this closes the gap they cannot cover on their
own.
"""

from __future__ import annotations

# Zero-width / invisible formatting characters that are not classified as
# whitespace by str.isspace() / str.strip(), so a naive `.strip()` check
# (the pattern already used for the handover decline reason) does not
# catch a value built only from these.
_INVISIBLE_CHARS = (
    "​"  # zero width space
    "‌"  # zero width non-joiner
    "‍"  # zero width joiner
    "⁠"  # word joiner
    "﻿"  # zero width no-break space / BOM
    "­"  # soft hyphen
)
_STRIP_TABLE = {ord(character): None for character in _INVISIBLE_CHARS}


def is_blank(value: str) -> bool:
    """True if `value` has no visible content once ordinary whitespace and
    invisible Unicode formatting characters are removed."""
    return value.translate(_STRIP_TABLE).strip() == ""


def require_meaningful_text(value: str) -> str:
    """Pydantic field validator: refuse whitespace-only or invisible-Unicode-only text.

    Applied only to fields that already carry their own `min_length` --
    this never loosens or replaces that check, it closes the gap it leaves.
    """
    if is_blank(value):
        raise ValueError("must contain visible text, not only whitespace or invisible characters")
    return value


def require_meaningful_text_if_present(value: str | None) -> str | None:
    """Same as `require_meaningful_text`, for an optional field that is only
    validated when a value was actually supplied."""
    if value is not None and is_blank(value):
        raise ValueError("must contain visible text, not only whitespace or invisible characters")
    return value


def require_meaningful_items(values: list[str]) -> list[str]:
    """Same as `require_meaningful_text`, for each entry of a list field
    (e.g. contributory factors, learning actions) split from free text."""
    if any(is_blank(item) for item in values):
        raise ValueError("each entry must contain visible text, not only whitespace or invisible characters")
    return values
