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
"""The base32 presets' codec surfaces: re-exports, Codec values, and size math."""

from __future__ import annotations

import typing

import pytest
from hypothesis import given
from hypothesis import strategies as st

import radixly.base32
import radixly.base32hex
from radixly import _core
from radixly.base32 import _api as base32_api
from radixly.base32hex import _api as base32hex_api

if typing.TYPE_CHECKING:
    from collections.abc import Callable


def test_functions_are_the_core_functions() -> None:
    """The zero-cost pin: the module attributes ARE the C functions."""
    assert radixly.base32.encode is _core.base32_encode
    assert radixly.base32.decode is _core.base32_decode
    assert radixly.base32hex.encode is _core.base32hex_encode
    assert radixly.base32hex.decode is _core.base32hex_decode


def test_base32_codec_fields() -> None:
    codec = radixly.base32.BASE32
    assert codec.encode is radixly.base32.encode
    assert codec.decode is radixly.base32.decode
    assert codec.encoded_len is radixly.base32.encoded_len
    assert codec.max_bytes is radixly.base32.max_bytes
    assert codec.name == "base32"
    assert codec.bits_per_char == 5 == radixly.base32.BITS_PER_CHAR
    assert radixly.get_codec("base32") is codec


def test_base32hex_codec_fields() -> None:
    codec = radixly.base32hex.BASE32HEX
    assert codec.encode is radixly.base32hex.encode
    assert codec.decode is radixly.base32hex.decode
    assert codec.encoded_len is radixly.base32hex.encoded_len
    assert codec.max_bytes is radixly.base32hex.max_bytes
    assert codec.name == "base32hex"
    assert codec.bits_per_char == 5 == radixly.base32hex.BITS_PER_CHAR
    assert radixly.get_codec("base32hex") is codec


def test_api_all_is_nonempty() -> None:
    assert len(base32_api.__all__) > 0
    assert len(base32hex_api.__all__) > 0


_REEXPORTS = [("base32", name) for name in base32_api.__all__] + [("base32hex", name) for name in base32hex_api.__all__]


@pytest.mark.parametrize(("codec", "name"), _REEXPORTS)
def test_package_reexports_the_api(codec: str, name: str) -> None:
    package = {"base32": radixly.base32, "base32hex": radixly.base32hex}[codec]
    api = {"base32": base32_api, "base32hex": base32hex_api}[codec]
    assert getattr(package, name) is getattr(api, name)


_SIZE_MATH: dict[str, tuple[Callable[[int], int], Callable[[int], int]]] = {
    "base32": (radixly.base32.encoded_len, radixly.base32.max_bytes),
    "base32hex": (radixly.base32hex.encoded_len, radixly.base32hex.max_bytes),
}
_ENCODE = {"base32": radixly.base32.encode, "base32hex": radixly.base32hex.encode}


@pytest.mark.parametrize("codec", _SIZE_MATH)
@given(payload=st.binary())
def test_encoded_len_matches_encode(codec: str, payload: bytes) -> None:
    encoded_len, _ = _SIZE_MATH[codec]
    assert encoded_len(len(payload)) == len(_ENCODE[codec](payload))


@pytest.mark.parametrize("n", range(1000))
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_max_bytes_is_maximal(codec: str, n: int) -> None:
    """max_bytes(n) fits in n characters; one more byte would not, because padding fills every group."""
    encoded_len, max_bytes = _SIZE_MATH[codec]
    assert encoded_len(max_bytes(n)) <= n < encoded_len(max_bytes(n) + 1)


@pytest.mark.parametrize(("num_bytes", "expected"), [(0, 0), (1, 8), (5, 8), (6, 16), (10, 16), (60, 96)])
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_encoded_len_pins(codec: str, num_bytes: int, expected: int) -> None:
    assert _SIZE_MATH[codec][0](num_bytes) == expected


@pytest.mark.parametrize(("num_chars", "expected"), [(0, 0), (7, 0), (8, 5), (15, 5), (100, 60)])
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_max_bytes_pins(codec: str, num_chars: int, expected: int) -> None:
    """Only whole groups of eight count: 100 characters hold 60 bytes, the four leftovers nothing."""
    assert _SIZE_MATH[codec][1](num_chars) == expected


@pytest.mark.parametrize(
    "func",
    [radixly.base32.encoded_len, radixly.base32.max_bytes, radixly.base32hex.encoded_len, radixly.base32hex.max_bytes],
)
@pytest.mark.parametrize("bad", [-1, -(10**9)])
def test_negative_input_rejected(func: Callable[[int], int], bad: int) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        func(bad)
