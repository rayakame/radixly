"""Console renderer: the familiar aligned tables."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from benchmarks import model

_THROUGHPUT_FLOOR: typing.Final = 65536  # below this, per-call time is the readable unit


def render(result: model.RunResult) -> str:
    env = result.environment
    lines = [
        f"python   {env.python}",
        f"cpu      {env.cpu}",
        f"governor {env.governor}",
        f"os       {env.os}",
        f"compiler {env.compiler}",
        f"radixly  {env.radixly_version} @ {env.commit}{' (dirty)' if env.dirty else ''}",
        "",
    ]
    groups: dict[tuple[str, str, str], list[model.Measurement]] = {}
    for measurement in result.measurements:
        key = (measurement.codec, measurement.implementation, measurement.direction)
        groups.setdefault(key, []).append(measurement)

    for (codec, implementation, direction), rows in groups.items():
        label = codec if implementation == "radixly" else f"{codec} ({implementation})"
        lines.append(f"{label} {direction}")
        reference_line = ""
        for row in rows:
            throughput = f"   {row.mb_per_s:.0f} MB/s" if row.size_bytes >= _THROUGHPUT_FLOOR else ""
            lines.append(f"  {row.size_label:8} {row.ns_per_call / 1e3:9.3f} us/call{throughput}")
            if row.reference_ns_per_call is not None and row.ratio is not None:
                reference_line = (
                    f"  reference (pure Python), {row.size_label}: "
                    f"{row.reference_ns_per_call / 1e3:.2f} us/call -> {row.ratio:.0f}x"
                )
        if reference_line:
            lines.append(reference_line)
        lines.append("")
    return "\n".join(lines)
