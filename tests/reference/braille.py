"""Braille preset: 8 bits per character, one byte per braille pattern."""

from __future__ import annotations

import typing

from tests.reference import block

START: typing.Final[int] = 0x2800
BITS_PER_CHAR: typing.Final[int] = 8


def encode(data: bytes) -> str:
    """Encode bytes as braille patterns."""
    return block.encode(data, START, BITS_PER_CHAR)


def decode(string: str) -> bytes:
    """Decode braille patterns back to bytes."""
    return block.decode(string, START, BITS_PER_CHAR)
