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
"""The drop-in suite: every function covered, both sides on equal work, rows that survive the record."""

from __future__ import annotations

import base64
import dataclasses
import json
import sys
import typing
import xml.etree.ElementTree as ET  # ruff: ignore[suspicious-xml-etree-import] -- parsing our own generated SVGs

import pytest

from benchmarks import cli
from benchmarks import compat
from benchmarks import environment
from benchmarks import model
from benchmarks.render import console
from benchmarks.render import graphs
from benchmarks.render import markdown
from radixly.compat import base64 as compat_base64
from tests.bench import factories

if typing.TYPE_CHECKING:
    import io
    import pathlib


def test_every_drop_in_function_is_timed() -> None:
    """A function added to the drop-in without a row here would go unmeasured and unnoticed."""
    public = {name for name in compat_base64.__all__ if callable(typing.cast("object", getattr(compat_base64, name)))}
    timed = {function.name for function in compat.FUNCTIONS}
    assert public <= timed
    # z85 joined the standard library, and so the drop-in, in 3.13.
    assert timed - public == (set() if sys.version_info >= (3, 13) else {"z85encode", "z85decode"})
    assert len(compat.FUNCTIONS) == 22


def test_pairs_follow_the_interpreter() -> None:
    names = {pair.function.name for pair in compat.pairs()}
    assert ("z85encode" in names) is (sys.version_info >= (3, 13))
    assert len(names) == (22 if sys.version_info >= (3, 13) else 20)


_PAIRS = compat.pairs()


@pytest.mark.parametrize("pair", _PAIRS, ids=[pair.function.name for pair in _PAIRS])
def test_both_sides_do_the_same_work(pair: compat.Pair) -> None:
    """Decoders get the standard library's own encoding, and both sides must agree on it before a row is timed."""
    value = compat.prepare(pair.function, bytes(range(256)) * 3)
    compat.check(pair, value)
    pair.ours(value)
    pair.stdlib(value)


def test_a_disagreement_refuses_to_be_timed() -> None:
    (real,) = compat.pairs((compat.Function("b64encode", "encode"),))

    def wrong(data: bytes) -> bytes:
        return base64.b64encode(data) + b"="

    with pytest.raises(ValueError, match="disagree"):
        compat.check(dataclasses.replace(real, ours=wrong), b"hello")


