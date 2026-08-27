"""Differential tests: the block-preset C functions against their reference oracles."""

from __future__ import annotations

import random
import typing

import pytest
from hypothesis import given
from hypothesis import strategies as st

from radixly import _core
from tests.base32768.test_core import PAYLOAD_FLAVORS
from tests.block import error_cases
from tests.reference import errors as errors_reference

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from _typeshed import ReadableBuffer

C_ENCODE: dict[str, Callable[[ReadableBuffer], str]] = {
    "braille": _core.braille_encode,
    "hexagram": _core.hexagram_encode,
}
C_DECODE: dict[str, Callable[[str], bytes]] = {
    "braille": _core.braille_decode,
    "hexagram": _core.hexagram_decode,
}


def _assert_parity(preset: str, string: str) -> bytes | None:
    """C and the oracle must agree exactly; returns the payload on accept."""
    try:
        expected = error_cases.PRESETS[preset].decode(string)
    except errors_reference.DecodeError as reference_error:
        expected_position = reference_error.position
    else:
        result = C_DECODE[preset](string)
        assert result == expected
        return result
    with pytest.raises(_core.DecodeError) as exc_info:
        C_DECODE[preset](string)
    assert exc_info.value.position == expected_position
    return None


# Cross-differentials: every arrow between the implementations tested independently.


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_encode_matches_reference_every_length(preset: str, flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert C_ENCODE[preset](payload) == error_cases.PRESETS[preset].encode(payload)


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_decode_inverts_reference_encode(preset: str, flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert C_DECODE[preset](error_cases.PRESETS[preset].encode(payload)) == payload


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_reference_decode_inverts_encode(preset: str, flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert error_cases.PRESETS[preset].decode(C_ENCODE[preset](payload)) == payload


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@given(payload=st.binary())
def test_round_trip(preset: str, payload: bytes) -> None:
    assert C_DECODE[preset](C_ENCODE[preset](payload)) == payload


# Error differential: same kind, same position, from the shared tables.


@pytest.mark.parametrize("kind", error_cases.INVALID_KINDS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_decode_rejects_invalid_characters(preset: str, kind: str) -> None:
    string, position = error_cases.INVALID_CASES[preset][kind]
    with pytest.raises(_core.DecodeError) as exc_info:
        C_DECODE[preset](string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.HEXAGRAM_REJECTIONS.values(),
    ids=error_cases.HEXAGRAM_REJECTIONS,
)
def test_hexagram_rejections(string: str, position: int) -> None:
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.hexagram_decode(string)
    assert exc_info.value.position == position


# The exhaustive sweep and the fuzz treatment.

_ACCEPTED_SINGLES = {"braille": 256, "hexagram": 0}


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_every_single_character_agrees(preset: str) -> None:
    """All 65,536 one-char strings, C vs oracle; braille accepts exactly its
    256 own characters, hexagram none (6 bits cannot fill a byte)."""
    accepted = sum(1 for code_point in range(0x10000) if _assert_parity(preset, chr(code_point)) is not None)
    assert accepted == _ACCEPTED_SINGLES[preset]


def _mutation_pool(preset: str) -> st.SearchStrategy[str]:
    module = error_cases.PRESETS[preset]
    alphabet = "".join(chr(module.START + i) for i in range(1 << module.BITS_PER_CHAR))
    # one_of keeps the hostiles from being lottery odds against the alphabet.
    return st.one_of(st.sampled_from(alphabet), st.sampled_from("A\x00\ud800\U0001f600"))


@st.composite
def _corrupted_encodings(draw: st.DrawFn, preset: str) -> str:
    encoded = error_cases.PRESETS[preset].encode(draw(st.binary()))
    pool = _mutation_pool(preset)
    mutation = draw(st.sampled_from(["replace", "insert", "delete", "truncate"]))
    if mutation == "insert":
        position = draw(st.integers(min_value=0, max_value=len(encoded)))
        return encoded[:position] + draw(pool) + encoded[position:]
    if not encoded:
        return draw(pool)  # nothing to mutate in place; a 1-char probe
    position = draw(st.integers(min_value=0, max_value=len(encoded) - 1))
    if mutation == "replace":
        return encoded[:position] + draw(pool) + encoded[position + 1 :]
    if mutation == "delete":
        return encoded[:position] + encoded[position + 1 :]
    return encoded[:position]  # truncate


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@given(data=st.data())
def test_fuzz_corrupted_encodings(preset: str, data: st.DataObject) -> None:
    _assert_parity(preset, data.draw(_corrupted_encodings(preset)))


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_megabyte_differential(preset: str) -> None:
    """Size-dependent bugs live past the sweep's comfort zone, both directions."""
    payload = random.Random(2**20).randbytes(2**20)
    encoded = C_ENCODE[preset](payload)
    assert encoded == error_cases.PRESETS[preset].encode(payload)
    assert C_DECODE[preset](encoded) == payload
