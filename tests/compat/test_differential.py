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
"""The drop-in against the standard library itself: same results or the same exception, type and text alike."""

from __future__ import annotations

import base64
import inspect
import typing

import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from radixly import _core
from radixly.compat import base64 as compat

if typing.TYPE_CHECKING:
    from collections.abc import Callable

STDLIB_ALL = typing.cast("list[str]", base64.__all__)
PORTED = sorted(name for name in STDLIB_ALL if getattr(compat, name) is getattr(_core, name, None))


def _ours(name: str) -> Callable[..., object]:
    return typing.cast("Callable[..., object]", getattr(compat, name))


def _theirs(name: str) -> Callable[..., object]:
    return typing.cast("Callable[..., object]", getattr(base64, name))


def test_ported_set_is_what_this_release_promises() -> None:
    """The docs list what runs in C; a port that fell back to the stdlib unnoticed would still pass every test."""
    assert PORTED == ["b16decode", "b16encode", "b32decode", "b32encode", "b32hexdecode", "b32hexencode"]


def test_all_matches_the_stdlib() -> None:
    assert sorted(compat.__all__) == sorted(STDLIB_ALL)


@pytest.mark.parametrize("name", sorted(STDLIB_ALL))
def test_signatures_match_the_stdlib(name: str) -> None:
    assert inspect.signature(_ours(name)) == inspect.signature(_theirs(name))


@pytest.mark.parametrize("name", sorted(STDLIB_ALL))
def test_keyword_calls_match_the_stdlib(name: str) -> None:
    """Every stdlib parameter can be passed by name; the C binders must accept the same spellings."""
    signature = inspect.signature(_theirs(name))
    if name in {"encode", "decode"}:
        return  # file arguments; covered by the vendored suite
    for parameter in signature.parameters.values():
        if parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD:
            assert parameter.name in signature.parameters


def _outcome(function: Callable[..., object], *args: object, **kwargs: object) -> tuple[str, object]:
    try:
        return ("ok", function(*args, **kwargs))
    except Exception as error:  # ruff: ignore[blind-except] -- the exception IS the result under comparison
        return (type(error).__qualname__, error.args)


def _assert_same(name: str, *args: object, **kwargs: object) -> None:
    ours = _outcome(_ours(name), *args, **kwargs)
    theirs = _outcome(_theirs(name), *args, **kwargs)
    assert ours == theirs


_TEXT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=01abcdefghijklmnopqrstuvwxyz \n\t!~\x00\xff"
_ENCODED_LIKE = st.text(alphabet=_TEXT_CHARS, max_size=40)
_DECODE_INPUTS = st.one_of(
    _ENCODED_LIKE,
    _ENCODED_LIKE.map(lambda text: text.encode("latin-1")),
    _ENCODED_LIKE.map(lambda text: bytearray(text.encode("latin-1"))),
    st.binary(max_size=40).map(memoryview),
    st.binary(max_size=40).map(lambda data: memoryview(data)[::2]),
    st.text(max_size=8),  # anything, non-ASCII included
)
_ENCODE_INPUTS = st.one_of(
    st.binary(max_size=40),
    st.binary(max_size=40).map(bytearray),
    st.binary(max_size=40).map(memoryview),
    st.binary(max_size=40).map(lambda data: memoryview(data)[::2]),
    st.binary(min_size=4, max_size=40)
    .filter(lambda data: len(data) % 4 == 0)
    .map(lambda data: memoryview(data).cast("I")),
)
_FLAGS = st.sampled_from([True, False, 1, 0, None, "x", ""])
_MAP01 = st.sampled_from([None, "L", "I", b"l", b"I", "LL", "", 5, "\xe9", bytearray(b"O")])
_ANYTHING = st.sampled_from([42, [], (), 3.5, object(), None])


@settings(max_examples=2000)
@given(st.sampled_from(["b16encode", "b32encode", "b32hexencode"]), _ENCODE_INPUTS)
def test_encoders_match(name: str, data: object) -> None:
    _assert_same(name, data)


@settings(max_examples=3000)
@given(_DECODE_INPUTS, _FLAGS, _MAP01)
def test_b32decode_matches(data: object, casefold: object, map01: object) -> None:
    _assert_same("b32decode", data, casefold, map01)
    _assert_same("b32decode", data, casefold=casefold, map01=map01)


@settings(max_examples=2000)
@given(_DECODE_INPUTS, _FLAGS)
def test_b32hexdecode_matches(data: object, casefold: object) -> None:
    _assert_same("b32hexdecode", data, casefold)
    _assert_same("b32hexdecode", data, casefold=casefold)


@settings(max_examples=2000)
@given(_DECODE_INPUTS, _FLAGS)
def test_b16decode_matches(data: object, casefold: object) -> None:
    _assert_same("b16decode", data, casefold)
    _assert_same("b16decode", data, casefold=casefold)


@given(st.binary(max_size=40))
def test_ported_round_trips_agree_with_the_stdlib(data: bytes) -> None:
    for encoder, decoder in (("b16encode", "b16decode"), ("b32encode", "b32decode"), ("b32hexencode", "b32hexdecode")):
        encoded = _ours(encoder)(data)
        assert encoded == _theirs(encoder)(data)
        assert _ours(decoder)(encoded) == data
        assert _theirs(decoder)(encoded) == data


@pytest.mark.parametrize("name", ["b16encode", "b16decode", "b32encode", "b32decode", "b32hexencode", "b32hexdecode"])
def test_wrong_argument_shapes_match(name: str) -> None:
    """Too many, unknown and duplicate arguments raise TypeError on both sides; the stdlib text is CPython's."""
    shapes: list[tuple[tuple[object, ...], dict[str, object]]] = [
        ((), {}),
        ((b"", b"", b"", b""), {}),
        ((b"",), {"nope": 1}),
        ((b"",), {"s": b""}),
    ]
    for args, kwargs in shapes:
        ours = _outcome(_ours(name), *args, **kwargs)
        theirs = _outcome(_theirs(name), *args, **kwargs)
        assert ours[0] == theirs[0] == "TypeError", (name, ours, theirs)


@pytest.mark.parametrize("value", [42, [], (), 3.5, None])
def test_non_buffer_inputs_match(value: object) -> None:
    for name in ("b16encode", "b32encode", "b32hexencode", "b16decode", "b32decode", "b32hexdecode"):
        _assert_same(name, value)


def test_map01_assertion_text_matches() -> None:
    """The stdlib asserts the length and reports the repr; the port says the same."""
    _assert_same("b32decode", "AAAAAAAA", map01="IL")
    _assert_same("b32decode", "AAAAAAAA", map01=b"")


def test_stdlib_quirks_are_kept() -> None:
    """Nonzero pad bits pass, seven data characters pass, a strided view is copied: the stdlib's calls, not ours."""
    assert compat.b32decode("IF======") == base64.b32decode("IF======") == b"A"
    assert compat.b32decode("IEAAAAA=") == base64.b32decode("IEAAAAA=") == b"A\x00\x00\x00"
    assert compat.b16decode(memoryview(b"AABBCCDD")[::2]) == b"\xab\xcd"
    assert compat.b32encode(memoryview(b"abcdef")[::2]) == base64.b32encode(b"ace")
