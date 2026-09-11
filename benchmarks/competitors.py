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

import importlib
import importlib.metadata
import typing

from benchmarks import registry

if typing.TYPE_CHECKING:
    from collections.abc import Callable

# (radixly codec, PyPI distribution): the module shares the distribution's name and exposes encode/decode.
RIVALS: typing.Final[tuple[tuple[str, str], ...]] = (
    ("base2048", "base2048"),
    ("base65536", "base65536"),
)


def discover(rivals: tuple[tuple[str, str], ...] = RIVALS) -> dict[str, tuple[registry.CompetitorSpec, ...]]:
    """One CompetitorSpec per importable rival, named after the distribution and its installed version."""
    found: dict[str, tuple[registry.CompetitorSpec, ...]] = {}
    for codec, distribution in rivals:
        try:
            module = importlib.import_module(distribution)
        except ImportError:
            continue
        version = importlib.metadata.version(distribution)
        encode = typing.cast("Callable[[bytes], str]", module.encode)  # pyright: ignore[reportAny]
        decode = typing.cast("Callable[[str], bytes]", module.decode)  # pyright: ignore[reportAny]
        spec = registry.CompetitorSpec(f"PyPI {distribution} {version}", encode, decode)
        found[codec] = (*found.get(codec, ()), spec)
    return found


def install() -> None:
    """Register every discovered rival with the benchmark registry; repeat calls are harmless."""
    registry.COMPETITORS.update(discover())
