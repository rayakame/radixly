"""Deterministic CLI pieces: size parsing, option resolution, wrapper shapes,
the non-optimized guard on both doors, and the --ci verdict end to end."""

from __future__ import annotations

import dataclasses
import json
import typing

import pytest

from benchmarks import ci
from benchmarks import cli
from benchmarks import environment
from benchmarks import model
from benchmarks import registry
from benchmarks import wrapper
from benchmarks.render import markdown
from tests.bench import factories

if typing.TYPE_CHECKING:
    import pathlib


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
        ["--render-from", "r.json", "--suite", "codecs"],
        ["--render-from", "r.json", "--force"],
        ["--suite", "wrapper", "--codecs", "uro14"],
        ["--suite", "wrapper", "--sizes", "1B"],
        ["--ci", "--codecs", "uro14"],
        ["--ci", "--sizes", "1B"],
        ["--ci", "--suite", "codecs"],
        ["--codecs", "base9000"],
    ],
)
def test_bad_arguments_exit(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        cli.parse_options(argv)


def test_unknown_codec_error_names_the_registry(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.parse_options(["--codecs", "base9000"])
    stderr = capsys.readouterr().err
    assert "base9000" in stderr
    assert "base32768" in stderr  # the fix is spelled out, not left to guessing


def test_output_paths_are_checked_before_measuring(tmp_path: pathlib.Path) -> None:
    """Minutes of measuring must never end in a missing-directory traceback."""
    missing = tmp_path / "absent" / "out.json"
    for argv in (
        ["--json", str(missing)],
        ["--markdown", str(missing)],
        ["--graphs", str(tmp_path / "absent" / "charts")],
        ["--inject", str(tmp_path / "no-such.md")],
    ):
        with pytest.raises(SystemExit):
            cli.parse_options(argv)


def test_inject_target_must_carry_the_markers(tmp_path: pathlib.Path) -> None:
    unmarked = tmp_path / "README.md"
    unmarked.write_text("# hello\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.parse_options(["--inject", str(unmarked)])
    marked = tmp_path / "marked.md"
    marked.write_text(f"{markdown.BEGIN}\nold\n{markdown.END}\n", encoding="utf-8")
    assert cli.parse_options(["--inject", str(marked)]).inject_path == marked


def test_wrapper_shapes_are_distinct_statements() -> None:
    """Four identical statements would measure the same call and prove nothing."""
    statements = [statement for _, statement, _ in wrapper._SHAPES]  # pyright: ignore[reportPrivateUsage]
    assert len(set(statements)) == len(statements)
    assert "m.encode(p)" in statements  # the dotted access lives inside the timed statement


_TINY = cli.RunConfig(
    mode="quick",
    codecs=("braille",),
    sizes=(("1 B", 1),),
    directions=("encode",),
    repeat=1,
    target=0.0001,
    reference_number=10,
)


def _pretend_unoptimized(monkeypatch: pytest.MonkeyPatch) -> None:
    def _capture() -> model.Environment:
        return factories.make_environment(optimized=False)

    monkeypatch.setattr(environment, "capture", _capture)


def test_non_optimized_build_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The founding guard: a debug build must never produce numbers by accident."""
    _pretend_unoptimized(monkeypatch)
    with pytest.raises(SystemExit, match="refusing"):
        cli.run(_TINY)


def test_force_measures_anyway_and_confesses(monkeypatch: pytest.MonkeyPatch) -> None:
    _pretend_unoptimized(monkeypatch)
    result = cli.run(dataclasses.replace(_TINY, force=True))
    assert result.run.forced is True
    assert result.environment.optimized is False
    assert len(result.measurements) == 1


def test_forced_flag_stays_false_on_an_optimized_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """--force on a healthy build is a no-op, not a false confession."""
    monkeypatch.setattr(environment, "capture", factories.make_environment)
    result = cli.run(dataclasses.replace(_TINY, force=True))
    assert result.run.forced is False
    assert result.run.mode == "quick"


def test_wrapper_suite_has_no_guard_side_door(monkeypatch: pytest.MonkeyPatch) -> None:
    """--suite wrapper measures too; the refusal must fire before it does."""
    _pretend_unoptimized(monkeypatch)

    def _must_not_measure(*_args: object) -> typing.Never:
        msg = "wrapper.measure ran despite the guard"
        raise AssertionError(msg)

    monkeypatch.setattr(wrapper, "measure", _must_not_measure)
    with pytest.raises(SystemExit, match="refusing"):
        cli.main(["--suite", "wrapper"])


def _ci_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, *, reference_ns: float, floor: float
) -> tuple[int, str]:
    """Run main(['--ci']) against a canned result and gates file; return (exit, summary)."""
    canned = factories.make_result(
        (
            factories.make_measurement(
                size_label="200 B", size_bytes=200, ns_per_call=110.0, reference_ns_per_call=reference_ns
            ),
        ),
        run=model.RunInfo(mode="ci"),
    )

    def _canned_run(_config: cli.RunConfig | None = None) -> model.RunResult:
        return canned

    monkeypatch.setattr(cli, "run", _canned_run)
    gates_path = tmp_path / "gates.json"
    gates_path.write_text(json.dumps({"ratio_floors": {"base32768": {"encode": floor}}}), encoding="utf-8")
    monkeypatch.setattr(ci, "GATES_PATH", gates_path)
    summary_path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    code = cli.main(["--ci"])
    summary = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    return code, summary


def test_ci_exit_codes_are_the_verdict(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """The workflow's red X hangs on this exit code; pin it end to end."""
    code, summary = _ci_main(monkeypatch, tmp_path, reference_ns=11_000.0, floor=55.0)  # ratio 100x
    assert code == 0
    assert "radixly benchmarks" in summary
    assert "Gate failures" not in summary
    code, summary = _ci_main(monkeypatch, tmp_path, reference_ns=2_200.0, floor=55.0)  # ratio 20x
    assert code == 1
    assert "Gate failures" in summary
    assert "below the floor" in summary
