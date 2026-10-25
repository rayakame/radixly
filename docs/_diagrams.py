"""The diagrams the docs embed, drawn at build time from the codecs themselves so they never go stale."""

from __future__ import annotations

import pathlib
import random

import radixly

FG = "var(--color-foreground-primary)"
MUTED = "var(--color-foreground-muted)"
BRAND = "var(--color-brand-primary)"
BORDER = "var(--color-background-border)"
BG2 = "var(--color-background-secondary)"
# Text on a brand fill: white on the light theme's dark teal, near-black on the dark theme's light one.
ON_BRAND = "var(--color-background-primary)"
FONT = 'font-family="var(--font-stack)" font-size="13"'

ASCII = {"base16", "base32", "base32hex", "base64", "base64url", "base85", "z85"}

# Bytes and characters per group, and what happens to a tail that does not fill one.
GROUPS: dict[str, tuple[int, int, str]] = {
    "base16": (1, 2, "every byte stands alone, so there is no tail"),
    "base32": (5, 8, "a shorter tail fills its group with = padding"),
    "base32hex": (5, 8, "a shorter tail fills its group with = padding"),
    "base64": (3, 4, "a shorter tail fills its group with = padding"),
    "base64url": (3, 4, "a shorter tail fills its group with = padding"),
    "base85": (4, 5, "a shorter tail takes one character more than its bytes"),
    "z85": (4, 5, "a shorter tail takes one character more than its bytes"),
    "base32768": (15, 8, "1 to 7 leftover bits take a short character from a second alphabet, 8 to 14 a padded one"),
    "base65536": (2, 1, "a final odd byte takes a character from a block of its own"),
    "base2048": (11, 8, "1 to 3 leftover bits take a short character from a second alphabet, 4 to 10 a padded one"),
    "uro14": (7, 4, "one character ahead of the body states the length; leftover bits are padded with ones"),
    "braille": (1, 1, "every byte stands alone, so there is no tail"),
    "hexagram": (3, 4, "leftover bits are padded with ones"),
}


def _svg(width: int, height: int, label: str, body: list[str]) -> str:
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{label}" {FONT}>'
    return "\n".join([head, *body, "</svg>"])


def density() -> str:
    """What 100 characters hold, one bar per registered codec, densest first."""
    rows = sorted(((name, codec.max_bytes(100)) for name, codec in radixly.CODECS.items()), key=lambda row: -row[1])
    top = rows[0][1]
    row_height, left, bar_max = 26, 110, 500
    height = 30 + (row_height * len(rows)) + 12
    body = [f'<text x="{left}" y="16" fill="{MUTED}" font-size="12">bytes carried by 100 characters</text>']
    for index, (name, held) in enumerate(rows):
        y = 30 + (index * row_height)
        width = bar_max * held / top
        fill, opacity = (BRAND, "0.9") if name in ASCII else (FG, "0.55")
        body.append(
            f'<a href="codecs/{name}.html"><text x="{left - 8}" y="{y + 17}" text-anchor="end" fill="{FG}">{name}</text></a>'
        )
        body.append(
            f'<rect x="{left}" y="{y + 4}" width="{width:.0f}" height="18" rx="4" fill="{fill}" fill-opacity="{opacity}"/>'
        )
        body.append(f'<text x="{left + width + 8:.0f}" y="{y + 17}" fill="{FG}">{held}</text>')
    body.append(f'<rect x="{left}" y="{height - 9}" width="12" height="8" rx="2" fill="{BRAND}" fill-opacity="0.9"/>')
    body.append(f'<text x="{left + 18}" y="{height - 1}" fill="{MUTED}" font-size="12">ASCII</text>')
    body.append(
        f'<rect x="{left + 80}" y="{height - 9}" width="12" height="8" rx="2" fill="{FG}" fill-opacity="0.55"/>'
    )
    body.append(f'<text x="{left + 98}" y="{height - 1}" fill="{MUTED}" font-size="12">Unicode</text>')
    return _svg(720, height, "Bytes that 100 characters hold, per codec", body)


