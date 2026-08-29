"""Markdown fragment with splice markers: regenerated, never hand-edited.

The fragment carries its own provenance line -- machine, governor, commit,
date -- so a quoted number can always be traced to the run that produced it.
``inject`` replaces the marked block in a larger document and is idempotent.
"""

from __future__ import annotations

import typing

from benchmarks import registry

if typing.TYPE_CHECKING:
    from benchmarks import model

BEGIN: typing.Final = "<!-- radixly-bench:begin -->"
END: typing.Final = "<!-- radixly-bench:end -->"

_THROUGHPUT_FLOOR: typing.Final = 65536


def _cell(measurement: model.Measurement) -> str:
    if measurement.size_bytes >= _THROUGHPUT_FLOOR:
        return f"{measurement.mb_per_s:,.0f} MB/s"
    return f"{measurement.ns_per_call / 1e3:.3f} μs"


def table(result: model.RunResult) -> str:
    """Provenance line plus the results table, marker-free (CI summaries use this)."""
    env = result.environment
    sizes: list[str] = []
    rows: dict[tuple[str, str, str], dict[str, model.Measurement]] = {}
    for m in result.measurements:
        if m.size_label not in sizes:
            sizes.append(m.size_label)
        rows.setdefault((m.codec, m.implementation, m.direction), {})[m.size_label] = m

    header = "| codec | direction | " + " | ".join(sizes) + " | vs reference |"
    divider = "|---|---|" + "---|" * len(sizes) + "---|"
    lines = [
        f"*Measured on {env.cpu} ({env.governor} governor), {env.os}, CPython {env.python}, "
        + f"{env.compiler}, radixly {env.radixly_version} @ {env.commit}"
        + f"{' (dirty)' if env.dirty else ''}, {env.timestamp}.*",
        "",
        header,
        divider,
    ]
    for (codec, implementation, direction), cells in rows.items():
        codec_label = codec if implementation == "radixly" else f"{codec} ({implementation})"
        chosen: model.Measurement | None = None
        for m in cells.values():
            if m.ratio is not None:
                chosen = m
                if m.size_label == registry.RATIO_SIZE_LABEL:
                    break
        ratio = f"{chosen.ratio:.0f}x at {chosen.size_label}" if chosen is not None and chosen.ratio else ""
        line = f"| {codec_label} | {direction} | "
        line += " | ".join(_cell(cells[label]) if label in cells else "—" for label in sizes)
        line += f" | {ratio or '—'} |"
        lines.append(line)
    return "\n".join(lines) + "\n"


def fragment(result: model.RunResult) -> str:
    """The marker-wrapped table; write it to a file or hand it to inject()."""
    return f"{BEGIN}\n{table(result)}{END}\n"


def inject(document: str, wrapped_fragment: str) -> str:
    """Replace the marked block in ``document``; markers must appear exactly once."""
    begin = document.find(BEGIN)
    end = document.find(END)
    if begin == -1 or end == -1 or end < begin:
        msg = f"document must contain one {BEGIN} ... {END} block"
        raise ValueError(msg)
    if document.find(BEGIN, begin + 1) != -1 or document.find(END, end + 1) != -1:
        msg = "markers appear more than once; refusing to guess which block to replace"
        raise ValueError(msg)
    return document[:begin] + wrapped_fragment.strip("\n") + document[end + len(END) :]
