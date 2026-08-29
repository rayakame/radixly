"""The light/dark palette pair, defined once for every chart.

Backgrounds are transparent on purpose: the docs embed both variants via
``<picture><source media="(prefers-color-scheme: dark)">``, and transparency
lets each sit on whatever surface the page provides.
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True, slots=True)
class Theme:
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
