"""uro14: 14 bits per CJK character behind a length-prefix character.

The prefix makes every tail truncation detectable; decoding is strict and
canonical.
"""

from __future__ import annotations

from radixly.uro14._api import *
