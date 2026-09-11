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
"""Conformance and differential tests for the C base65536 codec."""

from __future__ import annotations

import inspect
import random
import typing

if typing.TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable

    from _typeshed import ReadableBuffer

import pytest
from hypothesis import given
from hypothesis import strategies as st

from radixly import _core
from tests.base65536 import error_cases
from tests.payloads import PAYLOAD_FLAVORS
from tests.reference import base65536 as base65536_reference


def test_encode_conformance(base65536_bin_path: pathlib.Path) -> None:
    payload = base65536_bin_path.read_bytes()
    expected = base65536_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert _core.base65536_encode(payload) == expected


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_encode_matches_reference_every_length(flavor: str, n: int) -> None:
    """Both parities at every small length; a wrong tail byte cannot hide."""
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert _core.base65536_encode(payload) == base65536_reference.encode(payload)


@given(st.binary())
def test_encode_matches_reference(payload: bytes) -> None:
    assert _core.base65536_encode(payload) == base65536_reference.encode(payload)


@pytest.mark.parametrize("view", [bytes, bytearray, memoryview])
def test_encode_accepts_any_buffer(view: Callable[[bytes], ReadableBuffer]) -> None:
    """The charter: encode() accepts any buffer-protocol object, not just bytes."""
    payload = random.Random(99).randbytes(187)
    assert _core.base65536_encode(view(payload)) == _core.base65536_encode(payload)


def test_encode_matches_reference_megabyte() -> None:
    """The vectors stop at 768 KiB; size-dependent bugs live past that."""
    payload = random.Random(2**20).randbytes(2**20)
    assert _core.base65536_encode(payload) == base65536_reference.encode(payload)


@pytest.mark.parametrize(
    ("payload", "expected_kind"),
    [(bytes([1, 109]) * 50, 2), (bytes([1, 110]), 4), (bytes([255, 109, 7]), 2), (b"", 1)],
    ids=["last-bmp-block", "first-astral-block", "bmp-with-tail", "empty"],
)
def test_astral_output_starts_at_block_110(payload: bytes, expected_kind: int) -> None:
    """Blocks from 110 on leave the BMP; a str built in the wrong kind would compare unequal to the oracle."""
    encoded = _core.base65536_encode(payload)
    widest = max(map(ord, encoded), default=0)
    assert (1 if widest < 0x100 else 2 if widest <= 0xFFFF else 4) == expected_kind
    assert encoded == base65536_reference.encode(payload)
    assert {encoded} == {base65536_reference.encode(payload)}  # hashing agrees too


@pytest.mark.parametrize("bad", ["text", 42], ids=["str", "int"])
def test_encode_rejects_non_buffer(bad: str | int) -> None:
    """The exact prose is the platform's; match only the load-bearing phrase."""
    with pytest.raises(TypeError, match="bytes-like"):
        _core.base65536_encode(bad)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("func", [_core.base65536_encode, _core.base65536_decode])
def test_signature_is_pinned(func: Callable[..., object]) -> None:
    """Fails if the text-signature block in the C docstring is mangled or lost."""
    assert str(inspect.signature(func)) == "(data, /)"


def test_decode_conformance(base65536_bin_path: pathlib.Path) -> None:
    payload = base65536_bin_path.read_bytes()
    encoded = base65536_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert _core.base65536_decode(encoded) == payload


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_decode_inverts_reference_encode(flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert _core.base65536_decode(base65536_reference.encode(payload)) == payload


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_reference_decode_inverts_encode(flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert base65536_reference.decode(_core.base65536_encode(payload)) == payload


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    """The C-only loop at unbounded lengths; the cross arrows are sweep-covered."""
    assert _core.base65536_decode(_core.base65536_encode(payload)) == payload


@pytest.mark.parametrize("name", sorted(error_cases.BAD_CASES))
def test_decode_rejects_bad_input(name: str, vector_dir: pathlib.Path) -> None:
    bad = (vector_dir / "bad" / f"{name}.txt").read_text(encoding="utf-8")
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base65536_decode(bad)
    assert exc_info.value.position == error_cases.BAD_CASES[name]


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.HOSTILE_CASES.values(),
    ids=error_cases.HOSTILE_CASES,
)
def test_decode_rejects_hostile_input(string: str, position: int) -> None:
    """Unpainted block cells on every side: below, in a gap, past the last, surrogates, the top code point."""
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base65536_decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.TAIL_CASES.values(),
    ids=error_cases.TAIL_CASES,
)
def test_decode_rejects_tail_character_before_the_end(string: str, position: int) -> None:
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base65536_decode(string)
    assert exc_info.value.position == position


def test_decode_empty_string_is_empty_payload() -> None:
    assert _core.base65536_decode("") == b""


def test_decode_accepts_lone_tail_character() -> None:
    """A one-byte payload is exactly one tail character; the tail rule must not over-reject."""
    assert _core.base65536_decode(base65536_reference.encode(b"B")) == b"B"


def _type_id(value: object) -> str:
    return type(value).__name__


@pytest.mark.parametrize("bad", error_cases.NON_STR_INPUTS, ids=_type_id)
def test_decode_rejects_non_str(bad: object) -> None:
    with pytest.raises(TypeError):
        _core.base65536_decode(bad)  # pyright: ignore[reportArgumentType]


def test_decode_matches_reference_megabyte() -> None:
    """The encode twin's mirror: size-dependent bugs, decode direction."""
    payload = random.Random(2**20).randbytes(2**20)
    assert _core.base65536_decode(base65536_reference.encode(payload)) == payload
