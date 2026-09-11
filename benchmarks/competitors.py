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
"""Rival implementations from PyPI, picked up when installed. A missing package only loses its rows."""

from __future__ import annotations

import dataclasses
import importlib
import importlib.metadata
import typing

from benchmarks import registry

if typing.TYPE_CHECKING:
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


_PROBE: typing.Final = bytes(range(8))


def _probe(distribution: str, spec: registry.CompetitorSpec) -> None:
    """Refuse a rival that cannot round-trip a small payload under radixly's contracts."""
    encoded = spec.encode(_PROBE)
    if not isinstance(encoded, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        msg = f"{distribution}.encode returned {type(encoded).__name__}, not str"
        raise TypeError(msg)
    if spec.decode(encoded) != _PROBE:
        msg = f"{distribution} does not round-trip its own output"
        raise ValueError(msg)


def discover(rivals: tuple[Rival, ...] | None = None) -> dict[str, tuple[registry.CompetitorSpec, ...]]:
    """One CompetitorSpec per installed rival, named after distribution and version, flagged for another alphabet."""
    found: dict[str, tuple[registry.CompetitorSpec, ...]] = {}
    for rival in RIVALS if rivals is None else rivals:
        try:
            module = importlib.import_module(rival.distribution)
        except ModuleNotFoundError as error:
            # Only the rival's own absence is skipped; a broken install of a present rival must be loud.
            if error.name != rival.distribution:
                raise
            continue
        # Outside the guard on purpose: a module without metadata is a shadowing file, not an absent package.
        version = importlib.metadata.version(rival.distribution)
        encode = typing.cast("Callable[[bytes], str]", module.encode)
        decode = typing.cast("Callable[[str], bytes]", module.decode)
        suffix = "" if rival.wire_compatible else ", other alphabet"
        spec = registry.CompetitorSpec(f"PyPI {rival.distribution} {version}{suffix}", encode, decode)
        _probe(rival.distribution, spec)
        found[rival.codec] = (*found.get(rival.codec, ()), spec)
    return found


def install() -> list[str]:
    """Register every discovered rival; returns the distributions that were not found. Repeat calls are harmless."""
    found = discover()
    registry.COMPETITORS.update(found)
    return [rival.distribution for rival in RIVALS if rival.codec not in found]
