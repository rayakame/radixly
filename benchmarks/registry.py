"""What to measure: every registered codec, references resolved by convention.

A new codec joins the benchmarks by registering itself in radixly -- which its
_api module does anyway. A codec without a tests.reference twin only loses
its ratio rows.
"""

from __future__ import annotations

import dataclasses
import importlib
import pathlib
import re
import sys
import typing

import radixly

if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

SIZES: tuple[tuple[str, int], ...] = (
    ("1 B", 1),
    ("200 B", 200),
    ("64 KiB", 65536),
    ("1 MiB", 2**20),
)

# The size whose rows also time the reference and carry the C-vs-oracle ratio.
RATIO_SIZE_LABEL: typing.Final = "200 B"

_UNITS: typing.Final = {"": ("B", 1), "b": ("B", 1), "kib": ("KiB", 1024), "mib": ("MiB", 1024**2)}
_SIZE_TOKEN: typing.Final = re.compile(r"^(\d+)\s*([A-Za-z]*)$")


def parse_sizes(spec: str) -> tuple[tuple[str, int], ...]:
    """Comma-separated human sizes: "1B,200B,64KiB,1MiB" -> labeled byte counts."""
    rows: list[tuple[str, int]] = []
    for token in spec.split(","):
        match = _SIZE_TOKEN.match(token.strip())
        unit = _UNITS.get(match.group(2).lower()) if match is not None else None
        if match is None or unit is None:
            msg = f"invalid size {token.strip()!r}; use forms like 200B, 64KiB, 1MiB"
            raise ValueError(msg)
        count = int(match.group(1))
        rows.append((f"{count} {unit[0]}", count * unit[1]))
    return tuple(rows)  # split() never yields zero tokens; an empty token errors above


class ReferenceCodec(typing.Protocol):
    """The shape every tests.reference module shares."""

    @property
    def encode(self) -> Callable[[bytes], str]: ...
    @property
    def decode(self) -> Callable[[str], bytes]: ...


@dataclasses.dataclass(frozen=True, slots=True)
class CodecSpec:
    name: str
    encode: Callable[[bytes], str]
    decode: Callable[[str], bytes]
    reference_encode: Callable[[bytes], str] | None
    reference_decode: Callable[[str], bytes] | None


def reference_module(name: str) -> ReferenceCodec | None:
    # `python -m benchmarks` from the repo root already has the root on
    # sys.path; the insert covers other invocation styles (`tests.` must resolve).
    root = str(pathlib.Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        module = importlib.import_module(f"tests.reference.{name}")
    except ImportError:
        return None
    # Modules satisfy the protocol structurally; pyright wants the detour via object.
    return typing.cast("ReferenceCodec", typing.cast("object", module))


@dataclasses.dataclass(frozen=True, slots=True)
class CompetitorSpec:
    """A rival implementation of a codec, measured for comparison charts.

    encode/decode must match radixly's contracts (bytes -> str, str -> bytes);
    adapters will live in a competitors module, their cost visible, when the
    first rival arrives with base64.
    """

    name: str
    encode: Callable[[bytes], str]
    decode: Callable[[str], bytes]


# codec name -> its rivals. Empty until base64 exists (stdlib, pybase64).
COMPETITORS: dict[str, tuple[CompetitorSpec, ...]] = {}


@dataclasses.dataclass(frozen=True, slots=True)
class Implementation:
    """One measurable implementation: radixly's own, or a competitor's."""

    codec: str
    name: str
    encode: Callable[[bytes], str]
    decode: Callable[[str], bytes]
    reference_encode: Callable[[bytes], str] | None
    reference_decode: Callable[[str], bytes] | None


def implementations(names: Sequence[str] | None = None) -> list[Implementation]:
    """radixly first, then any rivals; competitors ride their codec's selection."""
    rows: list[Implementation] = []
    for spec in specs(names):
        rows.append(
            Implementation(spec.name, "radixly", spec.encode, spec.decode, spec.reference_encode, spec.reference_decode)
        )
        rows.extend(
            Implementation(spec.name, rival.name, rival.encode, rival.decode, None, None)
            for rival in COMPETITORS.get(spec.name, ())
        )
    return rows


def specs(names: Sequence[str] | None = None) -> list[CodecSpec]:
    chosen = dict(radixly.CODECS) if names is None else {name: radixly.get_codec(name) for name in names}
    result: list[CodecSpec] = []
    for name, codec in chosen.items():
        reference = reference_module(name)
        result.append(
            CodecSpec(
                name=name,
                encode=codec.encode,
                decode=codec.decode,
                reference_encode=reference.encode if reference is not None else None,
                reference_decode=reference.decode if reference is not None else None,
            )
        )
    return result
