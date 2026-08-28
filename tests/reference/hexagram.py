"""Hexagram preset: 6 bits per character from the Yijing hexagram block."""

from __future__ import annotations

import typing

from tests.reference import block

START: typing.Final[int] = 0x4DC0
BITS_PER_CHAR: typing.Final[int] = 6


def encode(data: bytes) -> str:
    """Encode bytes as hexagram symbols."""
    return block.encode(data, START, BITS_PER_CHAR)


def decode(string: str) -> bytes:
    """Decode hexagram symbols back to bytes."""
    return block.decode(string, START, BITS_PER_CHAR)
