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
"""The Python faces: the C functions bound as-is, the codec values, the size math."""

from __future__ import annotations

import typing

import pytest
from hypothesis import given
from hypothesis import strategies as st

import radixly.base64
import radixly.base64url
from radixly import _core
from radixly.base64 import _api as base64_api
from radixly.base64url import _api as base64url_api

if typing.TYPE_CHECKING:
    from collections.abc import Callable


def test_functions_are_the_core_functions() -> None:
    """The zero-cost pin: the module attributes ARE the C functions."""
    assert radixly.base64.encode is _core.base64_encode
    assert radixly.base64.decode is _core.base64_decode
    assert radixly.base64url.encode is _core.base64url_encode
    assert radixly.base64url.decode is _core.base64url_decode


def test_base64_codec_fields() -> None:
    codec = radixly.base64.BASE64
    assert codec.encode is radixly.base64.encode
    assert codec.decode is radixly.base64.decode
    assert codec.encoded_len is radixly.base64.encoded_len
    assert codec.max_bytes is radixly.base64.max_bytes
    assert codec.name == "base64"
    assert codec.bits_per_char == 6 == radixly.base64.BITS_PER_CHAR
    assert radixly.get_codec("base64") is codec


def test_base64url_codec_fields() -> None:
    codec = radixly.base64url.BASE64URL
    assert codec.encode is radixly.base64url.encode
    assert codec.decode is radixly.base64url.decode
    assert codec.encoded_len is radixly.base64url.encoded_len
    assert codec.max_bytes is radixly.base64url.max_bytes
    assert codec.name == "base64url"
    assert codec.bits_per_char == 6 == radixly.base64url.BITS_PER_CHAR
    assert radixly.get_codec("base64url") is codec


def test_api_all_is_nonempty() -> None:
    assert len(base64_api.__all__) > 0
    assert len(base64url_api.__all__) > 0
    assert set(_SIZE_MATH) == {"base64", "base64url"} == set(_ENCODE)


_REEXPORTS = [("base64", name) for name in base64_api.__all__] + [("base64url", name) for name in base64url_api.__all__]


@pytest.mark.parametrize(("codec", "name"), _REEXPORTS)
def test_package_reexports_the_api(codec: str, name: str) -> None:
    package = {"base64": radixly.base64, "base64url": radixly.base64url}[codec]
    api = {"base64": base64_api, "base64url": base64url_api}[codec]
    assert getattr(package, name) is getattr(api, name)


_SIZE_MATH: dict[str, tuple[Callable[[int], int], Callable[[int], int]]] = {
    "base64": (radixly.base64.encoded_len, radixly.base64.max_bytes),
    "base64url": (radixly.base64url.encoded_len, radixly.base64url.max_bytes),
}
_ENCODE = {"base64": radixly.base64.encode, "base64url": radixly.base64url.encode}


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


@pytest.mark.parametrize(("num_bytes", "expected"), [(0, 0), (1, 4), (3, 4), (4, 8), (10, 16), (75, 100)])
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_encoded_len_pins(codec: str, num_bytes: int, expected: int) -> None:
    assert _SIZE_MATH[codec][0](num_bytes) == expected


@pytest.mark.parametrize(("num_chars", "expected"), [(0, 0), (3, 0), (4, 3), (7, 3), (100, 75)])
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_max_bytes_pins(codec: str, num_chars: int, expected: int) -> None:
    """Only whole groups of four count: 100 characters hold 75 bytes, nothing is left over."""
    assert _SIZE_MATH[codec][1](num_chars) == expected


@pytest.mark.parametrize(
    "func",
    [radixly.base64.encoded_len, radixly.base64.max_bytes, radixly.base64url.encoded_len, radixly.base64url.max_bytes],
)
@pytest.mark.parametrize("bad", [-1, -(10**9)])
def test_negative_input_rejected(func: Callable[[int], int], bad: int) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        func(bad)
