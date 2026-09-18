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
"""The base85 error contract as data: known vectors and every rejection shape with its position."""

from __future__ import annotations

import typing

from tests.reference import base85
from tests.reference import z85

if typing.TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ("FOREIGN_CHARS", "INVALID_CASES", "INVALID_KINDS", "NON_STR_INPUTS", "PRESETS", "VECTORS", "Base85Preset")


class Base85Preset(typing.Protocol):
    """The shape both preset reference modules share."""

    @property
    def ALPHABET(self) -> str: ...  # ruff: ignore[invalid-function-name]
    @property
    def BITS_PER_CHAR(self) -> float: ...  # ruff: ignore[invalid-function-name]
    @property
    def encode(self) -> Callable[[bytes], str]: ...
    @property
    def decode(self) -> Callable[[str], bytes]: ...


PRESETS: dict[str, Base85Preset] = {"base85": base85, "z85": z85}

# Characters of the other alphabet only, which this one refuses.
FOREIGN_CHARS: dict[str, str] = {"base85": "./:[]", "z85": ";_`|~"}

# The standard library's own output (Lib/test/test_base64.py and ZeroMQ's RFC 32 example), both directions.
VECTORS: dict[str, dict[bytes, str]] = {
    "base85": {
        b"": "",
        b"www.python.org": "cXxL#aCvlSZ*DGca%T",
        b"\x00": "00",
        b"\x00\x00": "000",
        b"\x00\x00\x00": "0000",
        b"\x00\x00\x00\x00": "00000",
        b"\xff\xff\xff\xff": "|NsC0",
        bytes(range(12)): "009C61O)~M2nh-c",
    },
    "z85": {
        b"": "",
        b"www.python.org": "CxXl-AcVLsz/dgCA+t",
        b"\x86\x4f\xd2\x6f\xb5\x59\xf7\x5b": "HelloWorld",
        b"\x00": "00",
        b"\xff\xff\xff\xff": "%nSc0",
    },
}


def _invalid_cases(module: Base85Preset, foreign: str) -> dict[str, tuple[str, int]]:
    """Every rejection shape, spelled with the preset's own digits."""
    zero, top = module.ALPHABET[0], module.ALPHABET[84]
    full = zero * 5  # four zero bytes
    one_byte = module.encode(b"h")  # two characters
    return {
        "other-alphabet": (foreign[0] + zero * 4, 0),
        "other-alphabet-last": (zero * 4 + foreign[-1], 4),
        "space": (zero * 2 + " " + zero * 2, 2),
        "newline-between-groups": (full + "\n" + full, 5),
        "astral": ("\U0001f600", 0),
        "lone-surrogate": ("\ud800", 0),
        "astral-mid-string": (full + "\U0001f600" + zero * 4, 5),
        "invalid-after-full-group": (full + "!" + zero * 4, 5)
        if "!" not in module.ALPHABET
        else (full + '"' + zero * 4, 5),
        "one-character-tail": (zero, 0),
        "one-character-tail-after-group": (full + zero, 5),
        "one-character-tail-invalid-wins": (full + "\x00", 5),
        "group-over-32-bits": (top * 5, 4),
        "group-over-32-bits-later": (full + top * 5, 9),
        "tail-over-32-bits": (top * 2, 1),
        "tail-not-the-encoder-spelling": (one_byte[0] + module.ALPHABET[module.ALPHABET.index(one_byte[1]) + 1], 1),
        "tail-with-dropped-bytes-set": (module.encode(b"hi!")[:2] + zero * 2, 3),
        "three-character-tail-off-by-one": (module.encode(b"hi")[:2] + module.ALPHABET[1], 2),
        "tail-after-group-not-the-encoder-spelling": (full + module.encode(b"\xff")[0] + top, 6),
    }


INVALID_CASES: dict[str, dict[str, tuple[str, int]]] = {
    name: _invalid_cases(module, FOREIGN_CHARS[name]) for name, module in PRESETS.items()
}
INVALID_KINDS = tuple(INVALID_CASES["base85"])  # identical keys for every preset

NON_STR_INPUTS: tuple[object, ...] = (b"bytes", 42)
