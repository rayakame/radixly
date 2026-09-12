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
import decimal
import inspect
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed argv, own interpreter
import sys
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


@pytest.mark.parametrize("name", PORTED)
def test_keyword_calls_match_the_stdlib(name: str) -> None:
    """Every parameter the stdlib takes by name, the port takes by name, with the same result."""
    parameters = inspect.signature(_theirs(name)).parameters
    assert all(p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for p in parameters.values())
    encoded = {"b16": b"4142", "b32": b"IE======", "b32hex": b"88======"}
    samples: dict[str, object] = {"s": encoded[name[:-6]], "casefold": True, "map01": "L"}
    by_name = {parameter: samples[parameter] for parameter in parameters}
    _assert_same(name, **by_name)
    assert _outcome(_ours(name), **by_name)[0] is _Ok


class _Ok:
    """The marker for a call that returned; the value sits next to it."""


def _outcome(function: Callable[..., object], *args: object, **kwargs: object) -> tuple[type, object]:
    try:
        return (_Ok, function(*args, **kwargs))
    # The exception is the result under comparison.
    except Exception as error:  # ruff: ignore[blind-except]
        return (type(error), error.args)


def _assert_same(name: str, *args: object, **kwargs: object) -> None:
    ours = _outcome(_ours(name), *args, **kwargs)
    theirs = _outcome(_theirs(name), *args, **kwargs)
    assert ours == theirs


class _RaisingFlag:
    """A truth value that raises, to pin where in the argument order the stdlib looks at casefold."""

    def __bool__(self) -> bool:
        message = "flag looked at"
        raise RuntimeError(message)


class _RaisingBuffer:
    """An exporter that fails with its own error, which the stdlib passes on instead of rewording."""

    def __buffer__(self, flags: int) -> memoryview:
        message = "no buffer today"
        raise RuntimeError(message)


def _released() -> memoryview:
    view = memoryview(b"IE======")
    view.release()
    return view


