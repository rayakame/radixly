"""The uro14 codec surface: re-exports, the Codec value, and the length math."""

from __future__ import annotations

import typing

import pytest
from hypothesis import given
from hypothesis import strategies as st

import radixly.uro14
from radixly import _core
from radixly.uro14 import _api

if typing.TYPE_CHECKING:
    from collections.abc import Callable


def test_functions_are_the_core_functions() -> None:
    """The zero-cost pin: the module attributes ARE the C functions."""
    assert radixly.uro14.encode is _core.uro14_encode
    assert radixly.uro14.decode is _core.uro14_decode


def test_codec_fields() -> None:
    codec = radixly.uro14.URO14
    assert codec.encode is radixly.uro14.encode
    assert codec.decode is radixly.uro14.decode
    assert codec.encoded_len is radixly.uro14.encoded_len
    assert codec.max_bytes is radixly.uro14.max_bytes
    assert codec.name == "uro14"
    assert codec.bits_per_char == 14 == radixly.uro14.BITS_PER_CHAR
    assert radixly.get_codec("uro14") is codec


def test_api_all_is_nonempty() -> None:
    """An emptied __all__ would collect zero re-export cases and guard nothing."""
    assert len(_api.__all__) > 0


@pytest.mark.parametrize("name", _api.__all__)
def test_package_reexports_the_api(name: str) -> None:
    assert getattr(radixly.uro14, name) is getattr(_api, name)


@given(st.binary())
def test_encoded_len_matches_encode(payload: bytes) -> None:
    assert radixly.uro14.encoded_len(len(payload)) == len(radixly.uro14.encode(payload))


@pytest.mark.parametrize("n", range(1, 1000))
def test_max_bytes_is_maximal(n: int) -> None:
    """max_bytes(n) fits in n characters; one more byte would not. n = 0 is the
    special case below: even b"" needs the prefix character."""
    assert radixly.uro14.encoded_len(radixly.uro14.max_bytes(n)) <= n
    assert n < radixly.uro14.encoded_len(radixly.uro14.max_bytes(n) + 1)


def test_zero_chars_fit_nothing() -> None:
    assert radixly.uro14.max_bytes(0) == 0
    assert radixly.uro14.encoded_len(0) == 1  # the prefix always costs one


@pytest.mark.parametrize(("num_bytes", "expected"), [(0, 1), (1, 2), (15, 10), (187, 108)])
def test_encoded_len_pins(num_bytes: int, expected: int) -> None:
    assert radixly.uro14.encoded_len(num_bytes) == expected


@pytest.mark.parametrize(("num_chars", "expected"), [(0, 0), (1, 0), (8, 12), (100, 173)])
def test_max_bytes_pins(num_chars: int, expected: int) -> None:
    """The headline: 100 code points carry 173 bytes, truncation-proof."""
    assert radixly.uro14.max_bytes(num_chars) == expected


@pytest.mark.parametrize("func", [radixly.uro14.encoded_len, radixly.uro14.max_bytes])
@pytest.mark.parametrize("bad", [-1, -(10**9)])
def test_negative_input_rejected(func: Callable[[int], int], bad: int) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        func(bad)
