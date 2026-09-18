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

import array
import base64
import binascii
import decimal
import functools
import gc
import inspect
import io
import pickle  # ruff: ignore[suspicious-pickle-import] -- PickleBuffer is the stdlib's buffer exporter
import random
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
    expected = [
        "a85decode",
        "a85encode",
        "b16decode",
        "b16encode",
        "b32decode",
        "b32encode",
        "b32hexdecode",
        "b32hexencode",
        "b64decode",
        "b64encode",
        "b85decode",
        "b85encode",
        "decode",
        "decodebytes",
        "encode",
        "encodebytes",
        "standard_b64decode",
        "standard_b64encode",
        "urlsafe_b64decode",
        "urlsafe_b64encode",
    ]
    if sys.version_info >= (3, 13):
        expected += ["z85decode", "z85encode"]  # pyright: ignore[reportUnreachable]
    assert expected == PORTED


def test_all_matches_the_stdlib() -> None:
    assert sorted(compat.__all__) == sorted(STDLIB_ALL)


@pytest.mark.parametrize("name", PORTED)
def test_signatures_match_the_stdlib(name: str) -> None:
    assert inspect.signature(_ours(name)) == inspect.signature(_theirs(name))


def test_nothing_is_left_to_the_stdlib() -> None:
    """The drop-in is complete; a name that fell back to the standard library would show up here."""
    assert sorted(PORTED) == sorted(STDLIB_ALL)


# The legacy four take a bytestring or a pair of files, so the sample table below does not fit them.
LEGACY = ("encode", "decode", "encodebytes", "decodebytes")


def test_legacy_keyword_calls_match_the_stdlib() -> None:
    """input, output and s are keyword names in the stdlib, so they are here too."""
    _assert_same("encodebytes", s=b"abc")
    _assert_same("decodebytes", s=b"YWJj\n")
    for name in ("encode", "decode"):
        payload = b"abc" if name == "encode" else b"YWJj\n"
        ours, theirs = io.BytesIO(), io.BytesIO()
        assert _ours(name)(input=io.BytesIO(payload), output=ours) is None
        assert _theirs(name)(input=io.BytesIO(payload), output=theirs) is None
        assert ours.getvalue() == theirs.getvalue()


