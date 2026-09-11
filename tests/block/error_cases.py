# Copyright (c) 2026-present rayakame
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Shared rejection tables for the block presets: same (input, position) on both sides."""

from __future__ import annotations

import typing

from tests.reference import braille
from tests.reference import hexagram

if typing.TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ("HEXAGRAM_REJECTIONS", "INVALID_CASES", "INVALID_KINDS", "PRESETS", "BlockPreset")


class BlockPreset(typing.Protocol):
    """The shape both preset reference modules share."""

    @property
    def START(self) -> int: ...  # ruff: ignore[invalid-function-name]
    @property
    def BITS_PER_CHAR(self) -> int: ...  # ruff: ignore[invalid-function-name]
    @property
    def encode(self) -> Callable[[bytes], str]: ...
    @property
    def decode(self) -> Callable[[str], bytes]: ...


PRESETS: dict[str, BlockPreset] = {"braille": braille, "hexagram": hexagram}


def _invalid_cases(module: BlockPreset) -> dict[str, tuple[str, int]]:
    """Each hostile kind alone (position 0) and buried mid-string (its index)."""
    prefix = module.encode(bytes(3))  # 24 bits: full characters in both presets
    bad_chars = {
        "below-block": chr(module.START - 1),
        "above-block": chr(module.START + (1 << module.BITS_PER_CHAR)),
        "astral": "\U0001f600",
        "lone-surrogate": "\ud800",
    }
    cases: dict[str, tuple[str, int]] = {}
    for kind, bad in bad_chars.items():
        cases[kind] = (bad, 0)
        cases[f"{kind}-mid-string"] = (prefix + bad + prefix, len(prefix))
    return cases


INVALID_CASES: dict[str, dict[str, tuple[str, int]]] = {
    name: _invalid_cases(module) for name, module in PRESETS.items()
}
INVALID_KINDS = tuple(INVALID_CASES["braille"])  # identical keys for every preset

# Hexagram-only: n % 4 == 1 leaves 6 padding bits, a zero-payload final char; filler and zeroed padding likewise.
HEXAGRAM_REJECTIONS: dict[str, tuple[str, int]] = {
    "lone-filler": ("䷿", 0),
    "five-fillers": ("䷿" * 5, 4),
    "nine-fillers": ("䷿" * 9, 8),
    "appended-filler": (hexagram.encode(bytes(3)) + "䷿", 4),
    "zeroed-padding": ("䷀䷀", 1),  # b"\x00" encodes to U+4DC0 U+4DCF; pad ones zeroed
}
