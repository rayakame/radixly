"""SVG charts, one file per theme, deterministic output for committing.

Two charts: sustained throughput (MB/s at the largest size with a throughput
story) and per-call latency at the ratio size. Each renders twice --
``<name>.svg`` (light) and ``<name>.dark.svg`` -- for the ``<picture>``
dark-mode embed. ``svg.hashsalt`` is pinned so re-rendering unchanged data
produces byte-identical files: committed artifacts diff cleanly.
"""

# Matplotlib's public API is loosely typed; this file quarantines the noise:
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import dataclasses
import typing

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

from benchmarks import registry
from benchmarks.render import theme as theme_module

if typing.TYPE_CHECKING:
    import pathlib

    from benchmarks import model
    from benchmarks.render.theme import Theme

_THROUGHPUT_FLOOR: typing.Final = 65536


def _grouped(result: model.RunResult, size_label: str) -> tuple[list[str], list[float], list[float]]:
    """Codec order preserved; (codecs, encode values, decode values) for one size."""
    encode: dict[str, float] = {}
    decode: dict[str, float] = {}
    for m in result.measurements:
        if m.size_label != size_label or m.implementation != "radixly":
            continue  # the cross-codec bars are radixly's own scoreboard
        (encode if m.direction == "encode" else decode)[m.codec] = m.ns_per_call
    codecs = [name for name in encode if name in decode]
    return codecs, [encode[name] for name in codecs], [decode[name] for name in codecs]


@dataclasses.dataclass(frozen=True, slots=True)
class _ChartData:
    title: str
    codecs: list[str]
    encode_values: list[float]
    decode_values: list[float]
    unit: str


def _bar_chart(path: pathlib.Path, theme: Theme, data: _ChartData) -> None:
    title, codecs = data.title, data.codecs
    encode_values, decode_values, unit = data.encode_values, data.decode_values, data.unit
    figure, axes = plt.subplots(figsize=(7.2, 3.6))
    figure.patch.set_alpha(0.0)
    axes.set_facecolor("none")
    positions = range(len(codecs))
    width = 0.38
    bars_e = axes.bar([p - width / 2 for p in positions], encode_values, width, label="encode", color=theme.encode)
    bars_d = axes.bar([p + width / 2 for p in positions], decode_values, width, label="decode", color=theme.decode)
    for bars in (bars_e, bars_d):
        axes.bar_label(bars, fmt="%.0f" if unit == "MB/s" else "%.2f", color=theme.muted, fontsize=8, padding=2)
    axes.set_title(title, color=theme.text, fontsize=11, loc="left")
    axes.set_ylabel(unit, color=theme.muted, fontsize=9)
    axes.set_xticks(list(positions), codecs)
    axes.tick_params(colors=theme.muted, labelsize=9)
    axes.grid(axis="y", color=theme.grid, linewidth=0.6)
    axes.set_axisbelow(True)
    for spine in axes.spines.values():
        spine.set_visible(False)
    legend = axes.legend(loc="upper right", frameon=False, fontsize=9)
    for text in legend.get_texts():
        text.set_color(theme.text)
    figure.tight_layout()
    with plt.rc_context({"svg.hashsalt": "radixly"}):
        figure.savefig(path, format="svg", transparent=True, metadata={"Date": None})
    plt.close(figure)


def _target_path(directory: pathlib.Path, name: str, theme: Theme) -> pathlib.Path:
    suffix = ".svg" if theme.name == "light" else ".dark.svg"
    return directory / f"{name}{suffix}"


@dataclasses.dataclass(frozen=True, slots=True)
class _SweepData:
    title: str
    unit: str
    log_y: bool
    # (implementation, direction) -> [(size_bytes, value)], size-sorted
    series: dict[tuple[str, str], list[tuple[int, float]]]


def _sweep_series(
    result: model.RunResult, codec: str, *, as_mbps: bool
) -> dict[tuple[str, str], list[tuple[int, float]]]:
    series: dict[tuple[str, str], list[tuple[int, float]]] = {}
    for m in result.measurements:
        if m.codec != codec:
            continue
        value = m.mb_per_s if as_mbps else m.ns_per_call / 1e3
        series.setdefault((m.implementation, m.direction), []).append((m.size_bytes, value))
    return {key: sorted(points) for key, points in series.items()}


def _implementation_colors(series: dict[tuple[str, str], list[tuple[int, float]]], theme: Theme) -> dict[str, str]:
    colors: dict[str, str] = {}
    ramp = iter(theme.competitors)
    for key in series:
        implementation = key[0]
        if implementation in colors:
            continue
        colors[implementation] = theme.encode if implementation == "radixly" else next(ramp, theme.decode)
    return colors


