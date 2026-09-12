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
"""Reference tests for the base32 presets: RFC vectors, rejection tables, alphabets."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.base32 import error_cases
from tests.reference import errors as errors_reference


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_rfc_vectors(preset: str) -> None:
    module = error_cases.PRESETS[preset]
    for payload, expected in error_cases.RFC_VECTORS[preset].items():
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
    assert len(error_cases.PRESETS[preset].encode(payload)) == 8 * ((len(payload) + 4) // 5)


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_alphabet_is_the_rfc_alphabet(preset: str) -> None:
    module = error_cases.PRESETS[preset]
    expected = {"base32": "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", "base32hex": "0123456789ABCDEFGHIJKLMNOPQRSTUV"}[preset]
    assert expected == module.ALPHABET
    assert len(set(module.ALPHABET)) == 1 << module.BITS_PER_CHAR


def test_base32hex_preserves_byte_order() -> None:
    """RFC 4648 section 7: payloads of one length, and unpadded text of any length, sort in byte order."""
    module = error_cases.PRESETS["base32hex"]
    same_length = sorted(bytes([a, b]) for a in range(0, 256, 17) for b in range(0, 256, 51))
    assert sorted(same_length, key=module.encode) == same_length
    mixed = sorted([b"", b"\x00", b"\x00\x00", b"\x00\x80", b"\x01", b"\x01\x00\x00\x00\x00\x00", b"\xff"])
    assert sorted(mixed, key=lambda payload: module.encode(payload).rstrip("=")) == mixed
    assert sorted(mixed, key=module.encode) != mixed  # the pad character sorts between 9 and A


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_nonzero_pad_bits_are_one_more_spelling_the_codec_refuses(preset: str) -> None:
    """RFC 4648 section 3.5 lets a decoder reject them; the strict codec always does."""
    module = error_cases.PRESETS[preset]
    zero, one = module.ALPHABET[0], module.ALPHABET[1]
    assert module.decode(zero * 2 + "======") == b"\x00"
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        module.decode(zero + one + "======")
    assert exc_info.value.position == 1
