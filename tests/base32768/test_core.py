"""Conformance and differential tests for the C base32768 codec."""

from __future__ import annotations

import copy
import inspect
import pickle  # ruff: ignore[suspicious-pickle-import] -- tests pickle only their own objects
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
from tests.base32768 import error_cases
from tests.payloads import PAYLOAD_FLAVORS
from tests.reference import base32768 as base32768_reference


def test_encode_conformance(base32768_bin_path: pathlib.Path) -> None:
    payload = base32768_bin_path.read_bytes()
    expected = base32768_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert _core.base32768_encode(payload) == expected


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_encode_matches_reference_every_length(flavor: str, n: int) -> None:
    """Every tail shape at every small length; broken tail math can't hide."""
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert _core.base32768_encode(payload) == base32768_reference.encode(payload)


@given(st.binary())
def test_encode_matches_reference(payload: bytes) -> None:
    assert _core.base32768_encode(payload) == base32768_reference.encode(payload)


@pytest.mark.parametrize("view", [bytes, bytearray, memoryview])
def test_encode_accepts_any_buffer(view: Callable[[bytes], ReadableBuffer]) -> None:
    """The charter: encode() accepts any buffer-protocol object, not just bytes."""
    payload = random.Random(99).randbytes(187)
    assert _core.base32768_encode(view(payload)) == _core.base32768_encode(payload)


def test_encode_matches_reference_megabyte() -> None:
    """The vectors stop at 128 KiB; size-dependent bugs live past that."""
    payload = random.Random(2**20).randbytes(2**20)
    assert _core.base32768_encode(payload) == base32768_reference.encode(payload)


@pytest.mark.parametrize("bad", ["text", 42], ids=["str", "int"])
def test_encode_rejects_non_buffer(bad: str | int) -> None:
    """The exact prose is the platform's; match only the load-bearing phrase."""
    with pytest.raises(TypeError, match="bytes-like"):
        _core.base32768_encode(bad)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("func", [_core.base32768_encode, _core.base32768_decode])
def test_signature_is_pinned(func: Callable[..., object]) -> None:
    """Fails if the text-signature block in the C docstring is mangled or lost."""
    assert str(inspect.signature(func)) == "(data, /)"


# --- decode -----------------------------------------------------------------


def test_decode_conformance(base32768_bin_path: pathlib.Path) -> None:
    payload = base32768_bin_path.read_bytes()
    encoded = base32768_bin_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert _core.base32768_decode(encoded) == payload


# Cross-differentials: every arrow between the implementations tested independently.


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_decode_inverts_reference_encode(flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert _core.base32768_decode(base32768_reference.encode(payload)) == payload


@pytest.mark.parametrize("n", range(601))
@pytest.mark.parametrize("flavor", PAYLOAD_FLAVORS)
def test_reference_decode_inverts_encode(flavor: str, n: int) -> None:
    payload = PAYLOAD_FLAVORS[flavor](n)
    assert base32768_reference.decode(_core.base32768_encode(payload)) == payload


@given(st.binary())
def test_round_trip(payload: bytes) -> None:
    """The C-only loop at unbounded lengths; the cross arrows are sweep-covered."""
    assert _core.base32768_decode(_core.base32768_encode(payload)) == payload


# Error differential: same kind, same position; the reference asserts its side from the same tables.


@pytest.mark.parametrize("name", sorted(error_cases.BAD_CASES))
def test_decode_rejects_bad_input(name: str, vector_dir: pathlib.Path) -> None:
    bad = (vector_dir / "bad" / f"{name}.txt").read_text(encoding="utf-8")
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base32768_decode(bad)
    assert exc_info.value.position == error_cases.BAD_CASES[name]


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.HOSTILE_NON_BMP.values(),
    ids=error_cases.HOSTILE_NON_BMP,
)
def test_decode_rejects_astral_and_surrogate_input(string: str, position: int) -> None:
    """Astral entries exercise the bounds guard, surrogates the painted cells."""
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base32768_decode(string)
    assert exc_info.value.position == position


@pytest.mark.parametrize(
    ("string", "position"),
    error_cases.CANONICALITY_CASES.values(),
    ids=error_cases.CANONICALITY_CASES,
)
def test_decode_rejects_zero_payload_final_character(string: str, position: int) -> None:
    """The deliberate qntm divergence, enforced identically on both sides."""
    with pytest.raises(_core.DecodeError) as exc_info:
        _core.base32768_decode(string)
    assert exc_info.value.position == position


