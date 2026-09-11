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
"""The markdown fragment and the splice: provenance, idempotence, refusals."""

from __future__ import annotations

import dataclasses

import pytest

from benchmarks import model
from benchmarks.render import console
from benchmarks.render import markdown
from tests.bench import factories


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


def test_dirty_flag_survives_into_print() -> None:
    """A dirty record once reached the README unnoticed; the provenance line must carry the flag."""
    result = _result()
    dirty = dataclasses.replace(result, environment=dataclasses.replace(result.environment, dirty=True))
    assert "abc1234 (dirty)," in markdown.fragment(dirty)
    assert "(dirty)" not in markdown.fragment(result)


def test_non_record_runs_confess_in_both_renderers() -> None:
    """A --quick or --force artifact must say so wherever it lands."""
    tainted = factories.make_result((factories.make_measurement(),), run=model.RunInfo(mode="quick", forced=True))
    for text in (markdown.fragment(tainted), console.render(tainted)):
        assert "quick" in text
        assert "not a record" in text
        assert "forced" in text
    clean = markdown.fragment(_result()) + console.render(_result())
    assert "not a record" not in clean
    assert "forced" not in clean


def test_codec_page_pairs_light_and_dark_charts() -> None:
    """Furo's toggle classes, never a <picture> that follows the OS."""
    page = markdown.codec_page(_result(), "base32768", "/benchmarks/charts")
    assert "| base32768 | encode |" in page
    assert page.count(":class: only-light") == 2
    assert page.count(":class: only-dark") == 2
    assert "```{image} /benchmarks/charts/base32768/latency.dark.svg" in page
    assert "<picture" not in page


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
