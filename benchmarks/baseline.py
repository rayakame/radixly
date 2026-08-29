"""Floor-sanity tripwire: warn when 1 B floors drift from the committed baseline.

A warning, never a refusal -- the committed results/ JSON for this machine and
governor is the expectation, and gross drift at the floor means something about
the run (build, frequency, scheduling) deserves a look before the numbers are
believed. Born from a mystery slowdown whose cause took three theories to find.
"""

from __future__ import annotations

import pathlib
import typing

from benchmarks import model

RESULTS_DIR: typing.Final = pathlib.Path(__file__).parent / "results"
FLOOR_SIZE_LABEL: typing.Final = "1 B"
FLOOR_BAND: typing.Final = 1.5  # deliberately wide: catch mechanisms, not wobble


def find_baseline(environment: model.Environment, directory: pathlib.Path = RESULTS_DIR) -> model.RunResult | None:
    """First committed result matching this machine's cpu and governor."""
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.json")):
        try:
            candidate = model.from_json(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            continue
        if candidate.environment.cpu == environment.cpu and candidate.environment.governor == environment.governor:
            return candidate
    return None


def floor_warnings(current: model.RunResult, baseline: model.RunResult) -> list[str]:
    """One warning per floor row outside the band, in either direction."""
    baseline_floors = {(m.codec, m.direction): m for m in baseline.measurements if m.size_label == FLOOR_SIZE_LABEL}
    warnings: list[str] = []
    for measurement in current.measurements:
        if measurement.size_label != FLOOR_SIZE_LABEL:
            continue
        reference = baseline_floors.get((measurement.codec, measurement.direction))
        if reference is None:
            continue
        factor = measurement.ns_per_call / reference.ns_per_call
        if factor > FLOOR_BAND or factor < 1 / FLOOR_BAND:
            warnings.append(
                f"{measurement.codec} {measurement.direction}: 1 B floor {measurement.ns_per_call:.1f} ns "
                + f"vs baseline {reference.ns_per_call:.1f} ns (x{factor:.2f})"
                + " -- investigate the run conditions before believing these numbers"
            )
    return warnings