def group(name: str) -> str:
    """One group of a codec: its bytes above, its characters below, the tail rule beneath."""
    group_bytes, group_chars, tail = GROUPS[name]
    bits = group_bytes * 8
    unit = 600 / bits
    x0 = 60
    body = [
        f'<text x="{x0}" y="18" fill="{MUTED}" font-size="12">{group_bytes} byte{"s" if group_bytes > 1 else ""}, {bits} bits</text>'
    ]
    for byte in range(group_bytes):
        x = x0 + (byte * 8 * unit)
        body.append(
            f'<rect x="{x:.1f}" y="26" width="{8 * unit - 4:.1f}" height="28" rx="4" fill="{BG2}" stroke="{BORDER}"/>'
        )
        if group_bytes <= 8:
            body.append(f'<text x="{x + 4 * unit - 2:.1f}" y="45" text-anchor="middle" fill="{FG}">byte {byte}</text>')
    per_char = bits / group_chars
    for char in range(group_chars):
        x = x0 + (char * per_char * unit)
        mid = x + (per_char * unit / 2) - 2
        body.append(f'<path d="M{mid:.1f} 58 L{mid:.1f} 82" stroke="{MUTED}" stroke-width="1.5" fill="none"/>')
        body.append(f'<rect x="{x:.1f}" y="84" width="{per_char * unit - 4:.1f}" height="28" rx="4" fill="{BRAND}"/>')
        body.append(f'<text x="{mid:.1f}" y="103" text-anchor="middle" fill="{ON_BRAND}">{per_char:g} bits</text>')
    body.append(
        f'<text x="{x0}" y="132" fill="{MUTED}" font-size="12">{group_chars} character{"s" if group_chars > 1 else ""}; {tail}</text>'
    )
    return _svg(720, 150, f"{group_bytes} bytes become {group_chars} {name} characters", body)


def choose() -> str:
    """Three questions, one codec; a decision tree with no two arrows crossing."""
    body: list[str] = []

    def box(x: float, y: float, width: float, height: float, text: str, *, strong: bool = False) -> None:
        body.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="6" fill="{BRAND if strong else BG2}" stroke="{BORDER}"/>'
        )
        lines = text.split("\n")
        start = y + (height / 2) - ((len(lines) - 1) * 8.5) + 4.5
        for k, line in enumerate(lines):
            body.append(
                f'<text x="{x + width / 2}" y="{start + k * 17:.1f}" text-anchor="middle" fill="{ON_BRAND if strong else FG}">{line}</text>'
            )

    def arrow(x1: float, y1: float, x2: float, y2: float, label: str = "") -> None:
        body.append(
            f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{MUTED}" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>'
        )
        if label:
            lx, ly = (x1 + x2) / 2, (y1 + y2) / 2
            body.append(
                f'<rect x="{lx - 14}" y="{ly - 9}" width="28" height="16" rx="3" fill="var(--color-background-primary)"/>'
            )
            body.append(
                f'<text x="{lx}" y="{ly + 4}" text-anchor="middle" fill="{MUTED}" font-size="12">{label}</text>'
            )

    body.append(
        f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{MUTED}"/></marker></defs>'
    )
    qx, qw, qh, rx, rw = 20, 260, 46, 440, 240
    questions = [
        (20, "Is the limit a count of\ncharacters, not bytes?", "no", "base64: as UTF-8 nothing\nhere beats it"),
        (110, "Must a cut-off string\nbe caught?", "yes", "uro14"),
        (200, "ASCII only?", "no", "base32768, base65536"),
        (290, "URLs, file names, or a\nchannel that folds case?", "yes", "base64url, base32"),
    ]
    for index, (y, question, branch, result) in enumerate(questions):
        box(qx, y, qw, qh, question)
        box(rx, y, rw, qh, result, strong=True)
        arrow(qx + qw, y + qh / 2, rx, y + qh / 2, branch)
        if index + 1 < len(questions):
            following = questions[index + 1][0]
            arrow(qx + qw / 2, y + qh, qx + qw / 2, following, "yes" if branch == "no" else "no")
    box(rx, 380, rw, qh, "base64, base85", strong=True)
    arrow(qx + qw / 2, 290 + qh, qx + qw / 2, 403, "no")
    arrow(qx + qw / 2, 403, rx, 403)
    return _svg(720, 440, "Four questions that pick a codec", body)