# DecodeError's own contract: fails when tp_init, the members, or the getset change.


def test_decode_error_is_a_value_error() -> None:
    assert issubclass(_core.DecodeError, ValueError)


def test_decode_error_default_message_names_the_position() -> None:
    assert str(_core.DecodeError(7)) == "Decode Error at position 7"


def test_decode_error_custom_message() -> None:
    err = _core.DecodeError(3, message="boom")
    assert (str(err), err.message, err.position) == ("boom", "boom", 3)


def test_decode_error_message_none_generates_text() -> None:
    """Explicit message=None is the same as omitting it (option c)."""
    err = _core.DecodeError(7, message=None)
    assert (str(err), err.message) == ("Decode Error at position 7", "Decode Error at position 7")


def test_decode_error_empty_message_is_preserved() -> None:
    """Option c: "" is a legal explicit message, stored verbatim."""
    err = _core.DecodeError(3, message="")
    assert (err.message, err.args) == ("", ("",))


def test_decode_error_rejects_non_str_message() -> None:
    """C-side only: the oracle deliberately trusts its annotations here."""
    with pytest.raises(TypeError, match="must be str or None"):
        _core.DecodeError(0, message=42)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
@pytest.mark.parametrize("flavor", error_cases.PICKLE_MESSAGE_CASES)
def test_decode_error_pickle_round_trip(flavor: str, protocol: int) -> None:
    """Every view of the clone must agree; position as the int, not truthiness."""
    kwargs, expected = error_cases.PICKLE_MESSAGE_CASES[flavor]
    original = _core.DecodeError(error_cases.PICKLE_POSITION, **kwargs)
    clone: object = pickle.loads(pickle.dumps(original, protocol))  # ruff: ignore[suspicious-pickle-usage]  # pyright: ignore[reportAny]
    assert type(clone) is _core.DecodeError
    assert clone.position == error_cases.PICKLE_POSITION
    assert (clone.message, clone.args, str(clone)) == (expected, (expected,), expected)


def test_decode_error_copy() -> None:
    """copy.copy rides __reduce_ex__: nearly free extra coverage."""
    clone = copy.copy(_core.DecodeError(error_cases.PICKLE_POSITION, message="boom"))
    assert type(clone) is _core.DecodeError
    assert (clone.position, clone.message, clone.args, str(clone)) == (
        error_cases.PICKLE_POSITION,
        "boom",
        ("boom",),
        "boom",
    )


def test_decode_error_setstate_rejects_non_str_state() -> None:
    """Pickle state is attacker-controlled input; a hand-crafted pickle can send anything."""
    with pytest.raises(TypeError, match="state must be str"):
        _core.DecodeError(0).__setstate__(42)  # pyright: ignore[reportArgumentType]


def test_decode_error_attributes_are_read_only() -> None:
    err = _core.DecodeError(1)
    with pytest.raises(AttributeError):
        err.position = 2  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(AttributeError):
        err.message = "x"  # pyright: ignore[reportAttributeAccessIssue]


def test_decode_error_raw_new_has_no_message() -> None:
    """The getset's defensive branch: raw __new__ answers None, never crashes."""
    assert _core.DecodeError.__new__(_core.DecodeError).message is None


def test_decode_error_requires_a_position() -> None:
    with pytest.raises(TypeError):
        _core.DecodeError()  # pyright: ignore[reportCallIssue]


# Housekeeping.


def test_decode_empty_string_is_empty_payload() -> None:
    assert _core.base32768_decode("") == b""


def _type_id(value: object) -> str:
    return type(value).__name__


@pytest.mark.parametrize("bad", error_cases.NON_STR_INPUTS, ids=_type_id)
def test_decode_rejects_non_str(bad: object) -> None:
    with pytest.raises(TypeError):
        _core.base32768_decode(bad)  # pyright: ignore[reportArgumentType]


def test_decode_matches_reference_megabyte() -> None:
    """The encode twin's mirror: size-dependent bugs, decode direction."""
    payload = random.Random(2**20).randbytes(2**20)
    assert _core.base32768_decode(base32768_reference.encode(payload)) == payload
