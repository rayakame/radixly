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
"""The base64 error contract as data: the RFC vectors and every rejection shape with its position."""

from __future__ import annotations

import typing

from tests.reference import base64
from tests.reference import base64url

if typing.TYPE_CHECKING:
    from collections.abc import Callable

__all__ = (
    "FOREIGN_CHARS",
    "HIGH_VECTORS",
    "INVALID_CASES",
    "INVALID_KINDS",
    "NON_STR_INPUTS",
    "PRESETS",
    "RFC_VECTORS",
    "Base64Preset",
)


class Base64Preset(typing.Protocol):
    """The shape both preset reference modules share."""

    @property
    def ALPHABET(self) -> str: ...  # ruff: ignore[invalid-function-name]
    @property
    def BITS_PER_CHAR(self) -> int: ...  # ruff: ignore[invalid-function-name]
    @property
    def encode(self) -> Callable[[bytes], str]: ...
    @property
    def decode(self) -> Callable[[str], bytes]: ...


PRESETS: dict[str, Base64Preset] = {"base64": base64, "base64url": base64url}

# The two characters of the other preset's alphabet, which this one refuses.
FOREIGN_CHARS: dict[str, str] = {"base64": "-_", "base64url": "+/"}

# RFC 4648 section 10; the vectors never reach values 62 and 63, so both presets share them.
RFC_VECTORS: dict[bytes, str] = {
    b"": "",
    b"f": "Zg==",
    b"fo": "Zm8=",
    b"foo": "Zm9v",
    b"foob": "Zm9vYg==",
    b"fooba": "Zm9vYmE=",
    b"foobar": "Zm9vYmFy",
}

# Values 62 and 63 in every position, where the alphabets differ.
HIGH_VECTORS: dict[str, dict[bytes, str]] = {
    "base64": {b"\xfb\xff\xbf": "+/+/", b"\xff\xef\xfe": "/+/+", b"\xfb\xff": "+/8=", b"\xfb": "+w=="},
    "base64url": {b"\xfb\xff\xbf": "-_-_", b"\xff\xef\xfe": "_-_-", b"\xfb\xff": "-_8=", b"\xfb": "-w=="},
}


def _invalid_cases(module: Base64Preset, foreign: str) -> dict[str, tuple[str, int]]:
    """Every rejection shape, spelled with the preset's first two characters (values 0 and 1)."""
    zero, one = module.ALPHABET[0], module.ALPHABET[1]
    full = zero * 4  # three zero bytes
    return {
        "other-alphabet": (foreign[0] + zero * 3, 0),
        "other-alphabet-last": (zero * 3 + foreign[1], 3),
        "space": (zero * 2 + " " + zero, 2),
        "newline-at-end": (full + "\n", 4),
        "astral": ("\U0001f600", 0),
        "lone-surrogate": ("\ud800", 0),
        "astral-mid-string": (full + "\U0001f600" + zero * 3, 4),
        "invalid-after-full-group": (full + "!" + zero * 3, 4),
        "padding-before-another-group": (zero * 2 + "==" + full, 2),
        "padding-before-a-remainder": (zero * 2 + "==" + zero, 2),
        "pad-bits-in-a-non-last-group": (zero + one + "==" + full, 2),
        "data-after-padding": (zero * 2 + "=" + zero, 3),
        "one-data-character": (zero + "===", 1),
        "all-padding": ("====", 0),
        "pad-bits-two-chars": (zero + one + "==", 1),
        "pad-bits-three-chars": (zero * 2 + one + "=", 2),
        "short-length": (zero * 3, 3),
        "short-length-invalid-wins": (zero * 2 + "!", 2),
        "short-length-with-padding": (zero * 2 + "=", 2),
        "short-second-group": (full + zero * 2, 6),
        "padding-after-full-groups": (full + "=", 4),
    }


INVALID_CASES: dict[str, dict[str, tuple[str, int]]] = {
    name: _invalid_cases(module, FOREIGN_CHARS[name]) for name, module in PRESETS.items()
}
INVALID_KINDS = tuple(INVALID_CASES["base64"])  # identical keys for every preset

NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)
