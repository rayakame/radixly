"""Base32768: 15 bits of payload per BMP code point, after qntm's spec.

Encodes arbitrary bytes as dense Unicode text for channels that budget by
code point; decoding is strict and canonical.
"""

from __future__ import annotations

from radixly.base32768._api import *
