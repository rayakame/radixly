"""The result data model: one run produces one RunResult; renderers only consume.

The JSON form is the canonical artifact (schema_version 1, additive evolution
only). Derived values (mb_per_s, ratio) are written for readers' convenience
but ignored on load -- the dataclass fields are the only source of truth.
"""

from __future__ import annotations

import dataclasses
import json
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
class RunResult:
    schema_version: int
    environment: Environment
    measurements: tuple[Measurement, ...]


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
        "measurements": rows,
    }


def to_json(result: RunResult) -> str:
    return json.dumps(to_dict(result), indent=2, sort_keys=True) + "\n"


def _str(mapping: dict[str, object], key: str) -> str:
    value = mapping[key]
    if not isinstance(value, str):
        msg = f"{key}: expected str, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _int(mapping: dict[str, object], key: str) -> int:
    value = mapping[key]
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"{key}: expected int, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _float(mapping: dict[str, object], key: str) -> float:
    value = mapping[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        msg = f"{key}: expected float, got {type(value).__name__}"
        raise TypeError(msg)
    return float(value)


def _bool(mapping: dict[str, object], key: str) -> bool:
    value = mapping[key]
    if not isinstance(value, bool):
        msg = f"{key}: expected bool, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        msg = f"expected object, got {type(value).__name__}"
        raise TypeError(msg)
    return typing.cast("dict[str, object]", value)


def from_json(text: str) -> RunResult:
    """Parse the canonical JSON; unknown keys are ignored for forward compatibility."""
    parsed: object = json.loads(text)  # pyright: ignore[reportAny]
    document = _mapping(parsed)
    version = _int(document, "schema_version")
    if version != SCHEMA_VERSION:
        msg = f"unsupported schema_version {version}; this reader knows {SCHEMA_VERSION}"
        raise ValueError(msg)
    env_row = _mapping(document["environment"])
    environment = Environment(
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
    rows = document["measurements"]
    if not isinstance(rows, list):
        msg = f"measurements: expected list, got {type(rows).__name__}"
        raise TypeError(msg)
    items = typing.cast("list[object]", rows)
    measurements: list[Measurement] = []
    for item in items:
        row = _mapping(item)
        reference = row.get("reference_ns_per_call")
        measurements.append(
            Measurement(
                codec=_str(row, "codec"),
                direction=_str(row, "direction"),
                size_label=_str(row, "size_label"),
                size_bytes=_int(row, "size_bytes"),
                ns_per_call=_float(row, "ns_per_call"),
                number=_int(row, "number"),
                repeats=_int(row, "repeats"),
                reference_ns_per_call=None if reference is None else _float(row, "reference_ns_per_call"),
                implementation=_str(row, "implementation") if "implementation" in row else "radixly",
            )
        )
    return RunResult(version, environment, tuple(measurements))
