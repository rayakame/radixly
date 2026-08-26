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


def test_import_is_eager() -> None:
    """The only test that fails if the eager base32768 import leaves __init__."""
    code = "import radixly; radixly.base32768.encode(b'x'); assert radixly.CODECS"
    subprocess.run([sys.executable, "-c", code], check=True)  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argv, own interpreter
