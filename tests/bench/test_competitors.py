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
"""The PyPI rivals: found when installed, absent without complaint, broken installs loud, never mistaken for radixly."""

from __future__ import annotations

import typing

import pytest

import radixly
from benchmarks import competitors
from benchmarks import registry

if typing.TYPE_CHECKING:
    import pathlib


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


def test_wire_compatibility_flags_are_true_to_the_packages() -> None:
    """A compatible rival encodes byte-identically to radixly; an incompatible one must say so in its label."""
    found = competitors.discover()
    payloads = [bytes(range(n)) for n in (0, 1, 2, 3, 16, 200)]
    for rival in competitors.RIVALS:
        (spec,) = found[rival.codec]
        ours = radixly.CODECS[rival.codec].encode
        agreements = sum(spec.encode(payload) == ours(payload) for payload in payloads)
        if rival.wire_compatible:
            assert agreements == len(payloads), f"{rival.distribution} drifted from the spec; drop the flag"
            assert "other alphabet" not in spec.name
        else:
            assert agreements < len(payloads), f"{rival.distribution} now agrees with radixly; flip the flag"
            assert spec.name.endswith(", other alphabet")


def test_missing_package_is_skipped_silently() -> None:
    absent = competitors.Rival("base2048", "radixly-no-such-rival", wire_compatible=True)
    assert competitors.discover((absent,)) == {}


def test_broken_install_of_a_present_rival_is_loud(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rival whose own import fails is not "absent": the record must not silently lose its rows."""
    package = tmp_path / "radixly_broken_rival"
    package.mkdir()
    (package / "__init__.py").write_text("from radixly_broken_rival._ext import encode\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))  # pyright: ignore[reportUnknownMemberType]
    broken = competitors.Rival("base2048", "radixly_broken_rival", wire_compatible=True)
    with pytest.raises(ModuleNotFoundError, match="_ext"):
        competitors.discover((broken,))


def test_install_puts_rivals_next_to_radixly(monkeypatch: pytest.MonkeyPatch) -> None:
    """After install(), every rival is a second implementation row of its codec, with no oracle ratio."""
    monkeypatch.setattr(registry, "COMPETITORS", {})
    assert competitors.install() == []
    assert competitors.install() == []  # repeat calls replace, never duplicate
    rows = [(impl.codec, impl.name.split(" ")[0]) for impl in registry.implementations(["base65536", "base2048"])]
    assert rows == [("base65536", "radixly"), ("base65536", "PyPI"), ("base2048", "radixly"), ("base2048", "PyPI")]
    for impl in registry.implementations(["base65536"]):
        if impl.name != "radixly":
            assert impl.reference_encode is None


def test_install_reports_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "COMPETITORS", {})
    absent = competitors.Rival("base2048", "radixly-no-such-rival", wire_compatible=True)
    monkeypatch.setattr(competitors, "RIVALS", (absent,))
    assert competitors.install() == ["radixly-no-such-rival"]
    assert registry.COMPETITORS == {}
