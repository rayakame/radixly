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
"""The drop-in suite: every ``radixly.compat.base64`` function against the standard library's, same input, same call."""

from __future__ import annotations

import base64
import dataclasses
import io
import typing

from benchmarks import model
from benchmarks import payloads
from benchmarks import timing
from radixly.compat import base64 as compat_base64

if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

    Call = Callable[[bytes], object]


@dataclasses.dataclass(frozen=True, slots=True)
class Function:
    """One drop-in function; a decoder's input is the standard library's ``source`` encoding of the payload."""

    name: str
    direction: str
    source: str | None = None
    file_pair: bool = False


FUNCTIONS: typing.Final[tuple[Function, ...]] = (
    Function("b16encode", "encode"),
    Function("b16decode", "decode", "b16encode"),
    Function("b32encode", "encode"),
    Function("b32decode", "decode", "b32encode"),
    Function("b32hexencode", "encode"),
    Function("b32hexdecode", "decode", "b32hexencode"),
    Function("b64encode", "encode"),
    Function("b64decode", "decode", "b64encode"),
    Function("standard_b64encode", "encode"),
    Function("standard_b64decode", "decode", "standard_b64encode"),
    Function("urlsafe_b64encode", "encode"),
    Function("urlsafe_b64decode", "decode", "urlsafe_b64encode"),
    Function("a85encode", "encode"),
    Function("a85decode", "decode", "a85encode"),
    Function("b85encode", "encode"),
    Function("b85decode", "decode", "b85encode"),
    Function("z85encode", "encode"),  # 3.13 and later; absent before, so the rows are skipped
    Function("z85decode", "decode", "z85encode"),
    Function("encodebytes", "encode"),
    Function("decodebytes", "decode", "encodebytes"),
    Function("encode", "encode", file_pair=True),
    Function("decode", "decode", "encodebytes", file_pair=True),
)


@dataclasses.dataclass(frozen=True, slots=True)
class Pair:
    """The two callables a row times, both taking the prepared input."""

    function: Function
    ours: Call
    stdlib: Call


def _file_call(function: Callable[..., object]) -> Call:
    def call(data: bytes) -> None:
        function(io.BytesIO(data), io.BytesIO())

    return call


def pairs(functions: tuple[Function, ...] | None = None) -> list[Pair]:
    """One pair per function the running interpreter's ``base64`` has."""
    rows: list[Pair] = []
    for function in FUNCTIONS if functions is None else functions:
        if not hasattr(base64, function.name):
            continue
        ours = typing.cast("Callable[..., object]", getattr(compat_base64, function.name))
        theirs = typing.cast("Callable[..., object]", getattr(base64, function.name))
        if function.file_pair:
            rows.append(Pair(function, _file_call(ours), _file_call(theirs)))
        else:
            rows.append(Pair(function, ours, theirs))
    return rows


def prepare(function: Function, payload: bytes) -> bytes:
    """Build the input both sides are timed on: the payload itself, or the standard library's encoding of it."""
    if function.source is None:
        return payload
    encode = typing.cast("Callable[[bytes], bytes]", getattr(base64, function.source))
    return encode(payload)


def check(pair: Pair, value: bytes) -> None:
    """Refuse to time two calls that disagree: the comparison is only fair on equal work."""
    if pair.function.file_pair:
        return  # the file pair's result lives in the output stream; the differential tests cover it
    ours = pair.ours(value)
    theirs = pair.stdlib(value)
    if ours != theirs:
        msg = f"compat.{pair.function.name} and base64.{pair.function.name} disagree on a {len(value)}-byte input"
        raise ValueError(msg)


def measure(
    sizes: Sequence[tuple[str, int]], directions: Sequence[str], repeat: int, target: float
) -> tuple[model.CompatMeasurement, ...]:
    """Time every pair at every size: ours, then the standard library's, on one prepared input."""
    rows: list[model.CompatMeasurement] = []
    for pair in pairs():
        if pair.function.direction not in directions:
            continue
        for label, size in sizes:
            value = prepare(pair.function, payloads.payload(size))
            check(pair, value)
            number = timing.calibrate(pair.ours, value, target)
            ours = timing.seconds_per_call(pair.ours, value, number, repeat) * 1e9
            stdlib_number = timing.calibrate(pair.stdlib, value, target)
            stdlib = timing.seconds_per_call(pair.stdlib, value, stdlib_number, repeat) * 1e9
            rows.append(
                model.CompatMeasurement(
                    pair.function.name, pair.function.direction, label, size, ours, stdlib, number, repeat
                )
            )
    return tuple(rows)
