"""The JSON layer: canonical round-trip, schema guard, forward compatibility."""

# This file's business is poking raw JSON documents:
# pyright: reportAny=false

from __future__ import annotations

import dataclasses
import json

import pytest

from benchmarks import model
from tests.bench import factories


def test_round_trip_is_lossless() -> None:
    original = factories.make_result(
        (
            factories.make_measurement(),
            factories.make_measurement(direction="decode", reference_ns_per_call=None),
            factories.make_measurement(size_label="1 MiB", size_bytes=2**20, ns_per_call=540_000.0),
        )
    )
    assert model.from_json(model.to_json(original)) == original


def test_derived_values_are_written_for_readers() -> None:
    document = json.loads(model.to_json(factories.make_result()))
    row = document["measurements"][0]
    assert row["mb_per_s"] == pytest.approx(1 / 18.0 * 1e3)
    assert row["ratio"] == pytest.approx(100.0)


def test_unknown_keys_are_ignored() -> None:
    """Forward compatibility: a newer writer's additive keys must not break this reader."""
    document = json.loads(model.to_json(factories.make_result()))
    document["future_top_level"] = {"x": 1}
    document["measurements"][0]["future_row_key"] = "y"
    document["environment"]["future_env_key"] = 2
    assert model.from_json(json.dumps(document)) == factories.make_result()


def test_implementation_round_trips_and_defaults() -> None:
    """New writers carry the field; documents from before it default to radixly."""
    rival = factories.make_result((factories.make_measurement(),))
    rival = model.RunResult(
        rival.schema_version,
        rival.environment,
        (dataclasses.replace(rival.measurements[0], implementation="pybase64", reference_ns_per_call=None),),
    )
    assert model.from_json(model.to_json(rival)).measurements[0].implementation == "pybase64"

    document = json.loads(model.to_json(factories.make_result()))
    del document["measurements"][0]["implementation"]
    del document["environment"]["compiler"]
    loaded = model.from_json(json.dumps(document))
    assert loaded.measurements[0].implementation == "radixly"
    assert loaded.environment.compiler == "unknown"


def test_run_info_round_trips_with_varied_booleans() -> None:
    """Provenance survives the trip: mode, reference loop count, forced flag,
    and the environment booleans a record's honesty hangs on."""
    original = model.RunResult(
        model.SCHEMA_VERSION,
        factories.make_environment(dirty=True, optimized=False),
        (factories.make_measurement(),),
        model.RunInfo(mode="quick", reference_number=2_000, forced=True),
    )
    loaded = model.from_json(model.to_json(original))
    assert loaded == original
    assert loaded.run.mode == "quick"
    assert loaded.environment.dirty is True
    assert loaded.environment.optimized is False


def test_legacy_document_without_run_block_defaults_to_full() -> None:
    document = json.loads(model.to_json(factories.make_result()))
    del document["run"]
    loaded = model.from_json(json.dumps(document))
    assert loaded.run == model.RunInfo()
    assert loaded.run.mode == "full"


@pytest.mark.parametrize("bad", [0, -1.0])
def test_zero_or_negative_timing_is_rejected(bad: float) -> None:
    """A zero ns_per_call would reach renderers as a ZeroDivisionError."""
    document = json.loads(model.to_json(factories.make_result()))
    document["measurements"][0]["ns_per_call"] = bad
    with pytest.raises(ValueError, match="positive finite"):
        model.from_json(json.dumps(document))


def test_nan_token_is_rejected() -> None:
    """json.loads accepts the bare NaN token; the domain check must not."""
    text = model.to_json(factories.make_result()).replace('"ns_per_call": 18.0', '"ns_per_call": NaN')
    assert "NaN" in text  # the surgery worked
    with pytest.raises(ValueError, match="positive finite"):
        model.from_json(text)


def test_unsupported_schema_version_raises() -> None:
    document = json.loads(model.to_json(factories.make_result()))
    document["schema_version"] = 99
    with pytest.raises(ValueError, match="unsupported schema_version 99"):
        model.from_json(json.dumps(document))


def test_missing_field_raises_the_documented_error() -> None:
    """Missing keys must be ValueError, not KeyError: the error contract is
    TypeError/ValueError, and the baseline scan relies on it to skip bad files."""
    document = json.loads(model.to_json(factories.make_result()))
    del document["environment"]["cpu"]
    with pytest.raises(ValueError, match="cpu: missing"):
        model.from_json(json.dumps(document))
    document = json.loads(model.to_json(factories.make_result()))
    del document["measurements"]
    with pytest.raises(ValueError, match="measurements: missing"):
        model.from_json(json.dumps(document))


def test_wrong_field_type_raises() -> None:
    document = json.loads(model.to_json(factories.make_result()))
    document["measurements"][0]["ns_per_call"] = "fast"
    with pytest.raises(TypeError, match="ns_per_call"):
        model.from_json(json.dumps(document))
