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
"""Rivals from PyPI, when installed, and from the standard library. A missing package only loses its rows."""

from __future__ import annotations

import base64
import dataclasses
import importlib
import importlib.metadata
import platform
import typing

import radixly
from benchmarks import registry

if typing.TYPE_CHECKING:
    import types
    from collections.abc import Callable


@dataclasses.dataclass(frozen=True, slots=True)
class Rival:
    """A PyPI distribution whose module of the same name exposes encode and decode."""

    codec: str
    distribution: str
    wire_compatible: bool  # False: same density, different alphabet; a speed comparison only


RIVALS: typing.Final[tuple[Rival, ...]] = (
    Rival("base2048", "base2048", wire_compatible=False),
    Rival("base65536", "base65536", wire_compatible=True),
)


@dataclasses.dataclass(frozen=True, slots=True)
class StdlibRival:
    """A standard library pair; its bytes result is decoded to str so the contracts match radixly's."""

    codec: str
    encode_name: str
    decode_name: str


STDLIB_RIVALS: typing.Final[tuple[StdlibRival, ...]] = (
    StdlibRival("base16", "b16encode", "b16decode"),
    StdlibRival("base32", "b32encode", "b32decode"),
    StdlibRival("base32hex", "b32hexencode", "b32hexdecode"),
)


_PROBE: typing.Final = bytes(range(8))


def _probe(label: str, codec: str, spec: registry.CompetitorSpec, *, wire_compatible: bool) -> None:
    """Refuse a rival that breaks radixly's contracts on a small payload, or one whose compatibility flag lies."""
    encoded = spec.encode(_PROBE)
    if not isinstance(encoded, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        msg = f"{label}.encode returned {type(encoded).__name__}, not str"
        raise TypeError(msg)
    decoded = spec.decode(encoded)
    if not isinstance(decoded, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
        msg = f"{label}.decode returned {type(decoded).__name__}, not bytes"
        raise TypeError(msg)
    if decoded != _PROBE:
        msg = f"{label} does not round-trip its own output"
        raise ValueError(msg)
    if wire_compatible and encoded != radixly.CODECS[codec].encode(_PROBE):
        msg = f"{label} is flagged wire-compatible but encodes differently from radixly"
        raise ValueError(msg)


def _import_rival(distribution: str) -> types.ModuleType | None:
    """Import the rival, or return None when the distribution itself is absent; a broken install stays loud."""
    try:
        return importlib.import_module(distribution)
    except ModuleNotFoundError as error:
        if error.name != distribution:
            raise
        return None


def discover(rivals: tuple[Rival, ...] | None = None) -> dict[str, tuple[registry.CompetitorSpec, ...]]:
    """One CompetitorSpec per installed rival, named after distribution and version, flagged for another alphabet."""
    found: dict[str, tuple[registry.CompetitorSpec, ...]] = {}
    for rival in RIVALS if rivals is None else rivals:
        module = _import_rival(rival.distribution)
        if module is None:
            continue
        # Outside the guard on purpose: a module without metadata is a shadowing file, not an absent package.
        version = importlib.metadata.version(rival.distribution)
        encode = typing.cast("Callable[[bytes], str]", module.encode)
        decode = typing.cast("Callable[[str], bytes]", module.decode)
        suffix = "" if rival.wire_compatible else ", other alphabet"
        spec = registry.CompetitorSpec(f"PyPI {rival.distribution} {version}{suffix}", encode, decode)
        _probe(rival.distribution, rival.codec, spec, wire_compatible=rival.wire_compatible)
        found[rival.codec] = (*found.get(rival.codec, ()), spec)
    return found


def stdlib_specs(rivals: tuple[StdlibRival, ...] | None = None) -> dict[str, tuple[registry.CompetitorSpec, ...]]:
    """One CompetitorSpec per standard library pair, labeled with the interpreter version."""
    found: dict[str, tuple[registry.CompetitorSpec, ...]] = {}
    version = platform.python_version()
    for rival in STDLIB_RIVALS if rivals is None else rivals:
        encode = typing.cast("Callable[[bytes], bytes]", getattr(base64, rival.encode_name))
        decode = typing.cast("Callable[[str], bytes]", getattr(base64, rival.decode_name))

        def encode_to_str(data: bytes, encode: Callable[[bytes], bytes] = encode) -> str:
            return encode(data).decode("ascii")

        spec = registry.CompetitorSpec(f"stdlib base64 {version}", encode_to_str, decode)
        _probe(f"stdlib base64.{rival.encode_name}", rival.codec, spec, wire_compatible=True)
        found[rival.codec] = (spec,)
    return found


def install() -> list[Rival]:
    """Register every discovered rival; returns the rivals that are not installed. Repeat calls are harmless."""
    found = discover()
    for codec, specs in stdlib_specs().items():
        found[codec] = (*found.get(codec, ()), *specs)
    registry.COMPETITORS.update(found)
    return [rival for rival in RIVALS if _import_rival(rival.distribution) is None]
