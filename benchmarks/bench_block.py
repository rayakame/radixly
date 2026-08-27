"""Benchmark the block-preset C codecs: braille, hexagram, uro14.

Same protocol as bench_base32768: quiet machine, governor pinned for record
runs, run twice and believe agreeing minimums. The helpers are copied from
bench_base32768 on purpose; the M8 benchmark product decides what merges.
"""

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

# The pure-Python references deliberately live in the tests package, outside
# radixly; put the repo root on the path so `tests.` resolves.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from radixly import _core
from tests.reference import braille as braille_reference
from tests.reference import hexagram as hexagram_reference
from tests.reference import uro14 as uro14_reference

REPEAT: typing.Final = 7

_T = typing.TypeVar("_T")


def seconds_per_call(func: Callable[[_T], object], payload: _T, number: int) -> float:
    """Best-of-REPEAT seconds for one ``func(payload)`` call."""
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
    """Rows for one direction, then the reference + ratio from the "187 B" case."""
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

    one: bytes = random.Random(1).randbytes(1)
    discord: bytes = random.Random(187).randbytes(187)
    big: bytes = random.Random(65536).randbytes(65536)

    codecs: list[
        tuple[str, Callable[[bytes], str], Callable[[str], bytes], Callable[[bytes], str], Callable[[str], bytes]]
    ] = [
        ("braille", _core.braille_encode, _core.braille_decode, braille_reference.encode, braille_reference.decode),
        (
            "hexagram",
            _core.hexagram_encode,
            _core.hexagram_decode,
            hexagram_reference.encode,
            hexagram_reference.decode,
        ),
        ("uro14", _core.uro14_encode, _core.uro14_decode, uro14_reference.encode, uro14_reference.decode),
    ]
    for name, c_encode, c_decode, ref_encode, ref_decode in codecs:
        report_direction(
            f"{name} encode",
            c_encode,
            ref_encode,
            [("1 B", one, 3_000_000, 1), ("187 B", discord, 500_000, 187), ("64 KiB", big, 3_000, 65536)],
        )
        print()
        report_direction(
            f"{name} decode",
            c_decode,
            ref_decode,
            [
                ("1 B", c_encode(one), 3_000_000, 1),
                ("187 B", c_encode(discord), 500_000, 187),
                ("64 KiB", c_encode(big), 3_000, 65536),
            ],
        )
        print()


if __name__ == "__main__":
    main()
