"""Seeded payload construction: any failing size reproduces byte-for-byte."""

from __future__ import annotations

import random


def payload(size: int) -> bytes:
    return random.Random(size).randbytes(size)