def _sample(length: int, seed: int = 0) -> bytes:
    return random.Random(seed).randbytes(length)


def cost() -> str:
    """What 100 bytes cost in characters, UTF-16 code units and UTF-8 bytes; small multiples on one scale."""
    rows: list[tuple[str, float, float, float]] = []
    for name, codec in radixly.CODECS.items():
        text = codec.encode(_sample(3000))
        rows.append((name, len(text) / 30, len(text.encode("utf-16-le")) / 60, len(text.encode()) / 30))
    rows.sort(key=lambda row: row[1])
    top = max(max(row[1:]) for row in rows)
    row_height, left, panel, bar_max = 24, 100, 205, 150
    height = 40 + (row_height * len(rows))
    body: list[str] = []
    for column, heading in enumerate(("characters", "UTF-16 code units", "UTF-8 bytes")):
        x0 = left + 10 + (column * panel)
        body.append(f'<text x="{x0}" y="18" fill="{MUTED}" font-size="12">{heading}</text>')
        for index, row in enumerate(rows):
            y = 30 + (index * row_height)
            value = row[column + 1]
            width = bar_max * value / top
            body.append(f'<rect x="{x0}" y="{y + 4}" width="{width:.0f}" height="16" rx="3" fill="{BRAND}"/>')
            body.append(f'<text x="{x0 + width + 6:.0f}" y="{y + 16}" fill="{FG}" font-size="12">{value:.0f}</text>')
    for index, row in enumerate(rows):
        y = 30 + (index * row_height)
        body.append(
            f'<a href="../codecs/{row[0]}.html"><text x="{left}" y="{y + 16}" text-anchor="end" fill="{FG}">{row[0]}</text></a>'
        )
    return _svg(720, height, "What 100 bytes of payload cost in characters, UTF-16 code units and UTF-8 bytes", body)


def truncation_rate(name: str) -> float:
    """Share of the cuts of encoded strings that decode without an error, over a spread of payload lengths."""
    codec = radixly.CODECS[name]
    passed = total = 0
    for length in range(48, 96):
        text = codec.encode(_sample(length, seed=length))
        for cut in range(1, len(text)):
            total += 1
            try:
                codec.decode(text[:cut])
            except radixly.DecodeError:
                continue
            passed += 1
    return passed / total


def truncation() -> str:
    """How often a cut-off string decodes without an error, one bar per codec, safest first."""
    rows = sorted(((name, truncation_rate(name)) for name in radixly.CODECS), key=lambda row: row[1])
    row_height, left, bar_max = 26, 110, 500
    height = 30 + (row_height * len(rows))
    body = [f'<text x="{left}" y="16" fill="{MUTED}" font-size="12">cuts that decode without an error</text>']
    for index, (name, rate) in enumerate(rows):
        y = 30 + (index * row_height)
        width = max(bar_max * rate, 2)
        body.append(
            f'<a href="../codecs/{name}.html"><text x="{left - 8}" y="{y + 17}" text-anchor="end" fill="{FG}">{name}</text></a>'
        )
        body.append(f'<rect x="{left}" y="{y + 4}" width="{width:.0f}" height="18" rx="4" fill="{BRAND}"/>')
        body.append(f'<text x="{left + width + 8:.0f}" y="{y + 17}" fill="{FG}">{rate:.0%}</text>')
    return _svg(720, height, "Share of truncated strings that decode without an error, per codec", body)


def write_all(directory: pathlib.Path) -> None:
    """Write every diagram into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "density.svg").write_text(density(), encoding="utf-8")
    (directory / "choose.svg").write_text(choose(), encoding="utf-8")
    (directory / "cost.svg").write_text(cost(), encoding="utf-8")
    (directory / "truncation.svg").write_text(truncation(), encoding="utf-8")
    for name in GROUPS:
        (directory / f"{name}-group.svg").write_text(group(name), encoding="utf-8")
