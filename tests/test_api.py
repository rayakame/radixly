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
"""The root surface: DecodeError, the registry machinery, and the frozen Codec."""

from __future__ import annotations

import copy
import dataclasses
import pickle  # ruff: ignore[suspicious-pickle-import] -- tests pickle only their own objects
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed argv, own interpreter
import sys
import typing

import pytest

import radixly
from radixly import _codec
from radixly import _core
from tests.reference import errors as errors_reference


def test_decode_error_is_the_core_type() -> None:
    assert radixly.DecodeError is _core.DecodeError


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_decode_error_carries_notes_and_attributes(protocol: int) -> None:
    """Every codec raises this type; dropping the instance dict would lose add_note without a word."""
    original = _core.DecodeError(7, message="boom")
    original.add_note("came from worker 3")
    original.custom = 42  # pyright: ignore[reportAttributeAccessIssue]
    clone = pickle.loads(pickle.dumps(original, protocol))  # ruff: ignore[suspicious-pickle-usage]  # pyright: ignore[reportAny]
    views: tuple[_core.DecodeError, ...] = (clone, copy.copy(original), copy.deepcopy(original))
    for view in views:
        assert type(view) is _core.DecodeError
        assert (view.position, view.message, view.args) == (7, "boom", ("boom",))
        assert view.__notes__ == ["came from worker 3"]
        assert getattr(view, "custom", None) == 42


def test_decode_error_reduce_matches_the_reference() -> None:
    """The reference models the C type's pickle contract; a drift here makes every reference test a lie."""

    def shape(error: BaseException) -> object:
        error.add_note("note")
        reduced = typing.cast("tuple[object, ...]", error.__reduce__())
        return (reduced[1], reduced[2])

    assert shape(_core.DecodeError(3, message="m")) == shape(errors_reference.DecodeError(3, message="m"))


@pytest.mark.parametrize("factory", [_core.DecodeError, errors_reference.DecodeError])
def test_decode_error_setstate_rejects_a_bad_pair(factory: type[ValueError]) -> None:
    """Pickle state is attacker-controlled; both slots are checked, and the reference says the same."""
    for state, pattern in ((("nope", None), "args must be a tuple"), ((None, "nope"), "instance dict must be a dict")):
        with pytest.raises(TypeError, match=pattern):
            factory(0).__setstate__(state)  # pyright: ignore[reportArgumentType]


def test_get_codec_returns_the_registered_object() -> None:
    assert radixly.get_codec("base32768") is radixly.base32768.BASE32768


def test_get_codec_unknown_name() -> None:
    with pytest.raises(KeyError, match=r"unknown codec 'nope'.*registered:"):
        radixly.get_codec("nope")


def test_codecs_is_a_read_only_live_view() -> None:
    assert "base32768" in radixly.CODECS
    assert radixly.CODECS["base32768"] is radixly.get_codec("base32768")
    with pytest.raises(TypeError):
        radixly.CODECS["x"] = radixly.CODECS["base32768"]  # pyright: ignore[reportIndexIssue]


def test_register_refuses_duplicate_name() -> None:
    duplicate = dataclasses.replace(radixly.base32768.BASE32768)
    with pytest.raises(ValueError, match="already registered"):
        radixly.register(duplicate)


def test_register_fresh_name_appears_in_the_view() -> None:
    fresh = dataclasses.replace(radixly.base32768.BASE32768, name="fresh-test-codec")
    radixly.register(fresh)
    try:
        assert radixly.CODECS["fresh-test-codec"] is fresh
    finally:
        _codec._registry.pop("fresh-test-codec")  # pyright: ignore[reportPrivateUsage]


def test_codec_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        radixly.base32768.BASE32768.name = "other"  # pyright: ignore[reportAttributeAccessIssue]


EXPECTED_CODECS = [
    "base16",
    "base32",
    "base32hex",
    "base64",
    "base64url",
    "base85",
    "base2048",
    "base32768",
    "base65536",
    "braille",
    "hexagram",
    "uro14",
    "z85",
]


@pytest.mark.parametrize("name", EXPECTED_CODECS)
@pytest.mark.parametrize("bad", [3.0, "3", None, b"3", 3.5], ids=repr)
def test_size_math_takes_integers_only(name: str, bad: object) -> None:
    """operator.index, so a float or a str is a TypeError and never a float result."""
    codec = radixly.get_codec(name)
    with pytest.raises(TypeError):
        codec.encoded_len(bad)  # pyright: ignore[reportArgumentType]
    with pytest.raises(TypeError):
        codec.max_bytes(bad)  # pyright: ignore[reportArgumentType]


class IndexLike:
    """An integer by __index__ only, the way numpy scalars and enums count."""

    def __init__(self, value: int) -> None:
        self.value: int = value

    def __index__(self) -> int:
        return self.value


@pytest.mark.parametrize("name", EXPECTED_CODECS)
def test_size_math_returns_int_for_index_likes(name: str) -> None:
    """Anything with __index__ is taken, the result is a plain int."""
    codec = radixly.get_codec(name)
    for value in (7, True, IndexLike(7)):
        for function in (codec.encoded_len, codec.max_bytes):
            result = function(value)
            assert type(result) is int
            assert result == function(int(value))


def test_import_is_eager() -> None:
    """The only test that fails if a codec's eager import leaves __init__; in-process, pytest imports it first."""
    code = (
        "import radixly\n"
        f"for name in {EXPECTED_CODECS!r}:\n"
        "    getattr(radixly, name).encode(b'x')\n"
        f"if list(radixly.CODECS) != {EXPECTED_CODECS!r}:\n"
        "    raise SystemExit(f'registry order {list(radixly.CODECS)}')\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argv, own interpreter
