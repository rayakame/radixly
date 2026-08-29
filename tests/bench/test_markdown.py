"""The markdown fragment and the splice: provenance, idempotence, refusals."""

from __future__ import annotations

import typing

import pytest

from benchmarks.render import markdown
from tests.bench import factories

if typing.TYPE_CHECKING:
    from benchmarks import model


def _result() -> model.RunResult:
    return factories.make_result(
        (
            factories.make_measurement(),
            factories.make_measurement(
                size_label="1 MiB", size_bytes=2**20, ns_per_call=540_000.0, reference_ns_per_call=None
            ),
            factories.make_measurement(direction="decode", ns_per_call=20.0, reference_ns_per_call=None),
        )
    )


def test_fragment_carries_markers_and_provenance() -> None:
    wrapped = markdown.fragment(_result())
    assert wrapped.startswith(markdown.BEGIN)
    assert wrapped.rstrip("\n").endswith(markdown.END)
    assert "Measured on TestCPU (performance governor)" in wrapped
    assert "abc1234" in wrapped


def test_fragment_cells() -> None:
    wrapped = markdown.fragment(_result())
    assert "| base32768 | encode | 0.018 μs | 1,942 MB/s | 100x at 1 B |" in wrapped
    assert "| base32768 | decode | 0.020 μs | — | — |" in wrapped  # no 1 MiB decode row, no reference


def test_inject_replaces_only_the_block() -> None:
    document = f"# Title\n\nprose above\n\n{markdown.BEGIN}\nstale table\n{markdown.END}\n\nprose below\n"
    wrapped = markdown.fragment(_result())
    spliced = markdown.inject(document, wrapped)
    assert "stale table" not in spliced
    assert spliced.startswith("# Title\n\nprose above\n\n")
    assert spliced.endswith("\n\nprose below\n")


def test_inject_is_idempotent() -> None:
    document = f"before\n{markdown.BEGIN}\nold\n{markdown.END}\nafter\n"
    wrapped = markdown.fragment(_result())
    once = markdown.inject(document, wrapped)
    assert markdown.inject(once, wrapped) == once


@pytest.mark.parametrize(
    "document",
    [
        "no markers at all\n",
        f"only begin\n{markdown.BEGIN}\n",
        f"reversed\n{markdown.END}\nthen\n{markdown.BEGIN}\n",
        f"{markdown.BEGIN}\n{markdown.END}\n{markdown.BEGIN}\n{markdown.END}\n",
    ],
    ids=["none", "half", "reversed", "duplicated"],
)
def test_inject_refuses_ambiguous_documents(document: str) -> None:
    with pytest.raises(ValueError, match=r"marker|block"):
        markdown.inject(document, markdown.fragment(_result()))