@pytest.mark.parametrize("name", [name for name in PORTED if name not in LEGACY])
def test_keyword_calls_match_the_stdlib(name: str) -> None:
    """Every parameter the stdlib takes by name, the port takes by name, with the same result."""
    parameters = inspect.signature(_theirs(name)).parameters
    kinds = {p.kind for p in parameters.values()}
    assert kinds <= {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    encoded = {
        "b16": b"4142",
        "b32": b"IE======",
        "b32hex": b"88======",
        "b64": b"QQ==",
        "standard_b64": b"QQ==",
        "urlsafe_b64": b"QQ==",
        "a85": b"5l",
        "b85": b"K>",
        "z85": b"k@",
    }
    samples: dict[str, object] = {
        "s": encoded[name[:-6]],
        "b": encoded[name[:-6]],
        "casefold": True,
        "map01": "L",
        "altchars": b"-_",
        "validate": True,
        "foldspaces": True,
        "wrapcol": 3,
        "pad": True,
        "adobe": False,
        "ignorechars": b" ",
    }
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
    # bytes == bytearray, so the equality above would let a bytearray result through; the stdlib returns bytes.
    assert type(ours[1]) is type(theirs[1])


class _RaisingFlag:
    """A flag that raises when looked at, to pin where in the argument order the stdlib reads it."""

    def __bool__(self) -> bool:
        message = "flag looked at"
        raise RuntimeError(message)

    def __index__(self) -> int:  # 3.11 reads b64decode's validate through __index__, not __bool__
        return int(self.__bool__())


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
_TEXT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=01abcdefghijklmnopqrstuvwxyz \n\t!~\x00\xff+/-_*$"
# The 85 family: its own alphabets, the z and y shorthands, the Adobe frame, whitespace, and what is outside.
_TEXT_CHARS_85 = (
    "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
    "zy<> \t\n\r\v\x0c\x00\x7f\xff"
)
_ENCODED_LIKE_85: st.SearchStrategy[str] = st.one_of(
    st.text(alphabet=_TEXT_CHARS_85, max_size=40),
    st.binary(max_size=25).map(lambda data: base64.a85encode(data).decode()),
    st.binary(max_size=25).map(lambda data: base64.a85encode(data, adobe=True, foldspaces=True).decode()),
    st.binary(max_size=25).map(lambda data: base64.b85encode(data).decode()),
    st.binary(max_size=25).map(lambda data: base64.a85encode(data).decode()).flatmap(_mutated),
    st.binary(max_size=25).map(lambda data: base64.b85encode(data).decode()).flatmap(_mutated),
)
_ENCODED_LIKE: st.SearchStrategy[str] = st.one_of(  # nine strategies: one_of would infer Any
    st.text(alphabet=_TEXT_CHARS, max_size=40),
    st.binary(max_size=25).map(lambda data: base64.b32encode(data).decode()),
    st.binary(max_size=25).map(lambda data: base64.b32hexencode(data).decode()),
    st.binary(max_size=20).map(lambda data: base64.b16encode(data).decode()),
    st.binary(max_size=25).map(lambda data: base64.b64encode(data).decode()),
    st.binary(max_size=25).map(lambda data: base64.urlsafe_b64encode(data).decode()),
    st.binary(max_size=25).map(lambda data: base64.b32encode(data).decode()).flatmap(_mutated),
    st.binary(max_size=20).map(lambda data: base64.b16encode(data).decode()).flatmap(_mutated),
    st.binary(max_size=25).map(lambda data: base64.b64encode(data).decode()).flatmap(_mutated),
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
_DECODE_INPUTS_85 = st.one_of(
    _ENCODED_LIKE_85,
    _ENCODED_LIKE_85.map(lambda text: text.encode("latin-1")),
    _ENCODED_LIKE_85.map(lambda text: bytearray(text.encode("latin-1"))),
    _ENCODED_LIKE_85.map(lambda text: memoryview(text.encode("latin-1"))),
    st.binary(max_size=40).map(lambda data: memoryview(data)[::2]),
    st.text(max_size=8),
    _HOSTILE_OBJECTS,
)
_WRAPCOL = st.sampled_from([0, 1, 2, 3, 5, 76, 1000, True, False, None, "x", "", 3.0, -1, 2**70, _RaisingFlag()])
_IGNORECHARS = st.sampled_from(
    [
        None,
        b" \t\n\r\v",
        b"",
        b"z",
        b"y",
        b"u",
        bytearray(b" "),
        memoryview(b" \n"),
        "x",
        " ",
        5,
        [32, 10],
        {32},
        b"\xff",
    ]
)
_MAP01 = st.sampled_from(
    [None, "L", "I", b"l", b"I", "LL", "", 5, "\xe9", bytearray(b"O"), "=", b"=", bytearray(b"ab"), memoryview(b"ab")]
)
# What b64decode's altchars goes through: _bytes_from_decode_data, so a str is fine and non-ASCII is not.
_DECODE_ALTCHARS = st.sampled_from(
    [
        None,
        b"-_",
        "-_",
        b"*$",
        b"+/",
        b"/+",
        b"--",
        b"=A",
        b"A=",
        b"",
        b"abc",
        "\xe9",
        5,
        bytearray(b"-_"),
        memoryview(b"*$"),
    ]
)
# What b64encode's altchars goes through: len() on the object itself, then the buffer protocol.
_ENCODE_ALTCHARS = st.sampled_from(
    [None, b"-_", b"*$", b"+/", b"/+", b"==", b"", b"abc", "-_", "", 5, bytearray(b"-_"), memoryview(b"*$")]
)


@settings(max_examples=2000)
@given(
    st.sampled_from(["b16encode", "b32encode", "b32hexencode", "b64encode", "standard_b64encode", "urlsafe_b64encode"]),
    _ENCODE_INPUTS,
)
def test_encoders_match(name: str, data: object) -> None:
    _assert_same(name, data)


@settings(max_examples=2000)
@given(_ENCODE_INPUTS, _FLAGS, _WRAPCOL, _FLAGS, _FLAGS)
def test_a85encode_matches(data: object, foldspaces: object, wrapcol: object, pad: object, adobe: object) -> None:
    _assert_same("a85encode", data, foldspaces=foldspaces, wrapcol=wrapcol, pad=pad, adobe=adobe)


@settings(max_examples=3000)
@given(_DECODE_INPUTS_85, _FLAGS, _FLAGS, _IGNORECHARS)
def test_a85decode_matches(data: object, foldspaces: object, adobe: object, ignorechars: object) -> None:
    kwargs: dict[str, object] = {"foldspaces": foldspaces, "adobe": adobe}
    if ignorechars is not None:
        kwargs["ignorechars"] = ignorechars
    _assert_same("a85decode", data, **kwargs)


@settings(max_examples=2000)
@given(_ENCODE_INPUTS, _FLAGS)
def test_b85encode_matches(data: object, pad: object) -> None:
    _assert_same("b85encode", data, pad)
    _assert_same("b85encode", data, pad=pad)


@settings(max_examples=2000)
@given(st.sampled_from(sorted({"b85decode", "z85decode", "z85encode"} & set(PORTED))), _DECODE_INPUTS_85)
def test_fixed_shape_85_functions_match(name: str, data: object) -> None:
    _assert_same(name, data)


@settings(max_examples=2000)
@given(_ENCODE_INPUTS, _ENCODE_ALTCHARS)
def test_b64encode_altchars_matches(data: object, altchars: object) -> None:
    _assert_same("b64encode", data, altchars)
    _assert_same("b64encode", data, altchars=altchars)


@settings(max_examples=3000)
@given(_DECODE_INPUTS, _DECODE_ALTCHARS, _FLAGS)
def test_b64decode_matches(data: object, altchars: object, validate: object) -> None:
    _assert_same("b64decode", data, altchars, validate)
    _assert_same("b64decode", data, altchars=altchars, validate=validate)


@settings(max_examples=2000)
@given(st.sampled_from(["standard_b64decode", "urlsafe_b64decode"]), _DECODE_INPUTS)
def test_fixed_alphabet_b64decoders_match(name: str, data: object) -> None:
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


_PAIRS_PORTED = (
    ("encodebytes", "decodebytes"),
    ("b16encode", "b16decode"),
    ("b32encode", "b32decode"),
    ("b32hexencode", "b32hexdecode"),
    ("b64encode", "b64decode"),
    ("standard_b64encode", "standard_b64decode"),
    ("urlsafe_b64encode", "urlsafe_b64decode"),
    ("a85encode", "a85decode"),
    ("b85encode", "b85decode"),
    *((("z85encode", "z85decode"),) if sys.version_info >= (3, 13) else ()),
)


@given(st.binary(max_size=40))
def test_ported_round_trips_agree_with_the_stdlib(data: bytes) -> None:
    for encoder, decoder in _PAIRS_PORTED:
        encoded = _ours(encoder)(data)
        assert encoded == _theirs(encoder)(data)
        assert _ours(decoder)(encoded) == data
        assert _theirs(decoder)(encoded) == data


def test_ported_pairs_agree_on_a_megabyte() -> None:
    """Multi-MB input through every ported pair: the resize path of the lenient decoders, and a MIME-shaped text."""
    payload = random.Random(2**20).randbytes(2**20)
    for encoder, decoder in _PAIRS_PORTED:
        encoded = _theirs(encoder)(payload)
        assert _ours(encoder)(payload) == encoded
        assert _ours(decoder)(encoded) == payload
    wrapped = base64.encodebytes(payload)  # 76-character lines, the shape b64decode discards newlines from
    assert wrapped.count(b"\n") > 10_000
    _assert_same("b64decode", wrapped)
    _assert_same("b64decode", wrapped, validate=True)
    _assert_same("standard_b64decode", wrapped)
    _assert_same("urlsafe_b64decode", wrapped)
    _assert_same("encodebytes", payload)
    _assert_same("decodebytes", base64.encodebytes(payload))
    # A length that is a nonzero multiple of the line's 57 bytes is the boundary of the one-shot allocation.
    for lines in (1, 2, 17):
        _assert_same("encodebytes", b"a" * (57 * lines))
        _assert_same("encodebytes", bytearray(b"b" * (57 * lines)))
    for name in ("encode", "decode"):
        source = payload if name == "encode" else base64.encodebytes(payload)
        ours, theirs = io.BytesIO(), io.BytesIO()
        assert _ours(name)(io.BytesIO(source), ours) is None
        assert _theirs(name)(io.BytesIO(source), theirs) is None
        assert ours.getvalue() == theirs.getvalue()
    _assert_same("b64decode", b"=" * 2**20 + base64.b64encode(payload))
    _assert_same("b64decode", base64.b64encode(payload) + b"=" * 2**20)
    zeros = bytes(2**20)
    for kwargs in ({}, {"foldspaces": True}, {"adobe": True, "wrapcol": 76}, {"pad": True}):
        _assert_same("a85encode", payload, **kwargs)
        _assert_same("a85encode", zeros, **kwargs)
    _assert_same("a85decode", base64.a85encode(payload, adobe=True, wrapcol=76), adobe=True)
    _assert_same("a85decode", b"z" * 2**20)
    _assert_same("a85decode", b" " * 2**20 + base64.a85encode(payload))
    _assert_same("b85decode", b"~" * 2**20)


@pytest.mark.parametrize("name", [name for name in PORTED if name not in LEGACY])
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
        ((b"",), {"altchar": b"-_"}),
        ((b"",), {"Validate": True}),
        ((b"", b"", b"", b""), {"validate": True}),  # b64decode: multiple values for validate, not too many
        ((b"", True), {"foldspaces": True}),  # a85: keyword-only, so the positional is one too many
        ((b"",), {"foldspace": True}),
        ((b"",), {"wrapcols": 3}),
        ((b"",), {"ignorechar": b" "}),
    ]
    # A keyword only some functions take is unexpected for every other; the same argument twice is refused by all.
    takers = {
        "map01": {"b32decode"},
        "altchars": {"b64encode", "b64decode"},
        "validate": {"b64decode"},
        "foldspaces": {"a85encode", "a85decode"},
        "wrapcol": {"a85encode"},
        "pad": {"a85encode", "b85encode"},
        "ignorechars": {"a85decode"},
    }
    samples: dict[str, object] = {
        "map01": "L",
        "altchars": b"-_",
        "validate": True,
        "foldspaces": True,
        "wrapcol": 3,
        "pad": True,
        "ignorechars": b" ",
    }
    shapes += [((b"",), {keyword: samples[keyword]}) for keyword, names in takers.items() if name not in names]
    if name in {"a85encode", "a85decode"}:
        shapes.append(((b"", False), {}))  # the second positional is keyword-only
    if name == "b85encode":
        shapes.append(((b"", True, True), {}))
    for args, kwargs in shapes:
        _assert_same(name, *args, **kwargs)
        assert _outcome(_ours(name), *args, **kwargs)[0] is TypeError, (name, args, kwargs)
    assert _outcome(compat.b32decode, b"", map01="L") == (_Ok, b"")
    assert _outcome(compat.b64decode, b"", altchars=b"-_", validate=True) == (_Ok, b"")
    assert _outcome(compat.b64encode, b"", altchars=b"-_") == (_Ok, b"")
    assert _outcome(compat.a85encode, b"", foldspaces=True, wrapcol=3, pad=True, adobe=True) == (_Ok, b"<~\n~>")
    assert _outcome(compat.a85decode, b"", foldspaces=True, adobe=False, ignorechars=b"") == (_Ok, b"")
    padded = True
    assert _outcome(compat.b85encode, b"", padded) == (_Ok, b"")


class _ClassLiar:
    """An object whose __class__ is not its type; the stdlib names the former."""

    @property
    def __class__(self) -> type[int]:  # pyright: ignore[reportIncompatibleMethodOverride, reportImplicitOverride]
        return int


# Subclassing str is the subject here, so UserString is not a substitute.
@typing.final
class _OwnEncode(str):  # ruff: ignore[subclass-builtin]
    """A str subclass whose encode the stdlib uses and the port must not skip."""

    __slots__ = ()

    # pyright wants @override, which needs 3.12; the project floor is 3.11.
    def encode(self, *_args: object, **_kwargs: object) -> bytes:  # ruff: ignore[no-self-use]  # pyright: ignore[reportImplicitOverride]
        return b"4142"


@typing.final
class _RaisingEncode(str):  # ruff: ignore[subclass-builtin]
    """A str subclass whose encode fails with something other than UnicodeEncodeError."""

    __slots__ = ()

    # pyright wants @override, which needs 3.12; the project floor is 3.11.
    def encode(self, *_args: object, **_kwargs: object) -> bytes:  # ruff: ignore[no-self-use]  # pyright: ignore[reportImplicitOverride]
        message = "no encode today"
        raise RuntimeError(message)


class _StrProxy:
    """A lazy proxy that reports str as its class, the shape werkzeug and django ship."""

    def __init__(self, value: str) -> None:
        self._value: str = value

    @property
    def __class__(self) -> type[str]:  # pyright: ignore[reportIncompatibleMethodOverride, reportImplicitOverride]
        return str

    def __getattr__(self, name: str) -> object:
        return getattr(self._value, name)  # pyright: ignore[reportAny]


@typing.final
class _BareStrClaim:
    """Claims str as its class and has nothing else; the stdlib trips over the missing encode."""

    # Lying about __class__ is the point of this class, so the checker's objection is the behaviour.
    __class__: type = str  # pyright: ignore[reportIncompatibleMethodOverride]


@pytest.mark.parametrize(
    "make",
    [
        lambda: _OwnEncode("ZZZZZZZZ"),
        lambda: _OwnEncode("MZXW6YTB"),
        lambda: _RaisingEncode("4142"),
        lambda: _StrProxy("4142"),
        lambda: _StrProxy("MZXW6YTB"),
        _BareStrClaim,
        lambda: _OwnEncode("\xe9"),
    ],
)
def test_str_like_inputs_go_through_encode(make: Callable[[], object]) -> None:
    """The stdlib dispatches on isinstance(s, str) and uses s.encode, so a subclass or proxy decides the bytes."""
    for name in ("b16decode", "b32decode", "b32hexdecode", "b64decode", "standard_b64decode", "urlsafe_b64decode"):
        _assert_same(name, make())
    for name in sorted({"a85decode", "b85decode", "z85decode"} & set(PORTED)):
        _assert_same(name, make())
    for name in ("encodebytes", "decodebytes"):
        _assert_same(name, make())
    _assert_same("b32decode", "AAAAAAAA", map01=make())
    _assert_same("b64decode", "AAAA", altchars=make())


def _context_shape(function: Callable[..., object], *args: object) -> tuple[type, type, bool]:
    try:
        function(*args)
    except Exception as error:  # ruff: ignore[blind-except] -- the exception chain is the subject
        return (type(error), type(error.__context__), error.__suppress_context__)
    message = "expected an exception"
    raise AssertionError(message)


class _ClearingFlag:
    """A flag whose truth test empties the bytearray being decoded."""

    def __init__(self, target: bytearray) -> None:
        self.target: bytearray = target

    def __bool__(self) -> bool:
        self.target.clear()
        return False

    def __index__(self) -> int:  # 3.11 reads b64decode's validate through __index__, not __bool__
        return int(self.__bool__())


def test_resizing_hook_is_refused_not_read() -> None:
    """The port holds the buffer across the hooks, so a resize is a BufferError; the stdlib reads what is left."""
    for name, encoded in (("b16decode", b"4142"), ("b32decode", b"IE======"), ("b32hexdecode", b"88======")):
        ours = bytearray(encoded)
        assert _outcome(_ours(name), ours, casefold=_ClearingFlag(ours))[0] is BufferError
        theirs = bytearray(encoded)
        assert _outcome(_theirs(name), theirs, casefold=_ClearingFlag(theirs)) == (_Ok, b"")


def test_b64decode_hooks_meet_the_buffer_where_the_stdlib_holds_it() -> None:
    """The stdlib holds s while it reads validate, so both sides refuse a resize; altchars copies first, on both."""
    ours, theirs = _ours("b64decode"), _theirs("b64decode")
    for make in (_ClearingFlag, _MutatingFlag):
        mine, yours = bytearray(b"QUJD"), bytearray(b"QUJD")
        assert _outcome(ours, mine, validate=make(mine)) == _outcome(theirs, yours, validate=make(yours))
    mine, yours = bytearray(b"QUJD"), bytearray(b"QUJD")
    assert _outcome(ours, mine, validate=_ClearingFlag(mine))[0] is BufferError
    assert _outcome(theirs, yours, validate=_ClearingFlag(yours))[0] is BufferError
    mine = bytearray(b"QUJD")
    assert ours(mine, validate=_MutatingFlag(mine)) == b"\x00\x00\x00"  # the live buffer, rewritten by the hook
    for make in (_ClearingFlag, _MutatingFlag):
        mine, yours = bytearray(b"QUJD"), bytearray(b"QUJD")
        assert ours(mine, altchars=b"-_", validate=make(mine)) == b"ABC"
        assert theirs(yours, altchars=b"-_", validate=make(yours)) == b"ABC"


def _raise_ambient() -> None:
    message = "ambient failure"
    raise ValueError(message)


def _chain_shape(call: Callable[[], object]) -> tuple[type, type, bool]:
    """Return the exception chain as a traceback would show it, from inside a live except block."""
    try:
        try:
            _raise_ambient()
        except ValueError:
            call()
    except Exception as error:  # ruff: ignore[blind-except] -- the exception chain is the subject
        return (type(error), type(error.__context__), error.__suppress_context__)
    message = "expected an exception"
    raise AssertionError(message)


@pytest.mark.parametrize(
    ("name", "args", "kwargs"),
    [
        ("b32decode", (b"!!!!!!!!",), {}),
        ("b32hexdecode", (b"!!!!!!!!",), {}),
        ("b32decode", (b"mmmmmmm!",), {"casefold": True}),
        ("b32decode", (b"01111111",), {"map01": b"9"}),
        ("b32decode", (b"AAA",), {}),
        ("b16decode", (b"ZZ",), {}),
        ("b16decode", (b"414",), {}),
        ("b16decode", (42,), {}),
        ("b32encode", (42,), {}),
        ("b16encode", (42,), {}),
        ("b64decode", (b"!!!!",), {"validate": True}),
        ("b64decode", (b"AAA",), {}),
        ("b64decode", (b"A",), {}),
        ("b64decode", (42,), {}),
        ("b64decode", (b"AAAA", "***"), {}),
        ("b64decode", (b"AAAA", "\xe9"), {}),
        ("b64encode", (42,), {}),
        ("b64encode", (b"", "*$"), {}),
        ("b64encode", (b"", b"***"), {}),
        ("b64encode", (b"", 5), {}),
        ("standard_b64decode", ("\xe9",), {}),
        ("urlsafe_b64decode", (42,), {}),
        ("urlsafe_b64encode", ("x",), {}),
        ("b85decode", (b"~",), {}),  # the struct.error behind the overflow, hidden
        ("b85decode", (b"0000 0",), {}),  # the TypeError behind the bad character, hidden
        ("b85decode", (42,), {}),
        ("b85encode", ("x",), {}),
        ("a85decode", (b"uuuuu",), {}),
        ("a85decode", (b"!!z",), {}),
        ("a85decode", (b"\x80",), {}),
        ("a85decode", (b"abc",), {"adobe": True}),
        ("a85decode", (b"!!",), {"ignorechars": "x", "adobe": True}),
        ("a85decode", (b" ",), {"ignorechars": "x"}),
        ("a85encode", (b"abc",), {"wrapcol": "x"}),
        ("a85encode", (b"abc",), {"wrapcol": 3.0}),
        ("a85encode", (42,), {}),
        ("encodebytes", (42,), {}),  # the memoryview TypeError rides along as the cause
        ("encodebytes", ("text",), {}),
        ("decodebytes", (42,), {}),
        ("decodebytes", (memoryview(b"abcdef")[::2],), {}),
        ("encodebytes", (memoryview(b"1234").cast("I"),), {}),
        ("encodebytes", (memoryview(b"1234").cast("B", (2, 2)),), {}),
    ],
)
def test_exception_chains_match(name: str, args: tuple[object, ...], kwargs: dict[str, object]) -> None:
    """Where the stdlib writes `raise ... from None`, the port must hide its context too, or tracebacks differ."""
    ours = _chain_shape(functools.partial(_ours(name), *args, **kwargs))
    theirs = _chain_shape(functools.partial(_theirs(name), *args, **kwargs))
    assert ours == theirs, (name, args, kwargs)


class _MutatingFlag:
    """A flag whose truth test rewrites the bytearray without changing its length."""

    def __init__(self, target: bytearray) -> None:
        self.target: bytearray = target

    def __bool__(self) -> bool:
        self.target[:] = b"A" * len(self.target)
        return False

    def __index__(self) -> int:  # 3.11 reads b64decode's validate through __index__, not __bool__
        return int(self.__bool__())


def test_map01_snapshots_where_the_stdlib_snapshots() -> None:
    """With map01 the stdlib decodes its translate() copy, so a hook's later edit reaches only the port."""
    ours = bytearray(b"MZXW6YTB")
    theirs = bytearray(b"MZXW6YTB")
    assert _ours("b32decode")(ours, casefold=_MutatingFlag(ours), map01=b"I") == b"\x00\x00\x00\x00\x00"
    assert _theirs("b32decode")(theirs, casefold=_MutatingFlag(theirs), map01=b"I") == b"fooba"
    # Without map01 the stdlib reads the live bytearray too, and both sides agree again.
    for name in ("b16decode", "b32decode", "b32hexdecode"):
        mine = bytearray(b"MZXW6YTB")
        yours = bytearray(b"MZXW6YTB")
        assert _ours(name)(mine, casefold=_MutatingFlag(mine)) == _theirs(name)(yours, casefold=_MutatingFlag(yours))


def _chain(function: Callable[..., object], *args: object, **kwargs: object) -> tuple[object, ...]:
    """Return the exception and its hidden context down to the message text, as a debugger shows them."""
    try:
        function(*args, **kwargs)
    except Exception as error:  # ruff: ignore[blind-except] -- the exception chain is the subject
        context = error.__context__
        return (type(error), error.args, type(context), context.args if context else None, error.__suppress_context__)
    message = "expected an exception"
    raise AssertionError(message)


@pytest.mark.parametrize("name", LEGACY)
def test_legacy_wrong_argument_shapes_match(name: str) -> None:
    """Too many, missing, unknown and duplicate arguments raise the stdlib's TypeError, text included."""
    files = name in {"encode", "decode"}
    sample: tuple[object, ...] = (io.BytesIO(b""), io.BytesIO()) if files else (b"",)
    shapes: list[tuple[tuple[object, ...], dict[str, object]]] = [
        ((), {}),
        ((*sample, b""), {}),
        ((*sample,), {"nope": 1}),
        ((*sample,), {"s": b""}),
        ((*sample,), {"input": io.BytesIO(b"")}),
        ((*sample,), {"output": io.BytesIO()}),
    ]
    extra: list[tuple[tuple[object, ...], dict[str, object]]] = (
        [
            ((io.BytesIO(b""),), {}),  # output is missing
            ((), {"s": b""}),
            ((), {"input": io.BytesIO(b"")}),  # output is missing, input bound by name
            ((), {"output": io.BytesIO()}),
        ]
        if files
        else [((), {"input": b""})]
    )
    shapes += extra
    for args, kwargs in shapes:
        _assert_same(name, *args, **kwargs)
        assert _outcome(_ours(name), *args, **kwargs)[0] is TypeError, (name, args, kwargs)


class _RaisingWrite(io.BytesIO):
    """An output file whose write fails, to pin that the port passes the failure on untouched."""

    # pyright wants @override, which needs 3.12; the project floor is 3.11.
    def write(self, _buffer: object, /) -> int:  # ruff: ignore[no-self-use]  # pyright: ignore[reportImplicitOverride]
        message = "no write today"
        raise RuntimeError(message)


class _ShortReads:
    """A file whose reads stop short of the line size, so the port must top the chunk up as the stdlib does."""

    def __init__(self, pieces: list[object]) -> None:
        self.pieces: list[object] = list(pieces)

    def read(self, _size: int) -> object:
        return self.pieces.pop(0) if self.pieces else b""


class _SizedReads:
    """A file that honours the size it is asked for and records every ask, the way a pipe or a socket does."""

    def __init__(self, data: bytes, most: int) -> None:
        self.data: bytes = data
        self.most: int = most
        self.asks: list[int] = []

    def read(self, size: int) -> bytes:
        self.asks.append(size)
        taken = self.data[: min(size, self.most)]
        self.data = self.data[len(taken) :]
        return taken


@pytest.mark.parametrize("most", [1, 7, 56, 57, 58, 100])
@pytest.mark.parametrize("length", [0, 1, 56, 57, 58, 114, 200])
def test_encode_asks_for_the_same_bytes_as_the_stdlib(most: int, length: int) -> None:
    """The top-up read asks for what is still missing, so the lines stay 76 characters on a short-reading file."""
    ours, theirs = _SizedReads(b"a" * length, most), _SizedReads(b"a" * length, most)
    out_ours, out_theirs = io.BytesIO(), io.BytesIO()
    assert _ours("encode")(ours, out_ours) is None
    assert _theirs("encode")(theirs, out_theirs) is None
    assert ours.asks == theirs.asks
    assert out_ours.getvalue() == out_theirs.getvalue()


# Fresh pieces per call: `s += ns` mutates a bytearray in place, so the two runs must not share one.
@pytest.mark.parametrize(
    "make",
    [
        lambda: [b"abc", b"de"],
        lambda: [b"a" * 57, b"b" * 57],
        lambda: [b"a" * 56, b"b"],
        lambda: [b"a" * 100],
        lambda: [b"", b"never read"],
        lambda: [bytearray(b"ab"), bytearray(b"cd")],
        lambda: [memoryview(b"abc")],
        lambda: [b"ab", memoryview(b"cd")],
    ],
    ids=lambda make: repr(make()),  # pyright: ignore[reportAny]
)
def test_encode_tops_up_short_reads_like_the_stdlib(make: Callable[[], list[object]]) -> None:
    ours, theirs = io.BytesIO(), io.BytesIO()
    assert _outcome(_ours("encode"), _ShortReads(make()), ours) == _outcome(
        _theirs("encode"), _ShortReads(make()), theirs
    )
    assert ours.getvalue() == theirs.getvalue()


def test_legacy_files_pass_their_own_failures_on() -> None:
    """A read, a write or a line that fails is the file's error, not reworded."""
    assert _outcome(_ours("encode"), io.BytesIO(b"abc"), _RaisingWrite()) == _outcome(
        _theirs("encode"), io.BytesIO(b"abc"), _RaisingWrite()
    )
    assert _outcome(_ours("decode"), io.BytesIO(b"YWJj\n"), _RaisingWrite()) == _outcome(
        _theirs("decode"), io.BytesIO(b"YWJj\n"), _RaisingWrite()
    )
    for missing in (object(), None, 42):
        assert _outcome(_ours("encode"), missing, io.BytesIO()) == _outcome(_theirs("encode"), missing, io.BytesIO())
        assert _outcome(_ours("decode"), missing, io.BytesIO()) == _outcome(_theirs("decode"), missing, io.BytesIO())


@pytest.mark.parametrize(
    ("text", "binary"),
    [(io.StringIO, io.BytesIO), (io.BytesIO, io.StringIO), (io.StringIO, io.StringIO)],
    ids=repr,
)
def test_legacy_text_files_match(text: Callable[..., object], binary: Callable[..., object]) -> None:
    """A text file on either side is the stdlib's TypeError, or its ValueError for non-ASCII input."""
    for name, payload in (("encode", "abc"), ("decode", "eA==\n")):
        for maker, other in ((text, binary), (binary, text)):
            ours = _outcome(_ours(name), maker(payload if maker is io.StringIO else payload.encode()), other())
            theirs = _outcome(_theirs(name), maker(payload if maker is io.StringIO else payload.encode()), other())
            assert ours == theirs, (name, maker, other)
    assert _outcome(_ours("decode"), io.StringIO("\xe9\n"), io.BytesIO()) == _outcome(
        _theirs("decode"), io.StringIO("\xe9\n"), io.BytesIO()
    )


_LONG_NAMED = typing.cast("type[object]", type("L" * 250, (), {}))


@typing.final
class _RaisingClassBytes(bytes):
    """A buffer whose __class__ raises; the stdlib reads __class__ only when it is about to raise."""

    __slots__ = ()

    @property
    def __class__(self) -> type:  # pyright: ignore[reportIncompatibleMethodOverride, reportImplicitOverride]
        message = "class lookup ran"
        raise RuntimeError(message)


@typing.final
class _ZeroLen(bytes):
    """A buffer whose __len__ says zero, so the stdlib's chunk loop never runs."""

    __slots__ = ()

    def __len__(self) -> int:  # pyright: ignore[reportImplicitOverride]
        return 0


@typing.final
class _LongLen(bytes):
    """A buffer whose __len__ overstates it, so the stdlib asks for slices past its end."""

    __slots__ = ()

    def __len__(self) -> int:  # pyright: ignore[reportImplicitOverride]
        return 200


@typing.final
class _Slicer(bytes):
    """A buffer whose slices are not its own bytes, which is what the stdlib encodes."""

    __slots__ = ()

    def __getitem__(self, key: object) -> bytes:  # pyright: ignore[reportImplicitOverride, reportIncompatibleMethodOverride]
        return b"ZZZ"


@pytest.mark.parametrize(
    "make",
    [
        lambda: _RaisingClassBytes(b"abcdef"),
        lambda: _ZeroLen(b"abcdef"),
        lambda: _LongLen(b"abcdef"),
        lambda: _Slicer(b"abcdef"),
        lambda: pickle.PickleBuffer(b"A" * 100),
        lambda: pickle.PickleBuffer(b""),
    ],
    ids=["raising-class", "zero-len", "long-len", "slicer", "picklebuffer", "empty-picklebuffer"],
)
def test_legacy_reads_the_object_where_the_stdlib_reads_it(make: Callable[[], object]) -> None:
    """len(), the slices and __class__ are the stdlib's, not the buffer's, so these must agree exactly."""
    _assert_same("encodebytes", make())
    _assert_same("decodebytes", make())


class _LongNamedLine:
    """A file whose line is an instance of a 250-character type, the name binascii cuts at 100 characters."""

    def readline(self) -> object:  # ruff: ignore[no-self-use]
        return _LONG_NAMED()


@typing.final
class _CountingLen(bytes):
    """A chunk that counts how often its length is asked for; the stdlib asks twice per top-up round."""

    __slots__ = ()
    calls: typing.ClassVar[int] = 0

    def __len__(self) -> int:  # pyright: ignore[reportImplicitOverride]
        type(self).calls += 1
        return bytes.__len__(self)


class _CountingReads:
    """A file whose reads hand back _CountingLen chunks, so len(s) calls are observable."""

    def __init__(self) -> None:
        self.reads: int = 0

    def read(self, _size: int) -> bytes:
        self.reads += 1
        return _CountingLen(b"abc") if self.reads == 1 else (_CountingLen(b"de") if self.reads == 2 else b"")


def test_encode_asks_for_the_length_as_often_as_the_stdlib() -> None:
    """The stdlib's loop condition and its read size are two separate len(s) calls."""
    counts: list[int] = []
    for name in ("ours", "theirs"):
        _CountingLen.calls = 0
        function = _ours("encode") if name == "ours" else _theirs("encode")
        assert function(_CountingReads(), io.BytesIO()) is None
        counts.append(_CountingLen.calls)
    assert counts[0] == counts[1]


class _RecordingWrites(io.BytesIO):
    """A sink that remembers the size of every write, so streaming is observable, not just the total."""

    def __init__(self) -> None:
        super().__init__()
        self.sizes: list[int] = []

    def write(self, buffer: object, /) -> int:  # pyright: ignore[reportImplicitOverride]
        self.sizes.append(len(typing.cast("bytes", buffer)))
        return super().write(typing.cast("bytes", buffer))


@pytest.mark.parametrize("length", [0, 1, 57, 58, 200, 1000])
def test_legacy_files_write_one_line_at_a_time(length: int) -> None:
    """A batching port would pass on the joined output alone, so the write sizes are pinned too."""
    payload = b"a" * length
    for name, source in (("encode", payload), ("decode", base64.encodebytes(payload))):
        ours, theirs = _RecordingWrites(), _RecordingWrites()
        assert _ours(name)(io.BytesIO(source), ours) is None
        assert _theirs(name)(io.BytesIO(source), theirs) is None
        assert ours.sizes == theirs.sizes, (name, length)
        assert ours.getvalue() == theirs.getvalue()


@typing.final
class _RaisingClassObject:
    """Not a buffer, and its __class__ raises: the stdlib is still inside `except TypeError` when it does."""

    @property
    def __class__(self) -> type:  # pyright: ignore[reportIncompatibleMethodOverride, reportImplicitOverride]
        message = "class boom"
        raise RuntimeError(message)


@pytest.mark.parametrize("name", ["encodebytes", "decodebytes"])
def test_failing_class_lookup_keeps_the_memoryview_error_as_context(name: str) -> None:
    """The stdlib's rewording happens inside an except block, so its TypeError stays as the context."""
    assert _chain(_ours(name), _RaisingClassObject()) == _chain(_theirs(name), _RaisingClassObject())


def test_decode_writes_what_the_stdlib_writes_for_text_lines() -> None:
    """The ASCII-str branch of the buffer converter decodes the line's own bytes, not an empty slice."""
    for text in ("eA==\n", "YWJj\n", "", "\n", "Zm9vYmFy\n" * 3):
        ours, theirs = io.BytesIO(), io.BytesIO()
        assert _ours("decode")(io.StringIO(text), ours) is None
        assert _theirs("decode")(io.StringIO(text), theirs) is None
        assert ours.getvalue() == theirs.getvalue()
        assert ours.getvalue() == base64.b64decode(text.encode("ascii"))


@pytest.mark.parametrize(
    "make", [lambda: memoryview(bytes(1 << 18)), lambda: array.array("B", bytes(1 << 18))], ids=repr
)
def test_encodebytes_keeps_nothing_per_chunk(make: Callable[[], object]) -> None:
    """The slicing path builds two index objects per 57-byte chunk; holding them would grow without bound."""
    argument = make()
    encode = _ours("encodebytes")
    encode(argument)
    gc.collect()
    before = sys.getallocatedblocks()
    for _ in range(5):
        encode(argument)
    gc.collect()
    assert sys.getallocatedblocks() - before < 100  # one chunk per 57 bytes, so a leak would be thousands


def test_long_type_names_are_truncated_where_binascii_truncates() -> None:
    """The drop-in's message carries the same truncated name as binascii's, not a longer one."""
    ours = _outcome(_ours("decode"), _LongNamedLine(), io.BytesIO())
    assert ours == _outcome(_theirs("decode"), _LongNamedLine(), io.BytesIO())
    message = str(typing.cast("tuple[object, ...]", ours[1])[0])
    assert "L" * 100 in message
    assert "L" * 101 not in message


@pytest.mark.parametrize("make", [lambda: 5, list, lambda: 3.5, lambda: decimal.Decimal(1), _ClassLiar, _RaisingBuffer])
def test_hidden_context_carries_the_stdlib_words(make: Callable[[], object]) -> None:
    """The stdlib's suppressed context is memoryview()'s own TypeError, or the exporter's; so is the port's."""
    for name in ("b16decode", "b32decode", "b32hexdecode", "b64decode", "standard_b64decode", "urlsafe_b64decode"):
        assert _chain(_ours(name), make()) == _chain(_theirs(name), make()), name
    assert _chain(compat.b64decode, b"AAAA", altchars=make()) == _chain(base64.b64decode, b"AAAA", altchars=make())
    assert _chain(compat.b32decode, b"AAAAAAAA", map01=make()) == _chain(base64.b32decode, b"AAAAAAAA", map01=make())


def test_non_ascii_str_carries_the_stdlib_context() -> None:
    """The stdlib raises the ValueError inside `except UnicodeEncodeError`, so the traceback shows both."""
    for name in ("b16decode", "b32decode", "b32hexdecode", "b64decode", "standard_b64decode", "urlsafe_b64decode"):
        ours = _context_shape(_ours(name), "\xe9")
        assert ours == _context_shape(_theirs(name), "\xe9") == (ValueError, UnicodeEncodeError, False)
    assert _outcome(compat.b32decode, "", map01="\xe9")[0] is ValueError
    assert _outcome(compat.b64decode, "", altchars="\xe9")[0] is ValueError


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
    _assert_same("b64decode", "AAAA", altchars="abc")
    _assert_same("b64decode", "AAAA", altchars=b"")
    _assert_same("b64decode", "AAAA", altchars=bytearray(b"a"))
    _assert_same("b64decode", "AAAA", altchars=memoryview(b"abc"))
    if not sys.flags.optimize:  # -O strips the stdlib's assert, and maketrans raises instead
        assert _outcome(compat.b32decode, "AAAAAAAA", map01=bytearray(b"ab")) == (
            AssertionError,
            ("bytearray(b'ab')",),
        )
        assert _outcome(compat.b64decode, "AAAA", altchars="abc") == (AssertionError, ("b'abc'",))
        assert _outcome(compat.b64decode, "AAAA", altchars=bytearray(b"a")) == (AssertionError, ("bytearray(b'a')",))


@typing.final
class _TwoLong(bytes):
    """A bytes whose __len__ says two whatever the buffer holds; the stdlib's assert believes it."""

    __slots__ = ()

    def __len__(self) -> int:  # pyright: ignore[reportImplicitOverride]
        return 2


@typing.final
class _ThreeLong(bytes):
    """A bytes whose __len__ says three whatever the buffer holds."""

    __slots__ = ()

    def __len__(self) -> int:  # pyright: ignore[reportImplicitOverride]
        return 3


@typing.final
class _ByteArrayEncode(str):  # ruff: ignore[subclass-builtin]
    """A str whose encode hands back a bytearray, which the stdlib then asserts on and reprs as such."""

    __slots__ = ()

    def encode(self, *_args: object, **_kwargs: object) -> bytearray:  # ruff: ignore[no-self-use]  # pyright: ignore[reportImplicitOverride, reportIncompatibleMethodOverride]
        return bytearray(b"abc")


def test_length_assertions_judge_the_coerced_object() -> None:
    """The stdlib asserts len() and repr() of the coerced object; maketrans then judges the buffer."""
    _assert_same("b64decode", b"QUJD", altchars=_TwoLong(b"-_-"))  # the assert passes, maketrans refuses
    _assert_same("b64decode", b"QUJD", altchars=_ThreeLong(b"-_"))  # the assert fails on a fitting buffer
    _assert_same("b64decode", b"QUJD", altchars=_TwoLong(b"-_"))
    _assert_same("b64decode", b"QUJD", altchars=_ByteArrayEncode("x"))
    _assert_same("b32decode", "AAAAAAAA", map01=_TwoLong(b"L"))
    _assert_same("b32decode", "AAAAAAAA", map01=_ByteArrayEncode("x"))
    if not sys.flags.optimize:
        assert _outcome(compat.b64decode, b"QUJD", altchars=_ThreeLong(b"-_")) == (AssertionError, ("b'-_'",))
        assert _outcome(compat.b64decode, b"QUJD", altchars=_ByteArrayEncode("x")) == (
            AssertionError,
            ("bytearray(b'abc')",),
        )
    assert _outcome(compat.b64decode, b"QUJD", altchars=_TwoLong(b"-_-")) == (
        ValueError,
        ("maketrans arguments must have same length",),
    )
    assert _outcome(compat.b64decode, b"QUJD", altchars=_TwoLong(b"-_")) == (_Ok, b"ABC")


def test_b64encode_altchars_is_judged_as_the_stdlib_judges_it() -> None:
    """len() on the object itself, its repr in the assertion, then bytes.maketrans on the buffer."""
    _assert_same("b64encode", b"", altchars=b"***")
    _assert_same("b64encode", b"", altchars="*$")
    _assert_same("b64encode", b"", altchars="")
    _assert_same("b64encode", b"", altchars=5)
    _assert_same("b64encode", b"", altchars=bytearray(b"*"))
    _assert_same("b64encode", b"", altchars=[42, 43])
    _assert_same("b64encode", b"", altchars=memoryview(b"*$*$").cast("H"))
    if not sys.flags.optimize:
        assert _outcome(compat.b64encode, b"", altchars=b"***") == (AssertionError, ("b'***'",))
        assert _outcome(compat.b64encode, b"", altchars=5) == (TypeError, ("object of type 'int' has no len()",))
    assert _outcome(compat.b64encode, b"", altchars="*$")[0] is TypeError
    # Two items of two bytes each: the assertion passes and maketrans sees four bytes against two.
    assert _outcome(compat.b64encode, b"", altchars=memoryview(b"*$*$").cast("H")) == (
        ValueError,
        ("maketrans arguments must have same length",),
    )


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
        # Not assert: -O strips those from this script too, and the test could never fail.
        # Not == 1: PYTHONOPTIMIZE in the environment raises the child's level past the -O we pass.
        "if sys.flags.optimize < 1: raise SystemExit('optimize %r' % sys.flags.optimize)\n"
        "expected = ('ValueError', ('maketrans arguments must have same length',))\n"
        "if run(base64.b32decode) != expected: raise SystemExit('stdlib: %r' % (run(base64.b32decode),))\n"
        "if run(compat.b32decode) != expected: raise SystemExit('port: %r' % (run(compat.b32decode),))\n"
        "def run64(f, *args, **kwargs):\n"
        "    try:\n"
        "        f(*args, **kwargs)\n"
        "    except Exception as error:\n"
        "        return (type(error).__name__, error.args)\n"
        "for args, kwargs in (((b'AAAA',), {'altchars': 'abc'}), ((b'AAAA', b''), {})):\n"
        "    if run64(base64.b64decode, *args, **kwargs) != expected: raise SystemExit('stdlib b64decode')\n"
        "    if run64(compat.b64decode, *args, **kwargs) != expected: raise SystemExit('port b64decode')\n"
        # Without the assert the stdlib never calls len(altchars), so 5 fails in maketrans, not in len().
        "for altchars in (5, b'abc', 'ab'):\n"
        "    ours, theirs = run64(compat.b64encode, b'', altchars), run64(base64.b64encode, b'', altchars)\n"
        "    if ours != theirs: raise SystemExit('b64encode %r: %r != %r' % (altchars, ours, theirs))\n"
        "if run64(compat.b64encode, b'', 5) != ('TypeError', (\"a bytes-like object is required, not 'int'\",)):\n"
        "    raise SystemExit('b64encode under -O: %r' % (run64(compat.b64encode, b'', 5),))\n"
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
    _assert_same("b64decode", 42, validate=_RaisingFlag())
    _assert_same("b64decode", "\xe9", validate=_RaisingFlag())
    _assert_same("b64decode", b"AAAA", altchars="abc", validate=_RaisingFlag())
    _assert_same("b64decode", b"AAAA", altchars="\xe9", validate=_RaisingFlag())
    _assert_same("b64decode", b"", validate=_RaisingFlag())
    assert _outcome(compat.b64decode, b"AAAA", validate=_RaisingFlag()) == (RuntimeError, ("flag looked at",))
    # a85encode reads foldspaces at the first word that is not zero and pad only when the tail needs padding.
    _assert_same("a85encode", b"\0\0\0\0", foldspaces=_RaisingFlag())
    _assert_same("a85encode", b"\0\0\0\0\1", foldspaces=_RaisingFlag())
    _assert_same("a85encode", b"abcd", pad=_RaisingFlag())
    _assert_same("a85encode", b"abcde", pad=_RaisingFlag())
    _assert_same("a85encode", b"abcde", foldspaces=_RaisingFlag(), pad=_RaisingFlag())
    _assert_same("a85encode", 42, foldspaces=_RaisingFlag(), wrapcol=_RaisingFlag(), adobe=_RaisingFlag())
    _assert_same("a85encode", b"abc", wrapcol=_RaisingFlag(), adobe=_RaisingFlag())
    _assert_same("a85encode", b"abc", wrapcol=_RaisingFlag())
    _assert_same("b85encode", b"abcd", pad=_RaisingFlag())
    _assert_same("b85encode", b"abcde", pad=_RaisingFlag())
    # a85decode reads foldspaces at the first byte outside the alphabet that is not z, whitespace included.
    _assert_same("a85decode", b"!!!!!", foldspaces=_RaisingFlag())
    _assert_same("a85decode", b"!!!!! ", foldspaces=_RaisingFlag())
    _assert_same("a85decode", b"z", foldspaces=_RaisingFlag())
    _assert_same("a85decode", b"!!", foldspaces=_RaisingFlag(), adobe=_RaisingFlag())
    _assert_same("a85decode", 42, foldspaces=_RaisingFlag(), adobe=_RaisingFlag())
    assert _outcome(compat.a85decode, b"!!!!! ", foldspaces=_RaisingFlag()) == (RuntimeError, ("flag looked at",))
    assert _outcome(compat.a85encode, b"\0\0\0\0", foldspaces=_RaisingFlag()) == (_Ok, b"z")


def test_stdlib_quirks_are_kept() -> None:
    """Nonzero pad bits pass and a strided view is copied: the stdlib's calls, not ours."""
    assert compat.b32decode("IF======") == base64.b32decode("IF======") == b"A"
    assert compat.b32decode("IEAAAAA=") == base64.b32decode("IEAAAAA=") == b"A\x00\x00\x00"
    assert compat.b16decode(memoryview(b"AABBCCDD")[::2]) == b"\xab\xcd"
    assert compat.b32decode(memoryview(b"MxFxRxGxGx=x=x=x")[::2]) == base64.b32decode(b"MFRGG===") == b"abc"
    assert compat.b32hexdecode(memoryview(b"Cx4x=x=x=x=x=x=x")[::2]) == base64.b32hexdecode(b"C4======") == b"a"
    assert compat.b32encode(memoryview(b"abcdef")[::2]) == base64.b32encode(b"ace")
    assert compat.b32decode("AAAAAAA1", map01="=") == base64.b32decode("AAAAAAA1", map01="=") == b"\x00\x00\x00\x00"
    assert compat.b64decode(b"AB==") == base64.b64decode(b"AB==") == b"\x00"
    assert compat.b64decode(b"A A\nA A") == base64.b64decode(b"A A\nA A") == b"\x00\x00\x00"
    assert compat.b64decode(b"====") == base64.b64decode(b"====") == b""
    assert compat.urlsafe_b64decode(b"++//") == base64.urlsafe_b64decode(b"++//") == b"\xfb\xef\xff"
    assert compat.b64decode(b"AA=A", altchars=b"=A") == base64.b64decode(b"AA=A", altchars=b"=A") == b"\xff\xff\xbf"
    assert compat.b64decode(memoryview(b"QxUxJxDx")[::2]) == base64.b64decode(b"QUJD") == b"ABC"
    # The 85 family pads with its largest digit, so a lone character overflows rather than decoding to nothing.
    assert _outcome(compat.a85decode, b"u") == (ValueError, ("Ascii85 overflow",))
    assert _outcome(base64.a85decode, b"u") == (ValueError, ("Ascii85 overflow",))
    assert compat.a85decode(b"!!!!!!") == b"\0\0\0\0"  # one leftover character decodes to nothing
    assert base64.a85decode(b"!!!!!!") == b"\0\0\0\0"
    assert compat.a85decode(b"<~~>", adobe=True) == b""
    assert compat.a85decode(b"~>", adobe=True) == b""
    assert _outcome(compat.a85decode, b"y") == (ValueError, ("Non-Ascii85 digit found: y",))  # y is past u
    assert compat.a85decode(b"y", foldspaces=True) == b"    "
    assert compat.a85encode(b"", adobe=True, wrapcol=2) == b"<~\n~>"
    assert compat.a85encode(b"\0\0\0\0\0") == b"z!!"
    assert compat.a85encode(b"\0\0\0\0\0", pad=True) == b"zz"
    assert compat.b85encode(b"\0") == b"00"
    assert compat.b85decode(b"") == b""
    # b64encode is binascii's, which takes the buffer as is: a strided view is refused, not copied.
    assert _outcome(compat.b64encode, memoryview(b"abcdef")[::2])[0] is BufferError


# The releases where binascii.a2b_base64 changed, as sys.hexversion, and the reading each side must get.
_A2B_VARIANT_ROWS: dict[str, tuple[int, int]] = {
    "3.11.0": (0x030B00F0, 0),
    "3.11.15": (0x030B0FF0, 0),
    "3.12.0": (0x030C00F0, 0),
    "3.12.3": (0x030C03F0, 0),
    "3.12.4": (0x030C04F0, 1),
    "3.12.13": (0x030C0DF0, 1),
    "3.13.0": (0x030D00F0, 1),
    "3.13.12": (0x030D0CF0, 1),
    "3.13.13": (0x030D0DF0, 2),
    "3.14.0rc1": (0x030E00C1, 1),
    "3.14.3": (0x030E03F0, 1),
    "3.14.4": (0x030E04F0, 2),
    "3.15.0a1": (0x030F00A1, 2),
}


def _a2b_variant_of_the_stdlib() -> int:
    """Tell the three readings apart by two inputs they judge differently."""

    def outcome(data: bytes) -> str | None:
        try:
            binascii.a2b_base64(data, strict_mode=True)
        except binascii.Error as error:
            return str(error)
        return None

    if outcome(b"AAAA=") is None:
        return 0  # the padding ended the parse before it was judged
    return 1 if outcome(b"AA===") == "Excess data after padding" else 2


@pytest.mark.parametrize("release", list(_A2B_VARIANT_ROWS))
def test_a2b_variant_table(release: str) -> None:
    """The version boundaries the C selects on, pinned as data; no CI interpreter sits on one."""
    hexversion, variant = _A2B_VARIANT_ROWS[release]
    assert _core.a2b_base64_variant(hexversion) == variant


def test_a2b_variant_matches_the_running_stdlib() -> None:
    """The table's answer for this interpreter is what its binascii actually does."""
    assert _core.a2b_base64_variant(sys.hexversion) == _a2b_variant_of_the_stdlib()


# Every shape a2b_base64 judges differently between CPython lines; the port must follow the running one.
_A2B_EDGE_INPUTS = [
    b"=",
    b"==",
    b"====",
    b"AA==",
    b"AA===",
    b"AA==A",
    b"AA==AAAA",
    b"AA=A",
    b"A=A=",
    b"AAA=",
    b"AAA==",
    b"AAAA=",
    b"AAAA==",
    b"AAAA====",
    b"A",
    b"AA",
    b"AAA",
    b"AA=",
    b"A==",
    b"A===",
    b"A=",
    b"=A",
    b"AAAA",
    b"A A",
    b"AA=\n=",
    b"=AAA",
    b"AAAAA",
    b"AAAAAA==",
    b"AAAAA===",
    b"AAAAAA=",
    b"AAAAAAA=",
    b"AAAAAAA",
    b"AB==",
    b"AAB=",
    b"AA=AAA",
    b"AAAA=AAAA",
    b"AA==AAAA",
    b"\xff",
    b"\xffAAAA",
    b"+/",
    b"-_",
    b"AA=X",
    b"A=A",
    b"AAA=A",
    b"AAAA=A",
    b"AAAA==AA",
    b"AA==\n",
]


@pytest.mark.parametrize("data", _A2B_EDGE_INPUTS, ids=repr)
def test_a2b_base64_edge_table_matches_the_running_interpreter(data: bytes) -> None:
    """a2b_base64 changed in 3.12.4 and again in 3.13.13 and 3.14.4; the port picks its variant at import."""
    for validate in (False, True):
        _assert_same("b64decode", data, validate=validate)
        _assert_same("b64decode", data.decode("latin-1"), validate=validate)
    _assert_same("standard_b64decode", data)
    _assert_same("urlsafe_b64decode", data)
