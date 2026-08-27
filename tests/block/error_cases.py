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

# Hexagram-only: 6n bits at n % 4 == 1 leave 6 padding bits (zero-payload final
# char), an appended filler is the same sin, and zeroed padding is corruption.
HEXAGRAM_REJECTIONS: dict[str, tuple[str, int]] = {
    "lone-filler": ("䷿", 0),
    "five-fillers": ("䷿" * 5, 4),
    "nine-fillers": ("䷿" * 9, 8),
    "appended-filler": (hexagram.encode(bytes(3)) + "䷿", 4),
    "zeroed-padding": ("䷀䷀", 1),  # b"\x00" encodes to U+4DC0 U+4DCF; pad ones zeroed
}
