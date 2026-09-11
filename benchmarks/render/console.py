# Copyright (c) 2026-present rayakame
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Console renderer: the familiar aligned tables."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from benchmarks import model

_THROUGHPUT_FLOOR: typing.Final = 65536  # below this, per-call time is the readable unit


def render(result: model.RunResult) -> str:
    """Render the console report of a run: one block per codec and direction."""
    env = result.environment
    lines = [
        f"python   {env.python}",
        f"cpu      {env.cpu}",
        f"governor {env.governor}",
        f"os       {env.os}",
        f"compiler {env.compiler}",
        f"radixly  {env.radixly_version} @ {env.commit}{' (dirty)' if env.dirty else ''}",
    ]
    if result.run.mode != "full":
        lines.append(f"mode     {result.run.mode} (not a record)")
    if result.run.forced:
        lines.append("build    forced despite non-optimized")
    lines.append("")
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
