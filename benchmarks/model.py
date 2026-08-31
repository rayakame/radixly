"""The result data model: one run produces one RunResult; renderers only consume.

The JSON form is the canonical artifact (schema_version 1, additive evolution
only). Derived values (mb_per_s, ratio) are written for readers' convenience
but ignored on load -- the dataclass fields are the only source of truth.
"""

from __future__ import annotations

import dataclasses
import json
import math
import typing

SCHEMA_VERSION: typing.Final = 1


@dataclasses.dataclass(frozen=True, slots=True)
class Environment:
    python: str
    cpu: str
    governor: str
    os: str
    compiler: str  # the one that built the extension, self-reported by _core
    radixly_version: str
    commit: str
    dirty: bool
    optimized: bool
    timestamp: str


@dataclasses.dataclass(frozen=True, slots=True)
class Measurement:
    codec: str
    direction: str  # "encode" | "decode"
    size_label: str
    size_bytes: int  # payload bytes; decode rows count the bytes recovered
    ns_per_call: float
    number: int  # calibrated loop count, recorded for reproducibility
    repeats: int
    reference_ns_per_call: float | None = None
    implementation: str = "radixly"  # or a competitor's name (stdlib, pybase64, ...)

    @property
    def mb_per_s(self) -> float:
        return self.size_bytes / self.ns_per_call * 1e3

    @property
    def ratio(self) -> float | None:
        if self.reference_ns_per_call is None:
            return None
        return self.reference_ns_per_call / self.ns_per_call


@dataclasses.dataclass(frozen=True, slots=True)
class RunInfo:
    """How the run was taken: a record is only a record if this says so."""

    mode: str = "full"  # "full" | "quick" | "ci"
    reference_number: int | None = None  # loop count behind reference rows; None = unrecorded
    forced: bool = False  # measured despite a non-optimized build


@dataclasses.dataclass(frozen=True, slots=True)
class RunResult:
    schema_version: int
    environment: Environment
    measurements: tuple[Measurement, ...]
    run: RunInfo = RunInfo()


def to_dict(result: RunResult) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for measurement in result.measurements:
        row = typing.cast("dict[str, object]", dataclasses.asdict(measurement))
        row["mb_per_s"] = measurement.mb_per_s
        row["ratio"] = measurement.ratio
        rows.append(row)
    return {
        "schema_version": result.schema_version,
        "environment": typing.cast("dict[str, object]", dataclasses.asdict(result.environment)),
        "run": typing.cast("dict[str, object]", dataclasses.asdict(result.run)),
        "measurements": rows,
    }


def to_json(result: RunResult) -> str:
    return json.dumps(to_dict(result), indent=2, sort_keys=True) + "\n"


def _required(mapping: dict[str, object], key: str) -> object:
    if key not in mapping:
        msg = f"{key}: missing"
        raise ValueError(msg)
    return mapping[key]


def _str(mapping: dict[str, object], key: str) -> str:
    value = _required(mapping, key)
    if not isinstance(value, str):
        msg = f"{key}: expected str, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _int(mapping: dict[str, object], key: str) -> int:
    value = _required(mapping, key)
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"{key}: expected int, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _float(mapping: dict[str, object], key: str) -> float:
    value = _required(mapping, key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        msg = f"{key}: expected float, got {type(value).__name__}"
        raise TypeError(msg)
    return float(value)


def _bool(mapping: dict[str, object], key: str) -> bool:
    value = _required(mapping, key)
    if not isinstance(value, bool):
        msg = f"{key}: expected bool, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _positive_finite(mapping: dict[str, object], key: str) -> float:
    """Domain check on top of the type check: json.loads accepts NaN/Infinity
    tokens, and a zero would reach renderers as a ZeroDivisionError."""
    value = _float(mapping, key)
    if not math.isfinite(value) or value <= 0:
        msg = f"{key}: must be a positive finite number, got {value}"
        raise ValueError(msg)
    return value


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        msg = f"expected object, got {type(value).__name__}"
        raise TypeError(msg)
    return typing.cast("dict[str, object]", value)


def _environment_from(env_row: dict[str, object]) -> Environment:
    return Environment(
        python=_str(env_row, "python"),
        cpu=_str(env_row, "cpu"),
        governor=_str(env_row, "governor"),
        os=_str(env_row, "os"),
        compiler=_str(env_row, "compiler") if "compiler" in env_row else "unknown",
        radixly_version=_str(env_row, "radixly_version"),
        commit=_str(env_row, "commit"),
        dirty=_bool(env_row, "dirty"),
        optimized=_bool(env_row, "optimized"),
        timestamp=_str(env_row, "timestamp"),
    )


def _measurement_from(row: dict[str, object]) -> Measurement:
    size_bytes = _int(row, "size_bytes")
    number = _int(row, "number")
    repeats = _int(row, "repeats")
    if size_bytes < 0 or number < 1 or repeats < 1:
        msg = f"size_bytes/number/repeats out of domain: {size_bytes}/{number}/{repeats}"
        raise ValueError(msg)
    reference = row.get("reference_ns_per_call")
    return Measurement(
        codec=_str(row, "codec"),
        direction=_str(row, "direction"),
        size_label=_str(row, "size_label"),
        size_bytes=size_bytes,
        ns_per_call=_positive_finite(row, "ns_per_call"),
        number=number,
        repeats=repeats,
        reference_ns_per_call=None if reference is None else _positive_finite(row, "reference_ns_per_call"),
        implementation=_str(row, "implementation") if "implementation" in row else "radixly",
    )


def _run_info_from(document: dict[str, object]) -> RunInfo:
    if "run" not in document:
        return RunInfo()  # documents from before provenance: an unqualified full run
    run_row = _mapping(document["run"])
    raw_reference = run_row.get("reference_number")
    return RunInfo(
        mode=_str(run_row, "mode"),
        reference_number=None if raw_reference is None else _int(run_row, "reference_number"),
        forced=_bool(run_row, "forced"),
    )


def from_json(text: str) -> RunResult:
    """Parse the canonical JSON; unknown keys are ignored for forward compatibility.

    Raises TypeError or ValueError on malformed documents -- never anything
    else, so callers scanning many files (the baseline tripwire) can skip
    bad ones instead of dying on them.
    """
    parsed: object = json.loads(text)  # pyright: ignore[reportAny]
    document = _mapping(parsed)
    version = _int(document, "schema_version")
    if version != SCHEMA_VERSION:
        msg = f"unsupported schema_version {version}; this reader knows {SCHEMA_VERSION}"
        raise ValueError(msg)
    environment = _environment_from(_mapping(_required(document, "environment")))
    rows = _required(document, "measurements")
    if not isinstance(rows, list):
        msg = f"measurements: expected list, got {type(rows).__name__}"
        raise TypeError(msg)
    items = typing.cast("list[object]", rows)
    measurements = tuple(_measurement_from(_mapping(item)) for item in items)
    return RunResult(version, environment, measurements, _run_info_from(document))
