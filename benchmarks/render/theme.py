# Copyright (c) 2026-present rayakame
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Light and dark palettes. Backgrounds are transparent so the charts sit on any page."""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True, slots=True)
class Theme:
    """One chart palette; light and dark are two instances."""

    name: str
    text: str
    muted: str
    grid: str
    encode: str
    decode: str
    competitors: tuple[str, ...]  # stable ramp for comparison implementations


LIGHT = Theme(
    name="light",
    text="#1b2531",
    muted="#5a6673",
    grid="#d8dde6",
    encode="#2563eb",
    decode="#d97706",
    competitors=("#059669", "#dc2626", "#7c3aed"),
)

DARK = Theme(
    name="dark",
    text="#e6eaf2",
    muted="#9aa6b8",
    grid="#3a4456",
    encode="#60a5fa",
    decode="#fbbf24",
    competitors=("#34d399", "#f87171", "#a78bfa"),
)

THEMES: tuple[Theme, ...] = (LIGHT, DARK)
