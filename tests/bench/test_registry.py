"""Deterministic tests for the benchmark suite's discovery and calibration."""

from __future__ import annotations

import dataclasses

import pytest

import radixly
from benchmarks import registry
from benchmarks import timing
from radixly import _codec
from tests.reference import base32768 as base32768_reference


def test_every_registered_codec_is_discovered() -> None:
    assert [spec.name for spec in registry.specs()] == list(radixly.CODECS)


def test_new_codec_appears_without_benchmark_changes() -> None:
    """The extensibility contract: registering is joining the benchmarks."""
    fake = dataclasses.replace(radixly.base32768.BASE32768, name="bench-fake-codec")
    radixly.register(fake)
    try:
        spec = next(s for s in registry.specs() if s.name == "bench-fake-codec")
        assert spec.encode is fake.encode
        assert spec.reference_encode is None  # no tests.reference twin: ratio rows drop out
    finally:
        _codec._registry.pop("bench-fake-codec")  # pyright: ignore[reportPrivateUsage]


def test_implementations_expand_competitors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rivals ride their codec: no runner or chart changes when one appears."""
    rival = registry.CompetitorSpec("fakelib", radixly.base32768.encode, radixly.base32768.decode)
    monkeypatch.setitem(registry.COMPETITORS, "base32768", (rival,))
    rows = [(impl.codec, impl.name) for impl in registry.implementations(["base32768"])]
    assert rows == [("base32768", "radixly"), ("base32768", "fakelib")]
    fake = next(impl for impl in registry.implementations(["base32768"]) if impl.name == "fakelib")
    assert fake.reference_encode is None  # no oracle ratios for rivals


def test_reference_resolved_by_convention() -> None:
    spec = next(s for s in registry.specs(["base32768"]))
    assert spec.reference_encode is base32768_reference.encode
    assert spec.reference_decode is base32768_reference.decode


def test_every_registered_codec_resolves_its_reference() -> None:
    """No oracle, no ratio, no CI gate: a codec whose tests/reference twin
    fails to resolve would silently lose its gate coverage."""
    for spec in registry.specs():
        assert spec.reference_encode is not None, f"{spec.name}: reference encode did not resolve"
        assert spec.reference_decode is not None, f"{spec.name}: reference decode did not resolve"


def test_ratio_size_is_a_configured_size() -> None:
    """The ratio rows must reference a size that actually runs."""
    assert registry.RATIO_SIZE_LABEL in {label for label, _ in registry.SIZES}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0.3, 1), (1, 1), (3, 2), (9, 5), (10, 10), (49, 20), (50, 50), (999, 500), (3_000_000, 2_000_000)],
)
def test_round_to_grid(raw: float, expected: int) -> None:
    assert timing.round_to_grid(raw) == expected


def test_grid_is_monotonic_and_bounded() -> None:
    """The count never exceeds the raw target and never regresses as raw grows."""
    previous = 0
    for raw in range(1, 10_000):
        count = timing.round_to_grid(raw)
        assert count <= raw
        assert count >= previous
        previous = count
