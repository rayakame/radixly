"""The block presets' codec surfaces: re-exports, Codec values, and size math."""

from __future__ import annotations

import typing

import pytest
from hypothesis import given
from hypothesis import strategies as st

import radixly.braille
import radixly.hexagram
from radixly import _core
from radixly.braille import _api as braille_api
from radixly.hexagram import _api as hexagram_api

if typing.TYPE_CHECKING:
    from collections.abc import Callable


def test_functions_are_the_core_functions() -> None:
    """The zero-cost pin: the module attributes ARE the C functions."""
    assert radixly.braille.encode is _core.braille_encode
    assert radixly.braille.decode is _core.braille_decode
    assert radixly.hexagram.encode is _core.hexagram_encode
    assert radixly.hexagram.decode is _core.hexagram_decode


def test_braille_codec_fields() -> None:
    codec = radixly.braille.BRAILLE
    assert codec.encode is radixly.braille.encode
    assert codec.decode is radixly.braille.decode
    assert codec.encoded_len is radixly.braille.encoded_len
    assert codec.max_bytes is radixly.braille.max_bytes
    assert codec.name == "braille"
    assert codec.bits_per_char == 8 == radixly.braille.BITS_PER_CHAR
    assert radixly.get_codec("braille") is codec


def test_hexagram_codec_fields() -> None:
    codec = radixly.hexagram.HEXAGRAM
    assert codec.encode is radixly.hexagram.encode
    assert codec.decode is radixly.hexagram.decode
    assert codec.encoded_len is radixly.hexagram.encoded_len
    assert codec.max_bytes is radixly.hexagram.max_bytes
    assert codec.name == "hexagram"
    assert codec.bits_per_char == 6 == radixly.hexagram.BITS_PER_CHAR
    assert radixly.get_codec("hexagram") is codec


def test_api_all_is_nonempty() -> None:
    """An emptied __all__ would collect zero re-export cases and guard nothing."""
    assert len(braille_api.__all__) > 0
    assert len(hexagram_api.__all__) > 0


_REEXPORTS = [("braille", name) for name in braille_api.__all__] + [("hexagram", name) for name in hexagram_api.__all__]


@pytest.mark.parametrize(("codec", "name"), _REEXPORTS)
def test_package_reexports_the_api(codec: str, name: str) -> None:
    package = {"braille": radixly.braille, "hexagram": radixly.hexagram}[codec]
    api = {"braille": braille_api, "hexagram": hexagram_api}[codec]
    assert getattr(package, name) is getattr(api, name)


_SIZE_MATH: dict[str, tuple[Callable[[int], int], Callable[[int], int]]] = {
    "braille": (radixly.braille.encoded_len, radixly.braille.max_bytes),
    "hexagram": (radixly.hexagram.encoded_len, radixly.hexagram.max_bytes),
}
_ENCODE = {"braille": radixly.braille.encode, "hexagram": radixly.hexagram.encode}


@pytest.mark.parametrize("codec", _SIZE_MATH)
@given(payload=st.binary())
def test_encoded_len_matches_encode(codec: str, payload: bytes) -> None:
    encoded_len, _ = _SIZE_MATH[codec]
    assert encoded_len(len(payload)) == len(_ENCODE[codec](payload))


@pytest.mark.parametrize("n", range(1000))
@pytest.mark.parametrize("codec", _SIZE_MATH)
def test_max_bytes_is_maximal(codec: str, n: int) -> None:
    """max_bytes(n) fits in n characters; one more byte would not."""
    encoded_len, max_bytes = _SIZE_MATH[codec]
    assert encoded_len(max_bytes(n)) <= n < encoded_len(max_bytes(n) + 1)


@pytest.mark.parametrize(
    ("codec", "num_bytes", "expected"),
    [
        ("braille", 0, 0),
        ("braille", 1, 1),
        ("braille", 187, 187),
        ("hexagram", 0, 0),
        ("hexagram", 1, 2),
        ("hexagram", 3, 4),
        ("hexagram", 187, 250),
    ],
)
def test_encoded_len_pins(codec: str, num_bytes: int, expected: int) -> None:
    assert _SIZE_MATH[codec][0](num_bytes) == expected


@pytest.mark.parametrize(
    ("codec", "num_chars", "expected"),
    [
        ("braille", 0, 0),
        ("braille", 100, 100),
        ("hexagram", 0, 0),
        ("hexagram", 1, 0),
        ("hexagram", 4, 3),
        ("hexagram", 100, 75),  # base64's density, in hexagrams
    ],
)
def test_max_bytes_pins(codec: str, num_chars: int, expected: int) -> None:
    assert _SIZE_MATH[codec][1](num_chars) == expected


@pytest.mark.parametrize(
    "func",
    [
        radixly.braille.encoded_len,
        radixly.braille.max_bytes,
        radixly.hexagram.encoded_len,
        radixly.hexagram.max_bytes,
    ],
)
@pytest.mark.parametrize("bad", [-1, -(10**9)])
def test_negative_input_rejected(func: Callable[[int], int], bad: int) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        func(bad)
