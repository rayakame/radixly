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

import dataclasses
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed argv, own interpreter
import sys

import pytest

import radixly
from radixly import _codec
from radixly import _core


def test_decode_error_is_the_core_type() -> None:
    assert radixly.DecodeError is _core.DecodeError


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


EXPECTED_CODECS = ["base2048", "base32768", "base65536", "braille", "hexagram", "uro14"]


@pytest.mark.parametrize("name", EXPECTED_CODECS)
def test_import_is_eager(name: str) -> None:
    """The only test that fails if a codec's eager import leaves __init__; in-process, pytest imports it first."""
    code = f"import radixly; radixly.{name}.encode(b'x'); assert list(radixly.CODECS) == {EXPECTED_CODECS!r}"
    subprocess.run([sys.executable, "-c", code], check=True)  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argv, own interpreter
