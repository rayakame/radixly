"""Braille: one byte per braille pattern, U+2800..U+28FF.

Encoded length equals payload length; decoding is strict and canonical.
"""

from __future__ import annotations

from radixly.braille._api import *
