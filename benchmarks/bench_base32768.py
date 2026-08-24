"""Benchmark the base32768 C encoder."""

from __future__ import annotations

import pathlib
import platform
import random
import sys
import timeit
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

# The pure-Python reference deliberately lives in tests/, not in the package,
# so the benchmark reaches it the same way the test suite does.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tests"))

from reference.base32768 import encode as reference_encode

from radixly._core import base32768_encode

REPEAT: typing.Final = 7


def seconds_per_call(func: Callable[[bytes], str], payload: bytes, number: int) -> float:
    """Best-of-REPEAT seconds for one ``func(payload)`` call.

    The statement is a *string*: timeit compiles it into a synthetic function
    body (locals, itertools-driven loop), the cheapest harness CPython can
    express. A lambda would add a Python call per iteration and poison the
    58 ns floor. min() is the statistic because noise only ever adds.
    """
    totals: list[float] = timeit.repeat(
        "func(payload)",
        globals={"func": func, "payload": payload},
        number=number,
        repeat=REPEAT,
    )
    return min(totals) / number


def print_environment() -> None:
    """A benchmark that records its own conditions can be believed later."""
    cpu: str
    try:
        with pathlib.Path("/proc/cpuinfo").open(encoding="utf-8") as f:
            cpu = next(line.split(":", 1)[1].strip() for line in f if line.startswith("model name"))
    except (OSError, StopIteration):
        cpu = "unknown"
    governor: str
    try:
        governor = (
            pathlib.Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").read_text(encoding="utf-8").strip()
        )
    except OSError:
        governor = "unknown"
    print(f"python   {platform.python_version()}")
    print(f"cpu      {cpu}")
    print(f"governor {governor}")
    print()


def main() -> None:
    print_environment()

    # Auto-calibration is M8 polish.
    one: bytes = random.Random(1).randbytes(1)
    discord: bytes = random.Random(187).randbytes(187)
    big: bytes = random.Random(65536).randbytes(65536)
    huge: bytes = random.Random(1_048_576).randbytes(1_048_576)

    t_1b: float = seconds_per_call(base32768_encode, one, number=3_000_000)
    t_187: float = seconds_per_call(base32768_encode, discord, number=500_000)
    t_64k: float = seconds_per_call(base32768_encode, big, number=3_000)
    t_1m: float = seconds_per_call(base32768_encode, huge, number=400)
    t_ref: float = seconds_per_call(reference_encode, discord, number=10_000)

    mbps_64k: float = len(big) / t_64k / 1e6
    mbps_1m: float = len(huge) / t_1m / 1e6
    print("base32768 encode")
    print(f"  1 B      {t_1b * 1e6:7.3f} us/call")
    print(f"  187 B    {t_187 * 1e6:7.3f} us/call")
    print(f"  64 KiB   {t_64k * 1e6:7.1f} us/call   {mbps_64k:.0f} MB/s")
    print(f"  1 MiB    {t_1m * 1e6:7.1f} us/call   {mbps_1m:.0f} MB/s")
    print()
    print(f"  reference (pure Python), 187 B: {t_ref * 1e6:.2f} us/call")
    print(f"  C vs reference at 187 B: {t_ref / t_187:.0f}x")


if __name__ == "__main__":
    main()
