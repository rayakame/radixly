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
"""The reference implementations against the known vectors and the pinned error contract."""

from __future__ import annotations

import base64
import math
import sys

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.base85 import error_cases
from tests.reference import errors as errors_reference


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_vectors(preset: str) -> None:
    module = error_cases.PRESETS[preset]
    for payload, expected in error_cases.VECTORS[preset].items():
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
    tail = len(payload) % 4
    assert len(error_cases.PRESETS[preset].encode(payload)) == 5 * (len(payload) // 4) + (tail + 1 if tail else 0)


@given(payload=st.binary())
def test_base85_is_the_stdlib_text(payload: bytes) -> None:
    """The encoders produce b85encode's and z85encode's bytes, as str."""
    assert error_cases.PRESETS["base85"].encode(payload) == base64.b85encode(payload).decode("ascii")
    if sys.version_info >= (3, 13):
        z85encode = base64.z85encode  # pyright: ignore[reportUnreachable]
        assert error_cases.PRESETS["z85"].encode(payload) == z85encode(payload).decode("ascii")


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_alphabet_has_85_distinct_ascii_characters(preset: str) -> None:
    module = error_cases.PRESETS[preset]
    assert len(module.ALPHABET) == len(set(module.ALPHABET)) == 85
    assert module.ALPHABET.isascii()
    assert math.isclose(module.BITS_PER_CHAR, 32 / 5)


def test_z85_excludes_selected_escaping_characters() -> None:
    """ZeroMQ left out both quotes, backslash, comma, semicolon, underscore, backquote, pipe, tilde and space."""
    assert not set(error_cases.PRESETS["z85"].ALPHABET) & set("\"'\\,;_`|~ ")


def _decode_or_position(module: error_cases.Base85Preset, string: str) -> bytes | int:
    try:
        return module.decode(string)
    except errors_reference.DecodeError as error:
        return error.position


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_one_tail_spelling_per_payload(preset: str) -> None:
    """Closing a tail with another digit is either refused or another payload's one spelling, never a second one."""
    module = error_cases.PRESETS[preset]
    for payload in (b"h", b"hi", b"hi!", b"\xff", b"\xff\xff", b"\xff\xff\xff", b"\x00", b"\x00\x00\x00"):
        text = module.encode(payload)
        assert module.decode(text) == payload
        seen = {payload}
        for last in module.ALPHABET:
            other = text[:-1] + last
            if other == text:
                continue
            outcome = _decode_or_position(module, other)
            if isinstance(outcome, int):
                assert outcome == len(other) - 1
                continue
            assert outcome not in seen
            seen.add(outcome)
            assert module.encode(outcome) == other
