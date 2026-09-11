# Copyright (c) 2026-present rayakame
"""Seeded payload construction: any failing size reproduces byte-for-byte."""

from __future__ import annotations

import random


def payload(size: int) -> bytes:
    """Deterministic pseudo-random payload of the given size, so runs compare like for like."""
    return random.Random(size).randbytes(size)
