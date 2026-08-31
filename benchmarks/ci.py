"""Ratio gates for CI: floors that divide out the runner's noise.

Absolute numbers are meaningless on shared runners (plus or minus half is
normal); the C-vs-reference ratio is not, because both sides share the same
noisy machine. Floors live in ci-gates.json, deliberately slack -- they exist
to catch structural regressions (an added Python frame, an unoptimized wheel,
a broken fast path), never five-percent wobble.
"""

from __future__ import annotations

import json
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
