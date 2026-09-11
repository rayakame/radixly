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

import importlib.metadata
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
    with pytest.raises(ModuleNotFoundError) as exc_info:
        competitors.discover((broken,))
    assert exc_info.value.name == "radixly_broken_rival._ext"  # the discriminator discover() branches on


def _fake_distribution(root: pathlib.Path, name: str, source: str) -> None:
    """Build a one-file module with just enough dist-info for importlib.metadata to find a version."""
    (root / f"{name}.py").write_text(source, encoding="utf-8")
    info = root / f"{name}-0.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 0.0\n", encoding="utf-8")


def test_rival_returning_bytes_is_refused(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_distribution(tmp_path, "radixly_bytes_rival", "encode = lambda data: bytes(data)\ndecode = bytes\n")
    monkeypatch.syspath_prepend(str(tmp_path))  # pyright: ignore[reportUnknownMemberType]
    rival = competitors.Rival("base2048", "radixly_bytes_rival", wire_compatible=True)
    with pytest.raises(TypeError, match="not str"):
        competitors.discover((rival,))


def test_rival_that_cannot_round_trip_is_refused(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = "encode = lambda data: data.hex()\ndecode = lambda text: b''\n"
    _fake_distribution(tmp_path, "radixly_lying_rival", source)
    monkeypatch.syspath_prepend(str(tmp_path))  # pyright: ignore[reportUnknownMemberType]
    rival = competitors.Rival("base2048", "radixly_lying_rival", wire_compatible=True)
    with pytest.raises(ValueError, match="round-trip"):
        competitors.discover((rival,))


def test_shadowing_module_without_metadata_is_loud(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stray module of the rival's name is not the package; the version lookup must not be swallowed."""
    (tmp_path / "radixly_shadow_rival.py").write_text("encode = str\ndecode = bytes\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))  # pyright: ignore[reportUnknownMemberType]
    rival = competitors.Rival("base2048", "radixly_shadow_rival", wire_compatible=True)
    with pytest.raises(importlib.metadata.PackageNotFoundError):
        competitors.discover((rival,))


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
