"""Reference tests for the contiguous-block presets: braille (8 bits) and hexagram (6 bits)."""

from __future__ import annotations

import typing
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.reference import braille
from tests.reference import errors as errors_reference
from tests.reference import hexagram

if typing.TYPE_CHECKING:
    from collections.abc import Callable


class BlockPreset(typing.Protocol):
    """The shape both preset modules share."""

    @property
    def START(self) -> int: ...  # ruff: ignore[invalid-function-name]
    @property
    def BITS_PER_CHAR(self) -> int: ...  # ruff: ignore[invalid-function-name]
    @property
    def encode(self) -> Callable[[bytes], str]: ...
    @property
    def decode(self) -> Callable[[str], bytes]: ...


PRESETS: dict[str, BlockPreset] = {"braille": braille, "hexagram": hexagram}


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
    module = PRESETS[preset]
    assert module.encode(payload) == expected
    assert module.decode(expected) == payload


@pytest.mark.parametrize("preset", PRESETS)
@given(payload=st.binary())
def test_round_trip(preset: str, payload: bytes) -> None:
    module = PRESETS[preset]
    assert module.decode(module.encode(payload)) == payload


@pytest.mark.parametrize("num_chars", [1, 5, 9])
def test_hexagram_zero_payload_lengths_raise(num_chars: int) -> None:
    """6n bits at n % 4 == 1 leave 6 padding bits: the final char carries nothing."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        hexagram.decode("䷿" * num_chars)
    assert exc_info.value.position == num_chars - 1


@given(st.binary())
def test_braille_is_one_char_per_byte(payload: bytes) -> None:
    assert len(braille.encode(payload)) == len(payload)


def test_braille_every_length_decodes() -> None:
    for num_chars in range(64):
        assert braille.decode("⠀" * num_chars) == bytes(num_chars)


def _bad_char(module: BlockPreset, kind: str) -> str:
    return {
        "below-block": chr(module.START - 1),
        "above-block": chr(module.START + (1 << module.BITS_PER_CHAR)),
        "astral": "\U0001f600",
        "lone-surrogate": "\ud800",
    }[kind]


@pytest.mark.parametrize("kind", ["below-block", "above-block", "astral", "lone-surrogate"])
@pytest.mark.parametrize("preset", PRESETS)
def test_invalid_character_positions(preset: str, kind: str) -> None:
    module = PRESETS[preset]
    bad = _bad_char(module, kind)
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        module.decode(bad)
    assert exc_info.value.position == 0
    prefix = module.encode(bytes(3))  # 24 bits: full characters in both presets
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        module.decode(prefix + bad + prefix)
    assert exc_info.value.position == len(prefix)


def test_hexagram_appended_filler_rejected() -> None:
    """Canonicality carries over from base32768: a pure-filler final char is refused."""
    encoded = hexagram.encode(bytes(3))  # 4 full characters, no padding
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        hexagram.decode(encoded + "䷿")
    assert exc_info.value.position == 4


def test_hexagram_zeroed_padding_rejected() -> None:
    """b"\\x00" encodes to U+4DC0 U+4DCF; zeroing the 4 padding bits gives U+4DC0."""
    with pytest.raises(errors_reference.DecodeError) as exc_info:
        hexagram.decode("䷀䷀")
    assert exc_info.value.position == 1


@pytest.mark.parametrize("form", ["NFC", "NFD", "NFKC", "NFKD"])
@pytest.mark.parametrize("preset", PRESETS)
def test_alphabet_sanity(preset: str, form: typing.Literal["NFC", "NFD", "NFKC", "NFKD"]) -> None:
    """Fully assigned, all Symbol-other, and a fixed point of every normalization form."""
    module = PRESETS[preset]
    alphabet = "".join(chr(module.START + i) for i in range(1 << module.BITS_PER_CHAR))
    assert {unicodedata.category(char) for char in alphabet} == {"So"}
    assert unicodedata.normalize(form, alphabet) == alphabet


@pytest.mark.parametrize("preset", PRESETS)
def test_empty_both_directions(preset: str) -> None:
    module = PRESETS[preset]
    assert (module.encode(b""), module.decode("")) == ("", b"")
