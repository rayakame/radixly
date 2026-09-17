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
"""The reference implementations against the RFC vectors and the pinned error contract."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.base64 import error_cases
from tests.reference import errors as errors_reference


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_rfc_vectors(preset: str) -> None:
    module = error_cases.PRESETS[preset]
    for payload, expected in error_cases.RFC_VECTORS.items():
        assert module.encode(payload) == expected
        assert module.decode(expected) == payload


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_high_vectors(preset: str) -> None:
    """Values 62 and 63 are where the two alphabets differ."""
    module = error_cases.PRESETS[preset]
    for payload, expected in error_cases.HIGH_VECTORS[preset].items():
        assert module.encode(payload) == expected
        assert module.decode(expected) == payload


@pytest.mark.parametrize("kind", error_cases.INVALID_KINDS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_decode_rejects_invalid_input(preset: str, kind: str) -> None:
    """Rejection pinned here so the C differential has a spec."""
    string, position = error_cases.INVALID_CASES[preset][kind]
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        error_cases.PRESETS[preset].decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@given(payload=st.binary())
def test_round_trip(preset: str, payload: bytes) -> None:
    module = error_cases.PRESETS[preset]
    assert module.decode(module.encode(payload)) == payload


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@given(payload=st.binary())
def test_encoded_length(preset: str, payload: bytes) -> None:
    assert len(error_cases.PRESETS[preset].encode(payload)) == 4 * ((len(payload) + 2) // 3)


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_alphabet_is_the_rfc_alphabet(preset: str) -> None:
    module = error_cases.PRESETS[preset]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    expected = {"base64": letters + "+/", "base64url": letters + "-_"}[preset]
    assert expected == module.ALPHABET
    assert len(set(module.ALPHABET)) == 1 << module.BITS_PER_CHAR


@given(payload=st.binary())
def test_base64url_is_base64_with_two_characters_swapped(payload: bytes) -> None:
    """RFC 4648 section 5: the same text with - for + and _ for /, padding kept."""
    base64, base64url = error_cases.PRESETS["base64"], error_cases.PRESETS["base64url"]
    assert base64url.encode(payload) == base64.encode(payload).translate(str.maketrans("+/", "-_"))
    assert not set(base64url.encode(payload)) & set("+/")


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_nonzero_pad_bits_are_one_more_spelling_the_codec_refuses(preset: str) -> None:
    """RFC 4648 section 3.5 lets a decoder reject them; the strict codec always does."""
    module = error_cases.PRESETS[preset]
    zero, one = module.ALPHABET[0], module.ALPHABET[1]
    assert module.decode(zero * 2 + "==") == b"\x00"
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        module.decode(zero + one + "==")
    assert exc_info.value.position == 1
