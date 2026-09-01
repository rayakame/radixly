"""SVG chart smoke: both themes, valid XML, deterministic bytes."""

from __future__ import annotations

import dataclasses
import typing
import xml.etree.ElementTree as ET  # ruff: ignore[suspicious-xml-etree-import] -- parsing our own generated SVGs

from benchmarks.render import graphs
from tests.bench import factories

if typing.TYPE_CHECKING:
    import pathlib

    from benchmarks import model


def _result() -> model.RunResult:
    measurements: list[model.Measurement] = []
    for codec in ("base32768", "uro14"):
        for direction in ("encode", "decode"):
            measurements.extend(
                (
                    factories.make_measurement(
                        codec=codec, direction=direction, size_label="200 B", size_bytes=200, ns_per_call=110.0
                    ),
                    factories.make_measurement(
                        codec=codec, direction=direction, size_label="64 KiB", size_bytes=65536, ns_per_call=34_000.0
                    ),
                )
            )
    return factories.make_result(tuple(measurements))


def test_charts_land_in_root_and_codec_folders(tmp_path: pathlib.Path) -> None:
    written = graphs.write_charts(_result(), tmp_path)
    names = sorted(str(path.relative_to(tmp_path)) for path in written)
    per_codec = [
        f"{codec}/{name}{suffix}"
        for codec in ("base32768", "uro14")
        for name in ("latency", "throughput")
        for suffix in (".dark.svg", ".svg")
    ]
    assert names == sorted(["latency.dark.svg", "latency.svg", "throughput.dark.svg", "throughput.svg", *per_codec])
    for path in written:
        root = ET.parse(path).getroot()  # ruff: ignore[suspicious-xml-element-tree-usage] -- our own SVGs
        assert root.tag.endswith("svg")


def test_competitor_rows_reach_sweeps_but_not_bars(tmp_path: pathlib.Path) -> None:
    base = _result()
    rival_rows = tuple(
        dataclasses.replace(m, implementation="fakelib", reference_ns_per_call=None)
        for m in base.measurements
        if m.codec == "base32768"
    )
    result = dataclasses.replace(base, measurements=base.measurements + rival_rows)
    written = graphs.write_charts(result, tmp_path)
    sweep = (tmp_path / "base32768" / "throughput.svg").read_text(encoding="utf-8")
    bars = (tmp_path / "throughput.svg").read_text(encoding="utf-8")
    assert "fakelib" in sweep  # legend carries the rival
    assert "fakelib" not in bars  # the cross-codec bars stay radixly-only
    assert len(written) == 4 + 8


def test_rendering_is_deterministic(tmp_path: pathlib.Path) -> None:
    """Committed artifacts must diff cleanly: same data, same bytes."""
    first = (tmp_path / "a", tmp_path / "b")
    graphs.write_charts(_result(), first[0])
    graphs.write_charts(_result(), first[1])
    for name in ("throughput.svg", "latency.dark.svg", "base32768/throughput.svg", "uro14/latency.dark.svg"):
        assert (first[0] / name).read_bytes() == (first[1] / name).read_bytes()


def test_no_throughput_sizes_means_no_throughput_chart(tmp_path: pathlib.Path) -> None:
    result = factories.make_result(
        (
            factories.make_measurement(size_label="200 B", size_bytes=200),
            factories.make_measurement(direction="decode", size_label="200 B", size_bytes=200),
        )
    )
    written = graphs.write_charts(result, tmp_path)
    root_only = [path.name for path in written if path.parent == tmp_path]
    assert sorted(root_only) == ["latency.dark.svg", "latency.svg"]
