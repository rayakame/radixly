"""Reference tests for uro14: 14 bits per CJK character behind a length prefix."""

from __future__ import annotations

import random
import typing
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.reference import errors as errors_reference
from tests.reference import uro14


@given(st.binary(max_size=50))
def test_every_tail_truncation_raises(payload: bytes) -> None:
    """The codec's reason to exist: the length prefix catches every tail cut."""
    encoded = uro14.encode(payload)
    for i in range(len(encoded)):
        with pytest.raises(errors_reference.DecodeError):
            uro14.decode(encoded[:i])


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    assert uro14.decode(uro14.encode(payload)) == payload


def test_empty_three_ways() -> None:
    """b"" encodes to the lone length character; the empty string never decodes."""
    assert (uro14.encode(b""), uro14.decode("一")) == ("一", b"")
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        uro14.decode("")
    assert exc_info.value.position == 0


def test_lone_prefix_claiming_bytes_raises() -> None:
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        uro14.decode("丁")
    assert exc_info.value.position == 0


def test_swapped_prefix_is_a_length_lie() -> None:
    """A mismatch that is not truncation-shaped: valid body, lying prefix."""
    encoded = uro14.encode(b"\xab\xcd")
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        uro14.decode("丁" + encoded[1:])
    assert exc_info.value.position == 0


def test_round_trip_past_the_modulus() -> None:
    """20,000 bytes: the claim wraps (20000 % 16384 = 3616) and the candidate
    match must still pick the right payload length. Hypothesis stays small by
    design, so this one is deterministic."""
    payload = random.Random(20_000).randbytes(20_000)
    assert uro14.decode(uro14.encode(payload)) == payload


# Hand-derived on paper from START and the bit stream; never regenerate from the code.
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"\x00", "丁丿"),  # prefix claims 1; 8 zero bits + 6 one-pads = 63
        (b"\xab\xcd", "丂磳淿"),  # 10101011110011 = 10995, then 01 + 12 one-pads = 8191
    ],
)
def test_paper_pins(payload: bytes, expected: str) -> None:
    assert uro14.encode(payload) == expected
    assert uro14.decode(expected) == payload


@pytest.mark.parametrize("bad", ["A", "踀"], ids=["ascii", "one-past-block"])
def test_invalid_prefix_char(bad: str) -> None:
    """Must be the invalid-character error, not length-mismatch: the one place
    prose is worth matching."""
    with pytest.raises(errors_reference.DecodeError, match="invalid character") as exc_info:
        uro14.decode(bad)
    assert exc_info.value.position == 0


def test_bad_body_char_position_counts_the_prefix() -> None:
    """Pins the +1 offset: the reported index is into the full string."""
    encoded = uro14.encode(bytes(7))  # prefix + 4 body characters
    corrupted = encoded[:2] + "A" + encoded[3:]
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        uro14.decode(corrupted)
    assert exc_info.value.position == 2


def test_bad_padding_in_final_body_char() -> None:
    """The b"\\x00" pin with its 6 padding ones zeroed: U+4E3F becomes U+4E00."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        uro14.decode("丁一")
    assert exc_info.value.position == 1


@pytest.mark.parametrize("form", ["NFC", "NFD", "NFKC", "NFKD"])
def test_alphabet_sanity(form: typing.Literal["NFC", "NFD", "NFKC", "NFKD"]) -> None:
    """U+4E00..U+8DFF: fully assigned, all Letter-other, normalization-stable."""
    alphabet = "".join(chr(uro14.START + i) for i in range(uro14.MODULUS))
    assert {unicodedata.category(char) for char in alphabet} == {"Lo"}
    assert unicodedata.normalize(form, alphabet) == alphabet


@given(st.binary())
def test_encoded_length(payload: bytes) -> None:
    assert len(uro14.encode(payload)) == 1 + (8 * len(payload) + 13) // 14
