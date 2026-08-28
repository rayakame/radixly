"""Reference tests for the contiguous-block presets: braille (8 bits) and hexagram (6 bits)."""

from __future__ import annotations

import typing
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.block import error_cases
from tests.reference import braille
from tests.reference import errors as errors_reference
from tests.reference import hexagram


# Expected strings hand-derived on paper from START and the bit stream, then
# cross-checked; they must never be regenerated from the code they test.
@pytest.mark.parametrize(
    ("preset", "payload", "expected"),
    [
        ("braille", b"\x00", "⠀"),
        ("braille", b"\xff", "⣿"),
        ("braille", b"\xab\xcd", "⢫⣍"),
        ("hexagram", b"\x00", "䷀䷏"),
        ("hexagram", b"\xab\xcd", "䷪䷼䷷"),
    ],
)
def test_paper_pins(preset: str, payload: bytes, expected: str) -> None:
    module = error_cases.PRESETS[preset]
    assert module.encode(payload) == expected
    assert module.decode(expected) == payload


@pytest.mark.parametrize("preset", error_cases.PRESETS)
@given(payload=st.binary())
def test_round_trip(preset: str, payload: bytes) -> None:
    module = error_cases.PRESETS[preset]
    assert module.decode(module.encode(payload)) == payload


@given(st.binary())
def test_braille_is_one_char_per_byte(payload: bytes) -> None:
    assert len(braille.encode(payload)) == len(payload)


def test_braille_every_length_decodes() -> None:
    for num_chars in range(64):
        assert braille.decode("⠀" * num_chars) == bytes(num_chars)


def test_rejection_catalogs_are_nonempty() -> None:
    """Emptied catalogs would collect zero rejection cases and guard nothing."""
    assert len(error_cases.INVALID_KINDS) > 0
    assert len(error_cases.HEXAGRAM_REJECTIONS) > 0


@pytest.mark.parametrize("kind", error_cases.INVALID_KINDS)
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_invalid_character_positions(preset: str, kind: str) -> None:
    string, position = error_cases.INVALID_CASES[preset][kind]
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        error_cases.PRESETS[preset].decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.HEXAGRAM_REJECTIONS.values(),
    ids=error_cases.HEXAGRAM_REJECTIONS,
)
def test_hexagram_rejections(string: str, position: int) -> None:
    """The reasoning behind each case lives with the data in error_cases."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        hexagram.decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize("form", ["NFC", "NFD", "NFKC", "NFKD"])
@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_alphabet_sanity(preset: str, form: typing.Literal["NFC", "NFD", "NFKC", "NFKD"]) -> None:
    """Fully assigned, all Symbol-other, and a fixed point of every normalization form."""
    module = error_cases.PRESETS[preset]
    alphabet = "".join(chr(module.START + i) for i in range(1 << module.BITS_PER_CHAR))
    assert {unicodedata.category(char) for char in alphabet} == {"So"}
    assert unicodedata.normalize(form, alphabet) == alphabet


@pytest.mark.parametrize("preset", error_cases.PRESETS)
def test_empty_both_directions(preset: str) -> None:
    module = error_cases.PRESETS[preset]
    assert (module.encode(b""), module.decode("")) == ("", b"")
