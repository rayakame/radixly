"""The ratio gates: file integrity, breach detection, and the registry lockstep."""

from __future__ import annotations

import json
import typing

import pytest

import radixly
from benchmarks import ci
from tests.bench import factories

if typing.TYPE_CHECKING:
    import pathlib


def test_committed_gates_file_parses() -> None:
    gates = ci.load_gates()
    assert gates, "the committed gates file must define at least one floor"
    for directions in gates.values():
        assert set(directions) <= {"encode", "decode"}


def test_gates_cover_every_registered_codec() -> None:
    """A new codec must bring a gate: registration and ci-gates.json in lockstep."""
    assert set(ci.load_gates()) == set(radixly.CODECS)


def test_passing_gates_are_silent() -> None:
    result = factories.make_result(
        (
            factories.make_measurement(
                size_label="200 B", size_bytes=200, ns_per_call=110.0, reference_ns_per_call=11_000.0
            ),
        )
    )
    assert ci.check_gates(result, {"base32768": {"encode": 55.0}}) == []


def test_breached_gate_names_ratio_and_floor() -> None:
    result = factories.make_result(
        (
            factories.make_measurement(
                size_label="200 B", size_bytes=200, ns_per_call=110.0, reference_ns_per_call=2_200.0
            ),
        )
    )
    failures = ci.check_gates(result, {"base32768": {"encode": 55.0}})
    assert failures == ["base32768 encode: ratio 20x is below the floor of 55x"]


def test_missing_ratio_row_is_a_failure_not_a_pass() -> None:
    """A gate that cannot be checked must fail loudly, never skip silently."""
    result = factories.make_result((factories.make_measurement(),))  # 1 B row only
    failures = ci.check_gates(result, {"base32768": {"encode": 55.0}})
    assert len(failures) == 1
    assert "none measured" in failures[0]


def test_malformed_gates_file_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gates.json"
    path.write_text(json.dumps({"ratio_floors": {"base32768": {"encode": "fast"}}}), encoding="utf-8")
    with pytest.raises(TypeError, match="must be a number"):
        ci.load_gates(path)
