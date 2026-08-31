"""The wrapper-cost probe: what does the API layering cost at the call floor?

The old bench_api, absorbed. Each shape's dotted access happens inside the
timed statement -- hoisting it to setup would measure four identical calls.
Setup binds each receiver as a local, matching the main harness shape, so the
baseline row reads the same floor as the codec suite. Console-only: shape rows
deliberately stay out of the canonical JSON document.
"""

from __future__ import annotations

import dataclasses
import timeit
import typing

import radixly.base32768
from benchmarks import payloads
from benchmarks import timing
from radixly import _core

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

SIZES: tuple[tuple[str, int], ...] = (("1 B", 1), ("200 B", 200))


@dataclasses.dataclass(frozen=True, slots=True)
class Shape:
    label: str
    statement: str
    bindings: dict[str, object]
    is_baseline: bool = False  # the delta anchor; exactly one shape carries it


_SHAPES: tuple[Shape, ...] = (
    Shape("baseline  f(p)", "f(p)", {"f": _core.base32768_encode}, is_baseline=True),
    Shape("module    m.encode(p)", "m.encode(p)", {"m": radixly.base32768}),
    Shape("codec     c.encode(p)", "c.encode(p)", {"c": radixly.base32768.BASE32768}),
    Shape("hoisted   g(p)", "g(p)", {"g": radixly.base32768.BASE32768.encode}),
)


@dataclasses.dataclass(frozen=True, slots=True)
class ShapeRow:
    size_label: str
    shape: str
    ns_per_call: float
    delta_ns: float  # vs the baseline shape at the same size
    is_baseline: bool


def _measure_statement(statement: str, bindings: dict[str, object], number: int, repeat: int) -> float:
    setup = "; ".join(f"{name} = _{name}" for name in bindings)
    prefixed = {f"_{name}": value for name, value in bindings.items()}
    totals: list[float] = timeit.repeat(statement, setup=setup, globals=prefixed, number=number, repeat=repeat)
    return min(totals) / number


def measure(repeat: int = timing.REPEAT, target: float = timing.TARGET_SECONDS) -> list[ShapeRow]:
    rows: list[ShapeRow] = []
    for size_label, size in SIZES:
        data = payloads.payload(size)
        # One calibration per size, shared by every shape: identical loop
        # counts keep the nanosecond deltas comparable.
        number = timing.calibrate(_core.base32768_encode, data, target)
        measured = [
            (shape, _measure_statement(shape.statement, shape.bindings | {"p": data}, number, repeat) * 1e9)
            for shape in _SHAPES
        ]
        baseline_ns = next(ns for shape, ns in measured if shape.is_baseline)
        rows.extend(
            ShapeRow(size_label, shape.label, ns, ns - baseline_ns, shape.is_baseline) for shape, ns in measured
        )
    return rows


def render(rows: Sequence[ShapeRow]) -> str:
    lines: list[str] = []
    current_size = ""
    for row in rows:
        if row.size_label != current_size:
            current_size = row.size_label
            lines.append(f"wrapper cost, base32768 encode, {current_size} payload")
        delta = "" if row.is_baseline else f"   ({row.delta_ns:+.3f} vs baseline)"
        lines.append(f"  {row.shape:24} {row.ns_per_call:8.3f} ns/call{delta}")
    lines.append("")
    return "\n".join(lines)
