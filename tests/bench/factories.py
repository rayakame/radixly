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
"""Synthetic result builders shared by the benchmark suite's self-tests."""

from __future__ import annotations

from benchmarks import model


def make_environment(
    cpu: str = "TestCPU",
    governor: str = "performance",
    *,
    dirty: bool = False,
    optimized: bool = True,
) -> model.Environment:
    return model.Environment(
        python="3.13.0",
        cpu=cpu,
        governor=governor,
        os="Linux-test",
        compiler="testcc 1.0",
        radixly_version="0.0.0.test",
        commit="abc1234",
        dirty=dirty,
        optimized=optimized,
        timestamp="2026-08-28T00:00:00+00:00",
    )


def make_measurement(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] -- factories are knobs
    codec: str = "base32768",
    direction: str = "encode",
    size_label: str = "1 B",
    size_bytes: int = 1,
    ns_per_call: float = 18.0,
    reference_ns_per_call: float | None = 1800.0,
) -> model.Measurement:
    return model.Measurement(
        codec=codec,
        direction=direction,
        size_label=size_label,
        size_bytes=size_bytes,
        ns_per_call=ns_per_call,
        number=5_000_000,
        repeats=7,
        reference_ns_per_call=reference_ns_per_call,
    )


def make_result(
    measurements: tuple[model.Measurement, ...] | None = None,
    cpu: str = "TestCPU",
    governor: str = "performance",
    run: model.RunInfo | None = None,
) -> model.RunResult:
    if measurements is None:
        measurements = (make_measurement(),)
    return model.RunResult(model.SCHEMA_VERSION, make_environment(cpu, governor), measurements, run or model.RunInfo())