def test_a_file_pair_disagreement_refuses_to_be_timed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The file pair returns nothing; its output stream is what must agree."""
    (pair,) = compat.pairs((compat.Function("encode", "encode", file_pair=True),))
    compat.check(pair, b"hello")

    def wrong(source: io.BytesIO, output: io.BytesIO) -> None:
        output.write(base64.b64encode(source.read()))

    monkeypatch.setattr(compat_base64, "encode", wrong)
    with pytest.raises(ValueError, match="disagree"):
        compat.check(pair, b"hello")


def test_measure_covers_sizes_and_directions() -> None:
    rows = compat.measure((("1 B", 1), ("16 B", 16)), ("decode",), repeat=1, target=0.0001)
    assert {row.direction for row in rows} == {"decode"}
    assert {row.size_label for row in rows} == {"1 B", "16 B"}
    assert len(rows) == 2 * sum(pair.function.direction == "decode" for pair in compat.pairs())
    assert all(row.speedup > 0 for row in rows)


def _document(result: model.RunResult) -> dict[str, list[dict[str, object]]]:
    return typing.cast("dict[str, list[dict[str, object]]]", json.loads(model.to_json(result)))


def test_compat_rows_round_trip_and_legacy_records_load() -> None:
    result = factories.make_result(compat=(factories.make_compat(), factories.make_compat("b16encode")))
    assert model.from_json(model.to_json(result)) == result
    document = _document(result)
    assert document["compat_measurements"][0]["speedup"] == pytest.approx(2.5)
    del document["compat_measurements"]
    assert model.from_json(json.dumps(document)).compat == ()


def test_compat_rows_are_held_to_the_domain_checks() -> None:
    document = _document(factories.make_result(compat=(factories.make_compat(),)))
    document["compat_measurements"][0]["stdlib_ns_per_call"] = 0
    with pytest.raises(ValueError, match="positive finite"):
        model.from_json(json.dumps(document))


def test_compat_page_lists_every_function_at_every_size() -> None:
    rows = (
        factories.make_compat(),
        factories.make_compat(
            size_label="1 MiB", size_bytes=2**20, ns_per_call=300_000.0, stdlib_ns_per_call=300_000.0
        ),
        factories.make_compat("encode", ns_per_call=100.0, stdlib_ns_per_call=70.0),
    )
    page = markdown.compat_page(factories.make_result(compat=rows), "/benchmarks/charts")
    assert page.startswith(markdown.GENERATED)
    assert "| function | 200 B | 1 MiB |" in page
    assert "| `b64decode` | 2.50x | 1.00x |" in page
    assert "| `encode` | 0.70x | — |" in page
    assert "Measured on TestCPU" in page
    assert "```{image} /benchmarks/charts/compat/speedup.dark.svg" in page


def test_a_record_without_compat_rows_says_so() -> None:
    page = markdown.compat_page(factories.make_result(), "/benchmarks/charts")
    assert page.startswith(markdown.GENERATED)
    assert "no drop-in measurements" in page
    assert "{image}" not in page


def test_console_reports_compat_rows() -> None:
    text = console.render(factories.make_result(compat=(factories.make_compat(),)))
    assert "radixly.compat.base64 vs the standard library" in text
    assert "b64decode" in text
    assert "2.50x" in text


def test_speedup_chart_lands_in_both_themes(tmp_path: pathlib.Path) -> None:
    rows = (
        factories.make_compat(),
        factories.make_compat(size_label="1 MiB", size_bytes=2**20),
        factories.make_compat("encode", ns_per_call=100.0, stdlib_ns_per_call=70.0),
    )
    written = graphs.write_charts(factories.make_result(compat=rows), tmp_path)
    compat_charts = sorted(path.name for path in written if path.parent.name == "compat")
    assert compat_charts == ["speedup.dark.svg", "speedup.svg"]
    svg = (tmp_path / "compat" / "speedup.svg").read_text(encoding="utf-8")
    ET.fromstring(svg)  # ruff: ignore[suspicious-xml-element-tree-usage] -- our own SVG
    assert "200 B payloads" in svg
    assert "1 MiB payloads" in svg


def test_no_compat_rows_means_no_speedup_chart(tmp_path: pathlib.Path) -> None:
    written = graphs.write_charts(factories.make_result(), tmp_path)
    assert not any(path.parent.name == "compat" for path in written)


def test_docs_always_carry_the_compat_fragment(tmp_path: pathlib.Path) -> None:
    docs = tmp_path / "docs" / "benchmarks"
    docs.parent.mkdir()
    charts = tmp_path / "charts"
    charts.mkdir()
    written = cli.write_docs(factories.make_result(), docs, charts)
    assert docs / "compat.md" in written
    assert "no drop-in measurements" in (docs / "compat.md").read_text(encoding="utf-8")


def test_compat_suite_scope_rules() -> None:
    assert cli.parse_options(["--suite", "compat"]).suite == "compat"
    for argv in (
        ["--suite", "compat", "--codecs", "uro14"],
        ["--suite", "compat", "--docs", "docs/benchmarks"],
        ["--suite", "compat", "--inject", "README.md"],
    ):
        with pytest.raises(SystemExit):
            cli.parse_options(argv)


def test_compat_suite_runs_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environment, "capture", factories.make_environment)
    config = cli.RunConfig(
        mode="quick",
        sizes=(("1 B", 1),),
        directions=("encode",),
        repeat=1,
        target=0.0001,
        codec_suite=False,
        compat_suite=True,
    )
    result = cli.run(config)
    assert result.measurements == ()
    assert {row.function for row in result.compat} >= {"b64encode", "a85encode", "encode"}
