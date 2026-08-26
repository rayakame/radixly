"""Shared rejection tables: both implementations must reject each input with
the same kind at the same position, pinned to each other through this data."""

from __future__ import annotations

from tests.reference import base32768 as base32768_reference

__all__ = (
    "BAD_CASES",
    "CANONICALITY_CASES",
    "HOSTILE_NON_BMP",
    "NON_STR_INPUTS",
    "PICKLE_MESSAGE_CASES",
    "PICKLE_POSITION",
)

# Each bad vector pins both the failure mode and the position it occurs at.
BAD_CASES: dict[str, int] = {
    "bad-padding": 3,
    "bad0": 0,
    "not-base32768-char": 111,
}

_VALID_8_CHARS = base32768_reference.encode(bytes(15))  # 120 bits: 8 full 15-bit characters, no padding

# Astral exercises the bounds guard, surrogates the painted reverse-table cells;
# the mid-string entries pin the position as a code-point index.
HOSTILE_NON_BMP: dict[str, tuple[str, int]] = {
    "astral": ("\U0001f600", 0),
    "high-surrogate": ("\ud800", 0),
    "low-surrogate": ("\udfff", 0),
    "astral-mid-string": (_VALID_8_CHARS + "\U0001f600" + _VALID_8_CHARS, 8),
    "surrogate-mid-string": (_VALID_8_CHARS + "\udc00" + _VALID_8_CHARS, 8),
}

_PURE_PADDING = base32768_reference.LOOKUP_E[7][127]  # 'ʟ', a 7-bit character that is all filler

# The deliberate divergence from qntm (CLAUDE.md): zero-payload final chars are
# rejected so decode is injective. Both would decode fine under qntm's rules.
CANONICALITY_CASES: dict[str, tuple[str, int]] = {
    "lone-padding": (_PURE_PADDING, 0),
    "appended-padding": (_VALID_8_CHARS + _PURE_PADDING, 8),
}

# For both implementations' type rejections: decode() takes str, full stop.
NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)

# Pickle flavors: kwargs -> the message every view of the clone must agree on;
# "empty" cross-checks that option c and the pickle state channel compose.
PICKLE_POSITION: int = 5
PICKLE_MESSAGE_CASES: dict[str, tuple[dict[str, str], str]] = {
    "explicit": ({"message": "boom"}, "boom"),
    "empty": ({"message": ""}, ""),
    "generated": ({}, f"Decode Error at position {PICKLE_POSITION}"),
}
