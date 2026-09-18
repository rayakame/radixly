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
"""Every C entry point, called in a loop: what it allocates it must give back, on the error paths too."""

from __future__ import annotations

import array
import base64
import functools
import gc
import io
import pickle  # ruff: ignore[suspicious-pickle-import] -- PickleBuffer is the stdlib's buffer exporter
import sys
import typing

import pytest

import radixly
from radixly.compat import base64 as compat

if typing.TYPE_CHECKING:
    from collections.abc import Callable

REPEATS: typing.Final[int] = 200
BATCHES: typing.Final[int] = 5
# A leak of one object per call shows REPEATS every batch; the allocator's own arena churn shows in one of them.
TOLERANCE: typing.Final[int] = 16


def _batch(call: Callable[[], object]) -> int:
    # Twice, because the first pass can free cycles the test runner left behind and skew the baseline.
    gc.collect()
    gc.collect()
    before = sys.getallocatedblocks()
    for _ in range(REPEATS):
        call()
    gc.collect()
    gc.collect()
    return sys.getallocatedblocks() - before


def retained(call: Callable[[], object]) -> int:
    """Return the smallest growth over several batches, one batch having saturated the freelists first.

    Taking the smallest is what makes the meter stable: obmalloc hands out and returns arenas in steps, so a
    single batch can show tens of blocks either way, while a real leak grows by REPEATS in every batch.

    Everything already alive is frozen into the permanent generation first, so each collection walks only what
    the calls themselves made; without that the collections are O(heap) and cost minutes after a full run.
    """
    gc.freeze()
    try:
        for _ in range(REPEATS):
            call()
        return min(_batch(call) for _ in range(BATCHES))
    finally:
        gc.unfreeze()


def raising(function: Callable[..., object], *args: object, **kwargs: object) -> Callable[[], object]:
    """Wrap the call so its exception is the expected outcome; anything else fails the test."""

    def attempt() -> object:
        try:
            function(*args, **kwargs)
        except Exception as error:  # ruff: ignore[blind-except] -- every error path is under test here
            return type(error)
        # Measuring the success path here would pass while proving nothing about the error path.
        pytest.fail(f"{getattr(function, '__name__', function)} did not raise")

    return attempt


def either(function: Callable[..., object], *args: object) -> Callable[[], object]:
    """Wrap a call whose outcome is the codec's own business, such as a cut that lands on a group boundary."""

    def attempt() -> object:
        try:
            return function(*args)
        except Exception as error:  # ruff: ignore[blind-except] -- both outcomes are under measurement
            return type(error)

    return attempt


PAYLOAD: typing.Final[bytes] = bytes(range(256)) * 8


def _meter_sees_a_leak() -> bool:
    """Whether this interpreter counts the blocks at all: PYTHONMALLOC=malloc, as ASan needs, does not."""
    kept: list[object] = []
    return retained(lambda: kept.append(object())) >= REPEATS


if not _meter_sees_a_leak():  # the ASan session runs with PYTHONMALLOC=malloc, where the counter stays flat
    pytest.skip("sys.getallocatedblocks() does not count this interpreter's allocations", allow_module_level=True)


def test_the_meter_notices_a_leak() -> None:
    """A test that cannot fail is worthless: a deliberate leak must show up as one block per call."""
    kept: list[object] = []
    assert retained(lambda: kept.append(object())) >= REPEATS
    assert retained(lambda: None) <= TOLERANCE


@pytest.mark.parametrize("name", list(radixly.CODECS))
def test_codec_encode_and_decode_keep_nothing(name: str) -> None:
    codec = radixly.CODECS[name]
    text = codec.encode(PAYLOAD)
    assert retained(lambda: codec.encode(PAYLOAD)) <= TOLERANCE
    assert retained(lambda: codec.decode(text)) <= TOLERANCE
    assert retained(functools.partial(codec.encode, memoryview(PAYLOAD))) <= TOLERANCE


