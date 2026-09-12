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
"""Shared rejection tables for the base32 presets: the same shapes in both alphabets, positions pinned by hand."""

from __future__ import annotations

import typing

from tests.reference import base32
from tests.reference import base32hex

if typing.TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ("INVALID_CASES", "INVALID_KINDS", "NON_STR_INPUTS", "PRESETS", "RFC_VECTORS", "Base32Preset")


class Base32Preset(typing.Protocol):
    """The shape both preset reference modules share."""

    @property
    def ALPHABET(self) -> str: ...  # ruff: ignore[invalid-function-name]
    @property
    def BITS_PER_CHAR(self) -> int: ...  # ruff: ignore[invalid-function-name]
    @property
    def encode(self) -> Callable[[bytes], str]: ...
    @property
    def decode(self) -> Callable[[str], bytes]: ...


PRESETS: dict[str, Base32Preset] = {"base32": base32, "base32hex": base32hex}

# RFC 4648 section 10.
RFC_VECTORS: dict[str, dict[bytes, str]] = {
    "base32": {
        b"": "",
        b"f": "MY======",
        b"fo": "MZXQ====",
        b"foo": "MZXW6===",
        b"foob": "MZXW6YQ=",
        b"fooba": "MZXW6YTB",
        b"foobar": "MZXW6YTBOI======",
    },
    "base32hex": {
        b"": "",
        b"f": "CO======",
        b"fo": "CPNG====",
        b"foo": "CPNMU===",
        b"foob": "CPNMUOG=",
        b"fooba": "CPNMUOJ1",
        b"foobar": "CPNMUOJ1E8======",
    },
}


def _invalid_cases(module: Base32Preset) -> dict[str, tuple[str, int]]:
    """Every rejection shape, spelled with the preset's first two characters (values 0 and 1)."""
    zero, one = module.ALPHABET[0], module.ALPHABET[1]
    full = zero * 8  # five zero bytes
    return {
        "lowercase": (module.ALPHABET[10].lower() + zero * 7, 0),
        "space": (zero * 4 + " " + zero * 3, 4),
        "astral": ("\U0001f600", 0),
        "lone-surrogate": ("\ud800", 0),
        "astral-mid-string": (full + "\U0001f600" + zero * 7, 8),
        "invalid-after-full-group": (full + "!" + zero * 7, 8),
        "padding-before-another-group": (zero * 2 + "======" + full, 2),
        "data-after-padding": (zero * 2 + "==" + zero * 4, 4),
        "one-data-character": (zero + "=======", 1),
        "three-data-characters": (zero * 3 + "=====", 3),
        "six-data-characters": (zero * 6 + "==", 6),
        "all-padding": ("========", 0),
        "pad-bits-two-chars": (zero + one + "======", 1),
        "pad-bits-four-chars": (zero * 3 + one + "====", 3),
        "pad-bits-five-chars": (zero * 4 + one + "===", 4),
        "pad-bits-seven-chars": (zero * 6 + one + "=", 6),
        "short-length": (zero * 7, 7),
        "short-length-invalid-wins": (zero * 3 + "!", 3),
        "short-length-with-padding": (zero * 2 + "==", 2),
        "short-second-group": (full + zero * 3, 11),
    }


INVALID_CASES: dict[str, dict[str, tuple[str, int]]] = {
    name: _invalid_cases(module) for name, module in PRESETS.items()
}
INVALID_KINDS = tuple(INVALID_CASES["base32"])  # identical keys for every preset

NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)
