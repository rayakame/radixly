"""The timeit core: setup-bound locals, min-of-N, calibrated loop counts.

The setup line binds func/value as true locals of timeit's synthetic function,
so the timed statement is LOAD_FAST plus the call -- with globals= alone the
names are LOAD_GLOBAL dictionary lookups every iteration. Settled by
measurement at the 1 B floor: 17.7-18.2 ns (setup-locals) vs 19.3 ns
(globals), ~1-1.7 ns of harness tax removed; this suite measures the codec,
not a dictionary. min() is the statistic because noise only ever adds.
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
    """Largest 1-2-5 x 10^k count <= raw (floor 1): stable across runs.

    Flooring can undershoot the time target by up to 2.5x (raw 4.9M -> 2M);
    accepted -- "near the target" is the contract, shorter runs the reward.
    """
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