@pytest.mark.parametrize("name", list(radixly.CODECS))
def test_codec_error_paths_keep_nothing(name: str) -> None:
    """A decoder that leaks only when it raises would pass every other test in the suite."""
    codec = radixly.CODECS[name]
    text = codec.encode(PAYLOAD)
    for bad in (text + "\ud800", text + "\U0001f600", "\x00" + text, "\x7f" + text):
        assert retained(raising(codec.decode, bad)) <= TOLERANCE, bad[:16]
    # A cut decodes or raises depending on where it lands, so only the allocation is the subject here.
    for cut in (text[:-1], text[:7], text[: len(text) // 2]):
        assert retained(either(codec.decode, cut)) <= TOLERANCE, cut[:16]
    assert retained(raising(codec.encode, "str is not a buffer")) <= TOLERANCE
    assert retained(raising(codec.decode, b"bytes are not a str")) <= TOLERANCE
    assert retained(raising(codec.encoded_len, 3.5)) <= TOLERANCE


_ENCODED: typing.Final[dict[str, bytes]] = {
    "b16": base64.b16encode(PAYLOAD),
    "b32": base64.b32encode(PAYLOAD),
    "b32hex": base64.b32hexencode(PAYLOAD),
    "b64": base64.b64encode(PAYLOAD),
    "standard_b64": base64.b64encode(PAYLOAD),
    "urlsafe_b64": base64.urlsafe_b64encode(PAYLOAD),
    "a85": base64.a85encode(PAYLOAD),
    "b85": base64.b85encode(PAYLOAD),
    "z85": base64.b85encode(PAYLOAD),  # replaced below where the stdlib has z85
}
if sys.version_info >= (3, 13):
    _ENCODED["z85"] = base64.z85encode(PAYLOAD)  # pyright: ignore[reportUnreachable]

_PORTED: typing.Final[list[str]] = sorted(
    name for name in typing.cast("list[str]", base64.__all__) if name not in {"encode", "decode"}
)


@pytest.mark.parametrize("name", _PORTED)
def test_compat_functions_keep_nothing(name: str) -> None:
    function = typing.cast("Callable[..., object]", getattr(compat, name))
    argument = PAYLOAD if name.endswith("encode") or name == "encodebytes" else _ENCODED.get(name[:-6], b"")
    if name == "decodebytes":
        argument = base64.encodebytes(PAYLOAD)
    assert retained(functools.partial(function, argument)) <= TOLERANCE
    # The lenient decoders take "text" as four digits and discard the rest, so only the strict ones raise.
    assert retained(either(function, "text")) <= TOLERANCE
    assert retained(raising(function, 42)) <= TOLERANCE


@pytest.mark.parametrize(
    "make",
    [
        lambda: memoryview(PAYLOAD),
        lambda: array.array("B", PAYLOAD),
        lambda: bytearray(PAYLOAD),
        lambda: PAYLOAD,
    ],
    ids=["memoryview", "array", "bytearray", "bytes"],
)
def test_encodebytes_keeps_nothing_per_chunk(make: Callable[[], object]) -> None:
    """The slicing path builds index objects per 57-byte chunk; holding them would grow without bound."""
    argument = make()
    encodebytes = typing.cast("Callable[[object], object]", compat.encodebytes)
    assert retained(functools.partial(encodebytes, argument)) <= TOLERANCE


def test_legacy_file_functions_keep_nothing() -> None:
    lines = base64.encodebytes(PAYLOAD)

    def encode_once() -> object:
        return compat.encode(io.BytesIO(PAYLOAD), io.BytesIO())

    def decode_once() -> object:
        return compat.decode(io.BytesIO(lines), io.BytesIO())

    assert retained(encode_once) <= TOLERANCE
    assert retained(decode_once) <= TOLERANCE
    assert retained(raising(compat.encodebytes, pickle.PickleBuffer(PAYLOAD))) <= TOLERANCE
    # A file that cannot be written to fails halfway through the loop, where the line is still owned; the
    # input is rebuilt per call, since an exhausted one would return b"" and never reach the write.
    encode = typing.cast("Callable[..., object]", compat.encode)
    decode = typing.cast("Callable[..., object]", compat.decode)
    assert retained(raising(lambda: encode(io.BytesIO(PAYLOAD), object()))) <= TOLERANCE
    assert retained(raising(lambda: decode(io.BytesIO(lines), object()))) <= TOLERANCE


def test_registry_and_errors_keep_nothing() -> None:
    decode_error = typing.cast("Callable[..., object]", radixly.DecodeError)
    assert retained(functools.partial(radixly.get_codec, "base64")) <= TOLERANCE
    assert retained(raising(radixly.get_codec, "nope")) <= TOLERANCE
    assert retained(lambda: radixly.DecodeError(3, message="x")) <= TOLERANCE
    assert retained(raising(decode_error, 3, message=42)) <= TOLERANCE
