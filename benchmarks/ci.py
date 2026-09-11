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
"""Ratio gates for CI: C vs reference, so runner noise divides out. Floors live in ci-gates.json, deliberately slack."""

from __future__ import annotations

import json
import math
import pathlib
import typing

from benchmarks import registry

if typing.TYPE_CHECKING:
    from benchmarks import model

GATES_PATH: typing.Final = pathlib.Path(__file__).parent / "ci-gates.json"


def load_gates(path: pathlib.Path = GATES_PATH) -> dict[str, dict[str, float]]:
    """{codec: {direction: floor}} from the committed gates file."""
    parsed: object = json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
    if not isinstance(parsed, dict):
        msg = "gates file must be a JSON object"
        raise TypeError(msg)
    document = typing.cast("dict[str, object]", parsed)
    floors_raw = document["ratio_floors"]
    if not isinstance(floors_raw, dict):
        msg = "ratio_floors must be an object"
        raise TypeError(msg)
    gates: dict[str, dict[str, float]] = {}
    for codec, directions in typing.cast("dict[str, object]", floors_raw).items():
        if not isinstance(directions, dict):
            msg = f"ratio_floors[{codec!r}] must be an object"
            raise TypeError(msg)
        gates[codec] = {}
        for direction, floor in typing.cast("dict[str, object]", directions).items():
            if not isinstance(floor, (int, float)) or isinstance(floor, bool):
                msg = f"ratio_floors[{codec!r}][{direction!r}] must be a number"
                raise TypeError(msg)
            if not math.isfinite(floor):
                # json.loads lets NaN through, and a NaN floor would pass the gate forever.
                msg = f"ratio_floors[{codec!r}][{direction!r}] must be finite"
                raise ValueError(msg)
            gates[codec][direction] = float(floor)
    return gates


def check_gates(result: model.RunResult, gates: dict[str, dict[str, float]]) -> list[str]:
    """One failure string per breached or uncheckable gate; empty means pass."""
    ratios: dict[tuple[str, str], float] = {}
    for m in result.measurements:
        if m.implementation != "radixly":
            continue  # rivals have no oracle; explicit, not safe-by-accident
        if m.size_label == registry.RATIO_SIZE_LABEL and m.ratio is not None:
            ratios[m.codec, m.direction] = m.ratio
    failures: list[str] = []
    for codec, directions in gates.items():
        for direction, floor in directions.items():
            ratio = ratios.get((codec, direction))
            if ratio is None:
                failures.append(
                    f"{codec} {direction}: gate requires a ratio at {registry.RATIO_SIZE_LABEL}, none measured"
                )
            elif ratio < floor:
                failures.append(f"{codec} {direction}: ratio {ratio:.0f}x is below the floor of {floor:.0f}x")
    return failures
