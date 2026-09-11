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
"""The codec surface: re-exports, the Codec value, and the length math."""

from __future__ import annotations

import typing

import pytest
from hypothesis import given
from hypothesis import strategies as st

import radixly.base32768
from radixly import _core
from radixly.base32768 import _api

if typing.TYPE_CHECKING:
    from collections.abc import Callable


def test_functions_are_the_core_functions() -> None:
    """The zero-cost pin: the module attributes ARE the C functions."""
    assert radixly.base32768.encode is _core.base32768_encode
    assert radixly.base32768.decode is _core.base32768_decode


def test_codec_fields() -> None:
    codec = radixly.base32768.BASE32768
    assert codec.encode is radixly.base32768.encode
    assert codec.decode is radixly.base32768.decode
    assert codec.encoded_len is radixly.base32768.encoded_len
    assert codec.max_bytes is radixly.base32768.max_bytes
    assert codec.name == "base32768"
    assert codec.bits_per_char == 15 == radixly.base32768.BITS_PER_CHAR


def test_api_all_is_nonempty() -> None:
    """Make an emptied __all__ loud.

    It would make the re-export parametrization collect zero cases and skip,
    green while guarding nothing.
    """
    assert len(_api.__all__) > 0


@pytest.mark.parametrize("name", _api.__all__)
def test_package_reexports_the_api(name: str) -> None:
    assert getattr(radixly.base32768, name) is getattr(_api, name)


@given(st.binary())
def test_encoded_len_matches_encode(payload: bytes) -> None:
    assert radixly.base32768.encoded_len(len(payload)) == len(radixly.base32768.encode(payload))


@pytest.mark.parametrize("n", range(1000))
def test_max_bytes_is_maximal(n: int) -> None:
    """max_bytes(n) fits in n characters; one more byte would not."""
    assert radixly.base32768.encoded_len(radixly.base32768.max_bytes(n)) <= n
    assert n < radixly.base32768.encoded_len(radixly.base32768.max_bytes(n) + 1)


@pytest.mark.parametrize(("num_bytes", "expected"), [(0, 0), (1, 1), (15, 8), (187, 100)])
def test_encoded_len_pins(num_bytes: int, expected: int) -> None:
    assert radixly.base32768.encoded_len(num_bytes) == expected


@pytest.mark.parametrize(("num_chars", "expected"), [(0, 0), (1, 1), (8, 15), (100, 187)])
def test_max_bytes_pins(num_chars: int, expected: int) -> None:
    assert radixly.base32768.max_bytes(num_chars) == expected


@pytest.mark.parametrize("func", [radixly.base32768.encoded_len, radixly.base32768.max_bytes])
@pytest.mark.parametrize("bad", [-1, -(10**9)])
def test_negative_input_rejected(func: Callable[[int], int], bad: int) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        func(bad)
