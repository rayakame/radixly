"""Deterministic CLI pieces: size parsing, option resolution, wrapper shapes."""

from __future__ import annotations

import pytest

from benchmarks import cli
from benchmarks import registry
from benchmarks import wrapper


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("1B", (("1 B", 1),)),
        ("200B", (("200 B", 200),)),
        ("300", (("300 B", 300),)),
        ("64KiB", (("64 KiB", 65536),)),
        ("2kib", (("2 KiB", 2048),)),
        ("1MiB", (("1 MiB", 1048576),)),
        ("1 B, 200B", (("1 B", 1), ("200 B", 200))),
    ],
)
def test_parse_sizes(spec: str, expected: tuple[tuple[str, int], ...]) -> None:
    assert registry.parse_sizes(spec) == expected


@pytest.mark.parametrize("bad", ["", "12XB", "abc", "1B,,200B", "1GB"])
def test_parse_sizes_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError, match="invalid size"):
        registry.parse_sizes(bad)


def test_default_options_are_the_complete_run() -> None:
    options = cli.parse_options([])
    assert options == cli.Options(
        codecs=None,
        sizes=None,
        directions=("encode", "decode"),
        suite="all",
        quick=False,
        json_path=None,
        force=False,
        ci_mode=False,
        markdown_path=None,
        graphs_dir=None,
        render_from=None,
        inject_path=None,
    )


def test_scoped_options() -> None:
    options = cli.parse_options(["--codecs", "uro14,braille", "--sizes", "1B", "--directions", "decode", "--quick"])
    assert options.codecs == ("uro14", "braille")
    assert options.sizes == (("1 B", 1),)
    assert options.directions == ("decode",)
    assert options.quick is True


def test_directions_keep_canonical_order() -> None:
    assert cli.parse_options(["--directions", "decode,encode"]).directions == ("encode", "decode")


@pytest.mark.parametrize(
    "argv",
    [
        ["--directions", "sideways"],
        ["--sizes", "1XB"],
        ["--suite", "wrapper", "--json", "out.json"],
        ["--suite", "everything"],
        ["--render-from", "r.json", "--quick"],
        ["--render-from", "r.json", "--codecs", "uro14"],
        ["--render-from", "r.json", "--json", "out.json"],
        ["--suite", "wrapper", "--markdown", "frag.md"],
        ["--suite", "wrapper", "--graphs", "out"],
        ["--ci", "--render-from", "r.json"],
    ],
)
def test_bad_arguments_exit(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        cli.parse_options(argv)


def test_wrapper_shapes_are_distinct_statements() -> None:
    """Four identical statements would measure the same call and prove nothing."""
    statements = [statement for _, statement, _ in wrapper._SHAPES]  # pyright: ignore[reportPrivateUsage]
    assert len(set(statements)) == len(statements)
    assert "m.encode(p)" in statements  # the dotted access lives inside the timed statement
