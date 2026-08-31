"""The floor tripwire: baseline matching and the warning band."""

from __future__ import annotations

import typing

from benchmarks import baseline
from benchmarks import model
from tests.bench import factories

if typing.TYPE_CHECKING:
    import pathlib


def _write(directory: pathlib.Path, name: str, result: model.RunResult) -> None:
    (directory / name).write_text(model.to_json(result), encoding="utf-8")


def test_baseline_matches_cpu_and_governor(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, "other.json", factories.make_result(cpu="OtherCPU"))
    _write(tmp_path, "mine.json", factories.make_result())
    found = baseline.find_baseline(factories.make_environment(), tmp_path)
    assert found is not None
    assert found.environment.cpu == "TestCPU"
    assert baseline.find_baseline(factories.make_environment(governor="powersave"), tmp_path) is None


def test_missing_directory_means_no_baseline(tmp_path: pathlib.Path) -> None:
    assert baseline.find_baseline(factories.make_environment(), tmp_path / "absent") is None


def test_unreadable_files_are_skipped(tmp_path: pathlib.Path) -> None:
    (tmp_path / "junk.json").write_text("{not json", encoding="utf-8")
    _write(tmp_path, "mine.json", factories.make_result())
    assert baseline.find_baseline(factories.make_environment(), tmp_path) is not None


def test_missing_key_documents_are_skipped_not_fatal(tmp_path: pathlib.Path) -> None:
    """The empirical crasher: a committed result missing 'cpu' must be skipped
    by the scan, never brick every future measured run."""
    broken = model.to_json(factories.make_result()).replace('"cpu": "TestCPU",', "")
    assert '"cpu"' not in broken  # the surgery worked; the document is truly missing the key
    (tmp_path / "aa-broken.json").write_text(broken, encoding="utf-8")
    assert baseline.find_baseline(factories.make_environment(), tmp_path) is None
    _write(tmp_path, "zz-good.json", factories.make_result())
    found = baseline.find_baseline(factories.make_environment(), tmp_path)
    assert found is not None


def test_floor_within_band_is_silent() -> None:
    current = factories.make_result((factories.make_measurement(ns_per_call=24.0),))
    assert baseline.floor_warnings(current, factories.make_result()) == []


def test_floor_drift_warns_in_both_directions() -> None:
    """Slower means trouble; suspiciously faster means the harness changed."""
    slow = factories.make_result((factories.make_measurement(ns_per_call=30.0),))
    fast = factories.make_result((factories.make_measurement(ns_per_call=10.0),))
    assert len(baseline.floor_warnings(slow, factories.make_result())) == 1
    assert "x1.67" in baseline.floor_warnings(slow, factories.make_result())[0]
    assert len(baseline.floor_warnings(fast, factories.make_result())) == 1


def test_only_floor_rows_are_compared() -> None:
    """A 1 MiB row 10x off is a throughput story, not the tripwire's business."""
    current = factories.make_result(
        (factories.make_measurement(size_label="1 MiB", size_bytes=2**20, ns_per_call=5_000_000.0),)
    )
    base = factories.make_result(
        (factories.make_measurement(size_label="1 MiB", size_bytes=2**20, ns_per_call=500_000.0),)
    )
    assert baseline.floor_warnings(current, base) == []
