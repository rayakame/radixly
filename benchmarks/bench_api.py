"""Wrapper-cost probe: what does the API layering cost at the call floor?

Each shape times the statement as user code writes it -- the dotted access
must happen inside the timed loop, or every shape measures the same raw C
function and the benchmark lies.
"""

from __future__ import annotations

import platform
import random
import timeit
import typing

import radixly.base32768
from radixly import _core

REPEAT: typing.Final = 7

# label -> (timed statement, bindings); "p" is added per payload.
SHAPES: dict[str, tuple[str, dict[str, object]]] = {
    "baseline  f(p)": ("f(p)", {"f": _core.base32768_encode}),
    "module    m.encode(p)": ("m.encode(p)", {"m": radixly.base32768}),
    "codec     c.encode(p)": ("c.encode(p)", {"c": radixly.base32768.BASE32768}),
    "hoisted   g(p)": ("g(p)", {"g": radixly.base32768.BASE32768.encode}),
}


def ns_per_call(statement: str, bindings: dict[str, object], payload: bytes, number: int) -> float:
    """Best-of-REPEAT nanoseconds per call; statement-as-string, min as the statistic."""
    bound = bindings | {"p": payload}  # copy: never mutate the shared SHAPES entries
    totals: list[float] = timeit.repeat(statement, globals=bound, number=number, repeat=REPEAT)
    return min(totals) / number * 1e9


def main() -> None:
    print(f"python   {platform.python_version()}")
    print()
    cases = (
        ("1 B", random.Random(1).randbytes(1), 3_000_000),
        ("187 B", random.Random(187).randbytes(187), 500_000),
    )
    for label, payload, number in cases:
        print(f"encode, {label} payload")
        baseline = 0.0
        for name, (statement, bindings) in SHAPES.items():
            t = ns_per_call(statement, bindings, payload, number)
            if name.startswith("baseline"):
                baseline = t
                print(f"  {name:24} {t:8.3f} ns/call")
            else:
                print(f"  {name:24} {t:8.3f} ns/call   ({t - baseline:+.3f} vs baseline)")
        print()


if __name__ == "__main__":
    main()
