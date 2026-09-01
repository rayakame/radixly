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
    commit = _git("rev-parse", "--short", "HEAD") or "unknown"
    status = _git("status", "--porcelain")
    # A failed probe reports dirty, not clean: the pessimistic direction is
    # the honest one. Note commit/dirty describe the checkout, not the tree
    # the installed .so was built from -- rebuild before believing either.
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
