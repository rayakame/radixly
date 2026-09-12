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
"""Reference tests for base16: the RFC vectors, the rejection table and the alphabet."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.base16 import error_cases
from tests.reference import base16 as base16_reference
from tests.reference import errors as errors_reference


@pytest.mark.parametrize(("payload", "expected"), list(error_cases.RFC_VECTORS.items()), ids=repr)
def test_rfc_vectors(payload: bytes, expected: str) -> None:
    assert base16_reference.encode(payload) == expected
    assert base16_reference.decode(expected) == payload


@pytest.mark.parametrize(("string", "position"), error_cases.INVALID_CASES.values(), ids=error_cases.INVALID_CASES)
def test_decode_rejects_invalid_input(string: str, position: int) -> None:
    """Rejection pinned here so the C differential has a spec."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        base16_reference.decode(string)
    assert exc_info.value.position == position


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    assert base16_reference.decode(base16_reference.encode(payload)) == payload


@given(st.binary())
def test_encoded_length(payload: bytes) -> None:
    assert len(base16_reference.encode(payload)) == 2 * len(payload)


def test_alphabet_is_the_rfc_alphabet() -> None:
    assert base16_reference.ALPHABET == "0123456789ABCDEF"
    assert len(set(base16_reference.ALPHABET)) == 1 << base16_reference.BITS_PER_CHAR


def test_lowercase_is_one_more_spelling_the_codec_refuses() -> None:
    """RFC 4648 leaves case to the decoder; the strict codec keeps one spelling per payload."""
    with pytest.raises(errors_reference.DecodeError):
        base16_reference.decode("ff")
    assert base16_reference.decode("FF") == b"\xff"
