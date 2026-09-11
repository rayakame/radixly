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
"""Environment capture: a benchmark that records its own conditions can be believed later."""

from __future__ import annotations

import datetime
import pathlib
import platform
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed argv, git only

import radixly
from benchmarks import model
from radixly import _core


def _cpu_model() -> str:
    try:
        with pathlib.Path("/proc/cpuinfo").open(encoding="utf-8") as f:
            return next(line.split(":", 1)[1].strip() for line in f if line.startswith("model name"))
    except (OSError, StopIteration):
        return "unknown"


def _governor() -> str:
    try:
        return pathlib.Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _os_description() -> str:
    """Distro plus kernel where available; the terse platform tuple otherwise."""
    try:
        lines = pathlib.Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
        pretty = next(line.split("=", 1)[1].strip('"') for line in lines if line.startswith("PRETTY_NAME="))
    except (OSError, StopIteration):
        return platform.platform(terse=True)
    return f"{pretty}, kernel {platform.release()}"


def _git(*args: str) -> str | None:
    """None on failure -- distinct from "" so a dead git cannot look clean."""
    try:
        completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed argv
            ["git", *args],  # ruff: ignore[start-process-with-partial-path] -- PATH-resolved on purpose
            capture_output=True,
            text=True,
            check=True,
            cwd=pathlib.Path(__file__).resolve().parent.parent,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def capture() -> model.Environment:
    """Snapshot the machine, interpreter, compiler and checkout state for provenance."""
    commit = _git("rev-parse", "--short", "HEAD") or "unknown"
    status = _git("status", "--porcelain")
    # A failed probe reports dirty, not clean; commit/dirty describe the checkout, not the built .so.
    dirty = True if status is None else bool(status)
    return model.Environment(
        python=platform.python_version(),
        cpu=_cpu_model(),
        governor=_governor(),
        os=_os_description(),
        compiler=str(_core.COMPILER),
        radixly_version=radixly.__version__,
        commit=commit,
        dirty=dirty,
        optimized=bool(_core.OPTIMIZED),
        timestamp=datetime.datetime.now(tz=datetime.UTC).isoformat(timespec="seconds"),
    )