def _line_chart(path: pathlib.Path, theme: Theme, data: _SweepData) -> None:
    figure, axes = plt.subplots(figsize=(7.2, 3.6))
    figure.patch.set_alpha(0.0)
    axes.set_facecolor("none")
    colors = _implementation_colors(data.series, theme)
    for (implementation, direction), points in data.series.items():
        sizes = [size for size, _ in points]
        values = [value for _, value in points]
        axes.plot(
            sizes,
            values,
            marker="o",
            markersize=4,
            linewidth=1.6,
            linestyle="-" if direction == "encode" else "--",
            color=colors[implementation],
            label=f"{implementation} {direction}",
        )
    axes.set_xscale("log")
    if data.log_y:
        axes.set_yscale("log")
    axes.set_title(data.title, color=theme.text, fontsize=11, loc="left")
    axes.set_ylabel(data.unit, color=theme.muted, fontsize=9)
    axes.set_xlabel("payload bytes", color=theme.muted, fontsize=9)
    axes.tick_params(colors=theme.muted, labelsize=9, which="both")
    axes.grid(color=theme.grid, linewidth=0.6, which="major")
    axes.set_axisbelow(True)
    for spine in axes.spines.values():
        spine.set_visible(False)
    legend = axes.legend(loc="best", frameon=False, fontsize=8)
    for text in legend.get_texts():
        text.set_color(theme.text)
    figure.tight_layout()
    with plt.rc_context({"svg.hashsalt": "radixly"}):
        figure.savefig(path, format="svg", transparent=True, metadata={"Date": None})
    plt.close(figure)


def _write_codec_sweeps(result: model.RunResult, directory: pathlib.Path) -> list[pathlib.Path]:
    """Per-codec folders: size sweeps for every implementation, rivals included."""
    written: list[pathlib.Path] = []
    codecs: list[str] = []
    for m in result.measurements:
        if m.codec not in codecs:
            codecs.append(m.codec)
    for codec in codecs:
        throughput = _sweep_series(result, codec, as_mbps=True)
        latency = _sweep_series(result, codec, as_mbps=False)
        if not throughput:
            continue
        subdirectory = directory / codec
        subdirectory.mkdir(parents=True, exist_ok=True)
        charts = (
            ("throughput", _SweepData(f"{codec}: throughput by payload size", "MB/s", log_y=False, series=throughput)),
            (
                "latency",
                _SweepData(f"{codec}: per-call latency by payload size", "μs/call", log_y=True, series=latency),
            ),
        )
        for name, data in charts:
            for theme in theme_module.THEMES:
                path = _target_path(subdirectory, name, theme)
                _line_chart(path, theme, data)
                written.append(path)
    return written


def write_charts(result: model.RunResult, directory: pathlib.Path) -> list[pathlib.Path]:
    """Both charts x both themes into ``directory``; returns what was written."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[pathlib.Path] = []

    throughput_rows = [m for m in result.measurements if m.size_bytes >= _THROUGHPUT_FLOOR]
    throughput_label = max(throughput_rows, key=lambda m: m.size_bytes).size_label if throughput_rows else None
    if throughput_label is not None:
        codecs, encode_ns, decode_ns = _grouped(result, throughput_label)
        size = next(m.size_bytes for m in throughput_rows if m.size_label == throughput_label)
        to_mbps = [size / ns * 1e3 for ns in encode_ns], [size / ns * 1e3 for ns in decode_ns]
        chart = _ChartData(f"Sustained throughput, {throughput_label} payloads", codecs, *to_mbps, "MB/s")
        for theme in theme_module.THEMES:
            path = _target_path(directory, "throughput", theme)
            _bar_chart(path, theme, chart)
            written.append(path)

    codecs, encode_ns, decode_ns = _grouped(result, registry.RATIO_SIZE_LABEL)
    if codecs:
        to_us = [ns / 1e3 for ns in encode_ns], [ns / 1e3 for ns in decode_ns]
        chart = _ChartData(f"Per-call latency, {registry.RATIO_SIZE_LABEL} payloads", codecs, *to_us, "μs/call")
        for theme in theme_module.THEMES:
            path = _target_path(directory, "latency", theme)
            _bar_chart(path, theme, chart)
            written.append(path)
    written.extend(_write_codec_sweeps(result, directory))
    return written
