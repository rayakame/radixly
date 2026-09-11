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
"""The PyPI rivals: discovered when installed, absent without complaint, never mistaken for radixly."""

from __future__ import annotations

import typing

from benchmarks import competitors
from benchmarks import registry

if typing.TYPE_CHECKING:
    import pytest


def test_installed_rivals_are_discovered_and_round_trip() -> None:
    """Both rivals ride the bench group, so both must show up, and each must round-trip its own output."""
    found = competitors.discover()
    assert set(found) == {"base2048", "base65536"}
    for codec, specs in found.items():
        assert len(specs) == 1
        (spec,) = specs
        assert spec.name.startswith(f"PyPI {codec} ")
        payload = bytes(range(200))
        assert spec.decode(spec.encode(payload)) == payload


def test_missing_package_is_skipped_silently() -> None:
    assert competitors.discover((("base2048", "radixly-no-such-rival"),)) == {}


def test_install_puts_rivals_next_to_radixly(monkeypatch: pytest.MonkeyPatch) -> None:
    """After install(), every rival is a second implementation row of its codec, with no oracle ratio."""
    monkeypatch.setattr(registry, "COMPETITORS", {})
    competitors.install()
    rows = [(impl.codec, impl.name.split(" ")[0]) for impl in registry.implementations(["base65536", "base2048"])]
    assert rows == [("base65536", "radixly"), ("base65536", "PyPI"), ("base2048", "radixly"), ("base2048", "PyPI")]
    for impl in registry.implementations(["base65536"]):
        if impl.name != "radixly":
            assert impl.reference_encode is None
