"""Shared rejection tables: the error-differential contract as data.

Both implementations must reject each input here with the same kind at the
same position. test_reference.py asserts the oracle's side and test_core.py
the C side, from these tables — so the two decoders are pinned to each other
through the data, not through parallel hand-maintained assertions.
"""

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

# The two non-BMP input kinds stress two different C defenses: an astral code
# point would index past the reverse table entirely (the cp bounds guard),
# while a lone surrogate sails through it and relies on those 2048 cells
# holding the sentinel. The mid-string entries pin that the reported position
# is the code-point index of the offender, not 0 and not a byte offset.
HOSTILE_NON_BMP: dict[str, tuple[str, int]] = {
    "astral": ("\U0001f600", 0),
    "high-surrogate": ("\ud800", 0),
    "low-surrogate": ("\udfff", 0),
    "astral-mid-string": (_VALID_8_CHARS + "\U0001f600" + _VALID_8_CHARS, 8),
    "surrogate-mid-string": (_VALID_8_CHARS + "\udc00" + _VALID_8_CHARS, 8),
}

_PURE_PADDING = base32768_reference.LOOKUP_E[7][127]  # 'ʟ', a 7-bit character that is all filler

# The M1 divergence from qntm's reference JS (see CLAUDE.md): a final
# character carrying zero payload bits is rejected so that decode is
# injective -- one payload, exactly one accepted spelling.
# - lone-padding: 'ʟ' alone would be a second spelling of b"".
# - appended-padding, the sneaky cousin: a valid 8-character encoding plus
#   'ʟ' would decode to the same payload under qntm's rules. A blanket
#   "reject every 7-bit character" bug would pass both of these, which is
#   why the reference file also asserts the unextended base still decodes.
CANONICALITY_CASES: dict[str, tuple[str, int]] = {
    "lone-padding": (_PURE_PADDING, 0),
    "appended-padding": (_VALID_8_CHARS + _PURE_PADDING, 8),
}

# For both implementations' type rejections: decode() takes str, full stop.
NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)

# Pickle round-trip flavors: constructor kwargs -> the message every view of
# the clone must agree on (.message, args[0], str()). "empty" is the
# cross-check that the option-c message contract and the pickle state channel
# compose: "" must survive verbatim, never replaced by the generated text.
PICKLE_POSITION: int = 5
PICKLE_MESSAGE_CASES: dict[str, tuple[dict[str, str], str]] = {
    "explicit": ({"message": "boom"}, "boom"),
    "empty": ({"message": ""}, ""),
    "generated": ({}, f"Decode Error at position {PICKLE_POSITION}"),
}
