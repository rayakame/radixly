"""Benchmark the base32768 C codec."""

from __future__ import annotations

import pathlib
import platform
import random
import sys
import timeit
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

# The pure-Python reference deliberately lives in the tests package, outside
# radixly; put the repo root on the path so `tests.` resolves.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from radixly import _core
from tests.reference import base32768 as base32768_reference

REPEAT: typing.Final = 7

_T = typing.TypeVar("_T")


def seconds_per_call(func: Callable[[_T], object], payload: _T, number: int) -> float:
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


def report_direction(
    title: str,
    func: Callable[[_T], object],
    reference: Callable[[_T], object],
    cases: Sequence[tuple[str, _T, int, int]],
) -> None:
    """Measure and print one direction: four rows, then the reference + ratio.

    Each case is (label, input, loop count, payload bytes). MB/s counts
    payload bytes moved per second in both directions, so they compare 1:1;
    it is printed only where per-call time stops being the readable unit.
    The reference row and ratio reuse the case labelled "187 B".
    """
    timings: dict[str, float] = {}
    print(title)
    for label, value, number, payload_len in cases:
        t = seconds_per_call(func, value, number)
        timings[label] = t
        throughput = f"   {payload_len / t / 1e6:.0f} MB/s" if payload_len >= 65536 else ""
        print(f"  {label:8} {t * 1e6:8.3f} us/call{throughput}")
    ref_input = next(value for label, value, _, _ in cases if label == "187 B")
    t_ref = seconds_per_call(reference, ref_input, number=10_000)
    print()
    print(f"  reference (pure Python), 187 B: {t_ref * 1e6:.2f} us/call")
    print(f"  C vs reference at 187 B: {t_ref / timings['187 B']:.0f}x")


def main() -> None:
    print_environment()

    # Hardcoded loop counts keep each repeat near 0.2 s; auto-calibration can come later.
    one: bytes = random.Random(1).randbytes(1)
    discord: bytes = random.Random(187).randbytes(187)
    big: bytes = random.Random(65536).randbytes(65536)
    huge: bytes = random.Random(1_048_576).randbytes(1_048_576)

    report_direction(
        "base32768 encode",
        _core.base32768_encode,
        base32768_reference.encode,
        [
            ("1 B", one, 3_000_000, len(one)),
            ("187 B", discord, 500_000, len(discord)),
            ("64 KiB", big, 3_000, len(big)),
            ("1 MiB", huge, 400, len(huge)),
        ],
    )
    print()
    report_direction(
        "base32768 decode",
        _core.base32768_decode,
        base32768_reference.decode,
        [
            ("1 B", _core.base32768_encode(one), 3_000_000, len(one)),
            ("187 B", _core.base32768_encode(discord), 500_000, len(discord)),
            ("64 KiB", _core.base32768_encode(big), 3_000, len(big)),
            ("1 MiB", _core.base32768_encode(huge), 400, len(huge)),
        ],
    )


if __name__ == "__main__":
    main()
