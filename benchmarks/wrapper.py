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
"""Wrapper-cost probe: what the API layering costs at the call floor.

The dotted access stays inside the timed statement. Console only.
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
    """One timed statement with the setup bindings it needs."""

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
    """One shape measured at one size, with its delta to the baseline."""

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
    """Time every shape at every size, one calibration per size."""
    rows: list[ShapeRow] = []
    for size_label, size in SIZES:
        data = payloads.payload(size)
        # One calibration per size, shared by every shape, keeps the deltas comparable.
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
    """Console table of the shape rows with their deltas to the baseline."""
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