def _two_dimensional(data: bytes) -> memoryview:
    return memoryview(data).cast("B", (len(data) // 2, 2))


def _mutated(text: str) -> st.SearchStrategy[str]:
    """One character of a valid encoding replaced by anything ASCII, so every error branch is reachable."""
    if not text:
        return st.just(text)
    return st.tuples(st.integers(0, len(text) - 1), st.characters(max_codepoint=0x7F)).map(
        lambda spot: text[: spot[0]] + spot[1] + text[spot[0] + 1 :]
    )


# Even and four-aligned lengths built directly, so no example is filtered away.
_PAIRS = st.lists(st.binary(min_size=2, max_size=2), min_size=1, max_size=20).map(b"".join)
_QUADS = st.lists(st.binary(min_size=4, max_size=4), min_size=1, max_size=10).map(b"".join)
# Built per example, as Hypothesis hashes sampled values and a released memoryview refuses that.
_HOSTILE_OBJECTS = st.sampled_from(
    [_released, _RaisingBuffer, lambda: decimal.Decimal(1), lambda: 42, lambda: None]
).map(lambda make: make())
_TEXT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=01abcdefghijklmnopqrstuvwxyz \n\t!~\x00\xff"
_ENCODED_LIKE: st.SearchStrategy[str] = st.one_of(  # six strategies: one_of would infer Any
    st.text(alphabet=_TEXT_CHARS, max_size=40),
    st.binary(max_size=25).map(lambda data: base64.b32encode(data).decode()),
    st.binary(max_size=25).map(lambda data: base64.b32hexencode(data).decode()),
    st.binary(max_size=20).map(lambda data: base64.b16encode(data).decode()),
    st.binary(max_size=25).map(lambda data: base64.b32encode(data).decode()).flatmap(_mutated),
    st.binary(max_size=20).map(lambda data: base64.b16encode(data).decode()).flatmap(_mutated),
)
_DECODE_INPUTS = st.one_of(
    _ENCODED_LIKE,
    _ENCODED_LIKE.map(lambda text: text.encode("latin-1")),
    _ENCODED_LIKE.map(lambda text: bytearray(text.encode("latin-1"))),
    _ENCODED_LIKE.map(lambda text: memoryview(text.encode("latin-1"))),
    st.binary(max_size=40).map(lambda data: memoryview(data)[::2]),
    _PAIRS.map(_two_dimensional),
    _QUADS.map(lambda data: memoryview(data).cast("I")),
    st.text(max_size=8),
    _HOSTILE_OBJECTS,
)
_ENCODE_INPUTS = st.one_of(
    st.binary(max_size=40),
    st.binary(max_size=40).map(bytearray),
    st.binary(max_size=40).map(memoryview),
    st.binary(max_size=40).map(lambda data: memoryview(data)[::2]),
    _PAIRS.map(_two_dimensional),
    _QUADS.map(lambda data: memoryview(data).cast("I")),
    _HOSTILE_OBJECTS,
    st.sampled_from(["text", ""]),
)
_FLAGS = st.sampled_from([True, False, 1, 0, None, "x", "", _RaisingFlag()])
_MAP01 = st.sampled_from(
    [None, "L", "I", b"l", b"I", "LL", "", 5, "\xe9", bytearray(b"O"), "=", b"=", bytearray(b"ab"), memoryview(b"ab")]
)


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
    """Too many, missing, unknown and duplicate arguments raise the stdlib's TypeError, text included."""
    shapes: list[tuple[tuple[object, ...], dict[str, object]]] = [
        ((), {}),
        ((b"", b"", b"", b""), {}),
        ((b"",), {"nope": 1}),
        ((b"",), {"s": b""}),
        ((b"", b"", b"", b""), {"nope": 1}),  # the unknown keyword is judged before the positional count
        ((b"", b"", b"", b""), {"s": b""}),  # so is the duplicate
        ((b"", b"", b""), {"casefold": True}),  # decoders: multiple values for casefold, not too many positionals
        ((), {"casefold": True}),  # decoders: s is missing once the keyword is bound
        ((b"",), {"casefol": True}),  # 3.13 and later suggest the nearest name; the port carries the suffix too
        ((b"",), {"Casefold": True}),
        ((b"",), {"map1": "L"}),
        ((b"",), {"mapp01": "L"}),
        ((b"",), {"S": b""}),
        ((b"",), {"s_": b""}),
    ]
    if name != "b32decode":
        shapes.append(((b"",), {"map01": "L"}))  # only b32decode takes map01
    for args, kwargs in shapes:
        _assert_same(name, *args, **kwargs)
        assert _outcome(_ours(name), *args, **kwargs)[0] is TypeError, (name, args, kwargs)
    assert _outcome(compat.b32decode, b"", map01="L") == (_Ok, b"")


class _ClassLiar:
    """An object whose __class__ is not its type; the stdlib names the former."""

    @property
    def __class__(self) -> type[int]:  # pyright: ignore[reportIncompatibleMethodOverride, reportImplicitOverride]
        return int


def _context_shape(function: Callable[..., object], *args: object) -> tuple[type, type, bool]:
    try:
        function(*args)
    except Exception as error:  # ruff: ignore[blind-except] -- the exception chain is the subject
        return (type(error), type(error.__context__), error.__suppress_context__)
    message = "expected an exception"
    raise AssertionError(message)


def test_non_ascii_str_carries_the_stdlib_context() -> None:
    """The stdlib raises the ValueError inside `except UnicodeEncodeError`, so the traceback shows both."""
    for name in ("b16decode", "b32decode", "b32hexdecode"):
        ours = _context_shape(_ours(name), "\xe9")
        assert ours == _context_shape(_theirs(name), "\xe9") == (ValueError, UnicodeEncodeError, False)
    assert _outcome(compat.b32decode, "", map01="\xe9")[0] is ValueError


@pytest.mark.parametrize(
    "make",
    [
        lambda: 42,
        list,
        tuple,
        lambda: 3.5,
        lambda: None,
        str,
        lambda: decimal.Decimal(1),
        _released,
        _RaisingBuffer,
        _ClassLiar,
    ],
)
def test_non_buffer_inputs_match(make: Callable[[], object]) -> None:
    for name in PORTED:
        _assert_same(name, make())


def test_map01_assertion_text_matches() -> None:
    """The stdlib asserts the length and reports the repr of what its coercion left; the port says the same."""
    _assert_same("b32decode", "AAAAAAAA", map01="IL")
    _assert_same("b32decode", "AAAAAAAA", map01=b"")
    _assert_same("b32decode", "AAAAAAAA", map01=bytearray(b"ab"))
    _assert_same("b32decode", "AAAAAAAA", map01=memoryview(b"ab"))
    assert _outcome(compat.b32decode, "AAAAAAAA", map01=bytearray(b"ab")) == (AssertionError, ("bytearray(b'ab')",))


def test_map01_under_optimize_matches() -> None:
    """Under -O the stdlib's assert is gone and maketrans raises a ValueError instead; the port follows the flag."""
    script = (
        "import base64, sys\n"
        "from radixly.compat import base64 as compat\n"
        "def run(f):\n"
        "    try:\n"
        "        f('AAAAAAAA', map01='ab')\n"
        "    except Exception as error:\n"
        "        return (type(error).__name__, error.args)\n"
        "assert sys.flags.optimize == 1\n"
        "expected = ('ValueError', ('maketrans arguments must have same length',))\n"
        "assert run(base64.b32decode) == expected, run(base64.b32decode)\n"
        "assert run(compat.b32decode) == expected, run(compat.b32decode)\n"
    )
    subprocess.run([sys.executable, "-O", "-c", script], check=True)  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argv, own interpreter


def test_flag_is_looked_at_where_the_stdlib_looks() -> None:
    """The stdlib reads s (and map01) before casefold, so a flag that raises loses to an input that raises."""
    _assert_same("b16decode", 42, casefold=_RaisingFlag())
    _assert_same("b16decode", b"", casefold=_RaisingFlag())
    _assert_same("b32decode", "MFRGG=", casefold=_RaisingFlag())
    _assert_same("b32decode", "AAAAAAAA", casefold=_RaisingFlag(), map01="LL")
    _assert_same("b32decode", "AAAAAAAA", casefold=_RaisingFlag())
    assert _outcome(compat.b32decode, "AAAAAAAA", casefold=_RaisingFlag()) == (RuntimeError, ("flag looked at",))


def test_stdlib_quirks_are_kept() -> None:
    """Nonzero pad bits pass and a strided view is copied: the stdlib's calls, not ours."""
    assert compat.b32decode("IF======") == base64.b32decode("IF======") == b"A"
    assert compat.b32decode("IEAAAAA=") == base64.b32decode("IEAAAAA=") == b"A\x00\x00\x00"
    assert compat.b16decode(memoryview(b"AABBCCDD")[::2]) == b"\xab\xcd"
    assert compat.b32decode(memoryview(b"MxFxRxGxGx=x=x=x")[::2]) == base64.b32decode(b"MFRGG===") == b"abc"
    assert compat.b32hexdecode(memoryview(b"Cx4x=x=x=x=x=x=x")[::2]) == base64.b32hexdecode(b"C4======") == b"a"
    assert compat.b32encode(memoryview(b"abcdef")[::2]) == base64.b32encode(b"ace")
    assert compat.b32decode("AAAAAAA1", map01="=") == base64.b32decode("AAAAAAA1", map01="=") == b"\x00\x00\x00\x00"
