"""Fuzz the C decoder against the oracle over hostile input spaces.

Fuzzing here is property-based testing with a differential twist: for garbage
input there is no expected output, so the property is full parity — C and the
reference must return the same bytes, or both must reject with a DecodeError
at the same position. A segfault, hang (Hypothesis's per-example deadline is
the tripwire — never disable it here), or wrong exception type all fail the
parity automatically. Found failures shrink to minimal examples and persist
in .hypothesis/ to be replayed first on every future run.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from radixly import _core
from tests.reference import base32768 as base32768_reference
from tests.reference import errors as errors_reference


def _assert_parity(string: str) -> bytes | None:
    """C and the oracle must agree exactly; returns the payload on accept."""
    try:
        expected = base32768_reference.decode(string)
    except errors_reference.DecodeError as reference_error:
        expected_position = reference_error.position
    else:
        result = _core.base32768_decode(string)
        assert result == expected
        return result
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base32768_decode(string)
    assert exc_info.value.position == expected_position
    return None


def _join_chars(code_points: list[int]) -> str:
    return "".join(chr(code_point) for code_point in code_points)


# Shape A: strings built from raw code points, because st.text()'s polite
# default alphabet never generates the lone surrogates we most want (the
# inputs that rely on the 2,048 painted sentinel cells). Full-range adds
# astral characters for the bounds guard.
BMP_STRINGS = st.lists(st.integers(min_value=0, max_value=0xFFFF)).map(_join_chars)
FULL_RANGE_STRINGS = st.lists(st.integers(min_value=0, max_value=0x10FFFF)).map(_join_chars)


@given(BMP_STRINGS)
def test_fuzz_bmp_strings(string: str) -> None:
    _assert_parity(string)


@given(FULL_RANGE_STRINGS)
def test_fuzz_full_range_strings(string: str) -> None:
    _assert_parity(string)


# Shape B: corruption fuzz. Random strings die at index 0 on the first
# invalid character; strings that are one mutation away from a valid encoding
# reach the deep rejections instead — misplaced 7-bit, canonicality, padding.
# The mutation pool is alphabet-biased for exactly that reason: an alphabet
# character in the wrong place makes plausible-but-wrong input, where decoder
# bugs actually live. A mutated string may also still be valid; parity covers
# both outcomes.
_ALPHABET: str = "".join(base32768_reference.LOOKUP_D)
# one_of, not one flat pool: sampled_from draws uniformly, and 4 hostile
# characters against ~32,896 alphabet ones would be lottery odds -- chosen
# once per ~8,000 draws, i.e. effectively never at 500 examples. Branching
# gives the hostile set real representation, and shrinking works through it.
_MUTATION_POOL = st.one_of(
    st.sampled_from(_ALPHABET),
    st.sampled_from("A\x00\ud800\U0001f600"),
)


@st.composite
def _corrupted_encodings(draw: st.DrawFn) -> str:
    encoded = base32768_reference.encode(draw(st.binary()))
    mutation = draw(st.sampled_from(["replace", "insert", "delete", "truncate"]))
    if mutation == "insert":
        position = draw(st.integers(min_value=0, max_value=len(encoded)))
        return encoded[:position] + draw(_MUTATION_POOL) + encoded[position:]
    if not encoded:
        return draw(_MUTATION_POOL)  # nothing to mutate in place; a 1-char probe
    position = draw(st.integers(min_value=0, max_value=len(encoded) - 1))
    if mutation == "replace":
        return encoded[:position] + draw(_MUTATION_POOL) + encoded[position + 1 :]
    if mutation == "delete":
        return encoded[:position] + encoded[position + 1 :]
    return encoded[:position]  # truncate


@settings(max_examples=500)
@given(_corrupted_encodings())
def test_fuzz_corrupted_encodings(string: str) -> None:
    _assert_parity(string)


# Shape C: not Hypothesis — the one exhaustive statement in the suite.


def test_every_single_character_agrees() -> None:
    """Interrogates every reverse-table cell, forever: all 65,536 one-character
    strings, C vs oracle. Exactly 256 decode (the 15-bit characters whose low
    7 bits are all ones — canonical padding); pinning the count is a bonus
    invariant on the alphabet's structure."""
    accepted = sum(1 for code_point in range(0x10000) if _assert_parity(chr(code_point)) is not None)
    assert accepted == 256


def test_multi_megabyte_hostile_tail() -> None:
    """The charter's last unticked fuzz box: multi-MB hostile input.

    Hypothesis keeps examples small by design and the megabyte differentials
    are all-valid, so this one is deterministic: a hostile character at the
    end of a multi-megabyte valid encoding must be rejected at the correct
    large index on both sides — pinning that pass 1 reports positions
    correctly deep into big inputs. The payload length is a multiple of 15 so
    the valid encoding has no 7-bit final character; otherwise the
    misplaced-7-bit check would fire one index earlier than the hostile char.
    """
    payload = random.Random(3_000_000).randbytes(3_000_000)
    corrupted = base32768_reference.encode(payload) + "\ud800"
    hostile_index = len(corrupted) - 1
    assert hostile_index == 1_600_000  # 8 * 3e6 / 15: the length math, pinned
    with pytest.raises(_core.DecodeError) as c_info:
        _core.base32768_decode(corrupted)
    with pytest.raises(errors_reference.DecodeError) as reference_info:
        base32768_reference.decode(corrupted)
    assert (c_info.value.position, reference_info.value.position) == (hostile_index, hostile_index)
