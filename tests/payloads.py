"""Payload flavors shared by the differential sweeps, one suite-neutral home.

Seeded so any failing length reproduces byte-for-byte; zeros and ones flank
the random flavor to hit the table corners random data misses.
"""

from __future__ import annotations

import random
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ("PAYLOAD_FLAVORS",)


def _random_payload(n: int) -> bytes:
    return random.Random(n).randbytes(n)


def _ones_payload(n: int) -> bytes:
    return b"\xff" * n


PAYLOAD_FLAVORS: dict[str, Callable[[int], bytes]] = {
    "random": _random_payload,
    "zeros": bytes,
    "ones": _ones_payload,
}
