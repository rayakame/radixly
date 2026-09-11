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
"""timeit core: setup-bound locals, min-of-N, calibrated loop counts.

Locals measured 1-1.7 ns cheaper than globals= at the 1 B floor; min because noise only adds.
"""

from __future__ import annotations

import timeit
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

REPEAT: typing.Final = 7
TARGET_SECONDS: typing.Final = 0.2

_T = typing.TypeVar("_T")


def round_to_grid(raw: float) -> int:
    """Round down to the largest 1-2-5 x 10^k count <= raw; may undershoot the target by up to 2.5x, accepted."""
    n = max(1, int(raw))
    magnitude = 1
    while magnitude * 10 <= n:
        magnitude *= 10
    for step in (5, 2, 1):
        if step * magnitude <= n:
            return step * magnitude
    return magnitude


def calibrate(func: Callable[[_T], object], value: _T, target: float = TARGET_SECONDS) -> int:
    """Loop count sizing one repeat near ``target`` seconds."""
    number = 1
    while True:
        elapsed = timeit.timeit(
            "f(v)",
            setup="f = func; v = value",
            globals={"func": func, "value": value},
            number=number,
        )
        if elapsed >= target / 10 or number >= 10**9:
            break
        number *= 10
    return round_to_grid(number * target / max(elapsed, 1e-9))


def seconds_per_call(func: Callable[[_T], object], value: _T, number: int, repeat: int = REPEAT) -> float:
    """Best-of-``repeat`` seconds for one ``func(value)`` call."""
    totals: list[float] = timeit.repeat(
        "f(v)",
        setup="f = func; v = value",
        globals={"func": func, "value": value},
        number=number,
        repeat=repeat,
    )
    return min(totals) / number
