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

import radixly.base85
import radixly.z85
from radixly import _core
from radixly.base85 import _api as base85_api
from radixly.z85 import _api as z85_api

if typing.TYPE_CHECKING:
    from collections.abc import Callable


def test_functions_are_the_core_functions() -> None:
    """The zero-cost pin: the module attributes ARE the C functions."""
    assert radixly.base85.encode is _core.base85_encode
    assert radixly.base85.decode is _core.base85_decode
    assert radixly.z85.encode is _core.z85_encode
    assert radixly.z85.decode is _core.z85_decode


def test_base85_codec_fields() -> None:
    codec = radixly.base85.BASE85
    assert codec.encode is radixly.base85.encode
    assert codec.decode is radixly.base85.decode
    assert codec.encoded_len is radixly.base85.encoded_len
    assert codec.max_bytes is radixly.base85.max_bytes
    assert codec.name == "base85"
    assert codec.bits_per_char == radixly.base85.BITS_PER_CHAR == pytest.approx(32 / 5)
    assert radixly.get_codec("base85") is codec


def test_z85_codec_fields() -> None:
    codec = radixly.z85.Z85
    assert codec.encode is radixly.z85.encode
    assert codec.decode is radixly.z85.decode
    assert codec.encoded_len is radixly.z85.encoded_len
    assert codec.max_bytes is radixly.z85.max_bytes
    assert codec.name == "z85"
    assert codec.bits_per_char == radixly.z85.BITS_PER_CHAR == pytest.approx(32 / 5)
    assert radixly.get_codec("z85") is codec


def test_api_all_is_nonempty() -> None:
    assert len(base85_api.__all__) > 0
    assert len(z85_api.__all__) > 0
    assert set(_SIZE_MATH) == {"base85", "z85"} == set(_ENCODE)


_REEXPORTS = [("base85", name) for name in base85_api.__all__] + [("z85", name) for name in z85_api.__all__]


@pytest.mark.parametrize(("codec", "name"), _REEXPORTS)
def test_package_reexports_the_api(codec: str, name: str) -> None:
    package = {"base85": radixly.base85, "z85": radixly.z85}[codec]
    api = {"base85": base85_api, "z85": z85_api}[codec]
    assert getattr(package, name) is getattr(api, name)


_SIZE_MATH: dict[str, tuple[Callable[[int], int], Callable[[int], int]]] = {
    "base85": (radixly.base85.encoded_len, radixly.base85.max_bytes),
    "z85": (radixly.z85.encoded_len, radixly.z85.max_bytes),
}
_ENCODE = {"base85": radixly.base85.encode, "z85": radixly.z85.encode}


@pytest.mark.parametrize("codec", _SIZE_MATH)
@given(payload=st.binary())
def test_encoded_len_matches_encode(codec: str, payload: bytes) -> None:
    encoded_len, _ = _SIZE_MATH[codec]
    assert encoded_len(len(payload)) == len(_ENCODE[codec](payload))


@pytest.mark.parametrize("n", range(1000))
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_max_bytes_is_maximal(codec: str, n: int) -> None:
    """max_bytes(n) fits in n characters; one more byte would not."""
    encoded_len, max_bytes = _SIZE_MATH[codec]
    assert encoded_len(max_bytes(n)) <= n < encoded_len(max_bytes(n) + 1)


@pytest.mark.parametrize(
    ("num_bytes", "expected"), [(0, 0), (1, 2), (2, 3), (3, 4), (4, 5), (5, 7), (10, 13), (80, 100)]
)
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_encoded_len_pins(codec: str, num_bytes: int, expected: int) -> None:
    assert _SIZE_MATH[codec][0](num_bytes) == expected


@pytest.mark.parametrize(("num_chars", "expected"), [(0, 0), (1, 0), (2, 1), (4, 3), (5, 4), (6, 4), (7, 5), (100, 80)])
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_max_bytes_pins(codec: str, num_chars: int, expected: int) -> None:
    """A sixth character carries nothing on its own; the seventh with it carries a byte."""
    assert _SIZE_MATH[codec][1](num_chars) == expected


@pytest.mark.parametrize(
    "func",
    [radixly.base85.encoded_len, radixly.base85.max_bytes, radixly.z85.encoded_len, radixly.z85.max_bytes],
)
@pytest.mark.parametrize("bad", [-1, -(10**9)])
def test_negative_input_rejected(func: Callable[[int], int], bad: int) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        func(bad)
