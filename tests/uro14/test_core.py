"""Differential tests: the uro14 C functions against the reference oracle."""

from __future__ import annotations

import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from radixly import _core
from tests.reference import errors as errors_reference
from tests.reference import uro14


def _assert_parity(string: str) -> bytes | None:
    """C and the oracle must agree exactly; returns the payload on accept."""
    try:
        expected = uro14.decode(string)
    except errors_reference.DecodeError as reference_error:
        expected_position = reference_error.position
    else:
        result = _core.uro14_decode(string)
        assert result == expected
        return result
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.uro14_decode(string)
    assert exc_info.value.position == expected_position
    return None


@given(st.binary(max_size=50))
def test_every_tail_truncation_raises(payload: bytes) -> None:
    """The crown: every chop of every C encoding must raise from the C too,
    at the oracle's position."""
    encoded = _core.uro14_encode(payload)
    for i in range(len(encoded)):
        assert _assert_parity(encoded[:i]) is None


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    assert _core.uro14_decode(_core.uro14_encode(payload)) == payload


@given(st.binary())
def test_encode_matches_reference(payload: bytes) -> None:
    assert _core.uro14_encode(payload) == uro14.encode(payload)


def test_empty_three_ways() -> None:
    assert (_core.uro14_encode(b""), _core.uro14_decode("一")) == ("一", b"")
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.uro14_decode("")
    assert exc_info.value.position == 0


def test_lone_prefix_claiming_bytes_raises() -> None:
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.uro14_decode("丁")
    assert exc_info.value.position == 0


def test_swapped_prefix_is_a_length_lie() -> None:
    """A mismatch that is not truncation-shaped: valid body, lying prefix."""
    encoded = _core.uro14_encode(b"\xab\xcd")
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.uro14_decode("丁" + encoded[1:])
    assert exc_info.value.position == 0


# Same table as the reference's paper pins; here they pin the C.
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"\x00", "丁丿"),
        (b"\xab\xcd", "丂磳淿"),
    ],
)
def test_paper_pins(payload: bytes, expected: str) -> None:
    assert _core.uro14_encode(payload) == expected
    assert _core.uro14_decode(expected) == payload


@pytest.mark.parametrize("bad", ["A", "踀"], ids=["ascii", "one-past-block"])
def test_invalid_prefix_char(bad: str) -> None:
    """Must be the invalid-character error, not length-mismatch."""
    with pytest.raises(_core.DecodeError, match="invalid character") as exc_info:
        _core.uro14_decode(bad)
    assert exc_info.value.position == 0


def test_bad_body_char_position_counts_the_prefix() -> None:
    """Pins the +1 offset: the reported index is into the full string."""
    encoded = _core.uro14_encode(bytes(7))  # prefix + 4 body characters
    corrupted = encoded[:2] + "A" + encoded[3:]
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.uro14_decode(corrupted)
    assert exc_info.value.position == 2


def test_bad_padding_in_final_body_char() -> None:
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.uro14_decode("丁一")
    assert exc_info.value.position == 1


def test_round_trip_past_the_modulus() -> None:
    """20,000 bytes: the claim wraps and the candidate match must still pick
    the right payload length -- in the C this time."""
    payload = random.Random(20_000).randbytes(20_000)
    assert _core.uro14_decode(_core.uro14_encode(payload)) == payload


@given(st.binary())
def test_encoded_length(payload: bytes) -> None:
    assert len(_core.uro14_encode(payload)) == 1 + (8 * len(payload) + 13) // 14
