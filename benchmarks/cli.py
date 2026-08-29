"""Argument parsing, the run loop, and renderer dispatch. Default scope: complete."""

from __future__ import annotations

import argparse
import dataclasses
import os
import pathlib
import sys
import typing

from benchmarks import baseline
from benchmarks import ci
from benchmarks import environment
from benchmarks import model
from benchmarks import payloads
from benchmarks import registry
from benchmarks import timing
from benchmarks import wrapper
from benchmarks.render import console
from benchmarks.render import graphs
from benchmarks.render import markdown

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

DIRECTIONS: typing.Final = ("encode", "decode")
REFERENCE_NUMBER: typing.Final = 10_000
QUICK_REPEAT: typing.Final = 3
QUICK_TARGET: typing.Final = 0.05
QUICK_REFERENCE_NUMBER: typing.Final = 2_000


@dataclasses.dataclass(frozen=True, slots=True)
class Options:
    codecs: tuple[str, ...] | None
    sizes: tuple[tuple[str, int], ...] | None
    directions: tuple[str, ...]
    suite: str
    quick: bool
    json_path: pathlib.Path | None
    force: bool
    ci_mode: bool
    markdown_path: pathlib.Path | None
    graphs_dir: pathlib.Path | None
    render_from: pathlib.Path | None
    inject_path: pathlib.Path | None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmarks", description="Run the radixly benchmark suite.")
    parser.add_argument("--codecs", default=None, help="comma-separated codec names (default: every registered codec)")
    parser.add_argument("--sizes", default=None, help="comma-separated payload sizes, e.g. 1B,200B,64KiB,1MiB")
    parser.add_argument("--directions", default=None, help="comma-separated subset of encode,decode")
    parser.add_argument("--suite", choices=("codecs", "wrapper", "all"), default="all", help="what to run")
    parser.add_argument("--quick", action="store_true", help="3 repeats, short targets: a smoke, never a record")
    parser.add_argument("--json", type=pathlib.Path, default=None, help="also write the canonical result JSON here")
    parser.add_argument("--force", action="store_true", help="measure even a non-optimized build")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: quick knobs, codecs suite, ratio gates from ci-gates.json, step summary; exits 1 on breach",
    )
    parser.add_argument(
        "--markdown", type=pathlib.Path, default=None, help="write the marker-wrapped markdown fragment here"
    )
    parser.add_argument("--graphs", type=pathlib.Path, default=None, help="write themed SVG charts into this directory")
    parser.add_argument(
        "--render-from",
        type=pathlib.Path,
        default=None,
        help="render from a committed result JSON instead of measuring",
    )
    parser.add_argument("--inject", type=pathlib.Path, default=None, help="splice the markdown fragment into this file")
    return parser


def _sizes_from(parser: argparse.ArgumentParser, raw: str | None) -> tuple[tuple[str, int], ...] | None:
    if raw is None:
        return None
    try:
        return registry.parse_sizes(raw)
    except ValueError as error:
        parser.error(str(error))


def _directions_from(parser: argparse.ArgumentParser, raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return DIRECTIONS
    chosen = {token.strip() for token in raw.split(",")}
    unknown = chosen - set(DIRECTIONS)
    if unknown:
        parser.error(f"unknown directions: {', '.join(sorted(unknown))}; choose from encode, decode")
    return tuple(d for d in DIRECTIONS if d in chosen)


def _validate(parser: argparse.ArgumentParser, options: Options, *, scoped: bool) -> None:
    if options.json_path is not None and options.suite == "wrapper":
        parser.error("--json captures the codecs suite; --suite wrapper produces no JSON document")
    if options.render_from is not None and (scoped or options.quick or options.force or options.json_path is not None):
        parser.error("--render-from renders an existing document; measurement flags do not apply")
    wants_codec_output = (
        options.markdown_path is not None or options.graphs_dir is not None or options.inject_path is not None
    )
    if wants_codec_output and options.render_from is None and options.suite == "wrapper":
        parser.error("--markdown/--graphs/--inject need codec results; --suite wrapper has none")
    if options.ci_mode and options.render_from is not None:
        parser.error("--ci measures; it cannot gate a --render-from document")


def parse_options(argv: Sequence[str] | None = None) -> Options:
    parser = _build_parser()
    args = parser.parse_args(argv)
    codecs_raw = typing.cast("str | None", args.codecs)
    sizes_raw = typing.cast("str | None", args.sizes)
    directions_raw = typing.cast("str | None", args.directions)
    options = Options(
        codecs=tuple(name.strip() for name in codecs_raw.split(",")) if codecs_raw is not None else None,
        sizes=_sizes_from(parser, sizes_raw),
        directions=_directions_from(parser, directions_raw),
        suite=typing.cast("str", args.suite),
        quick=typing.cast("bool", args.quick),
        json_path=typing.cast("pathlib.Path | None", args.json),
        force=typing.cast("bool", args.force),
        ci_mode=typing.cast("bool", args.ci),
        markdown_path=typing.cast("pathlib.Path | None", args.markdown),
        graphs_dir=typing.cast("pathlib.Path | None", args.graphs),
        render_from=typing.cast("pathlib.Path | None", args.render_from),
        inject_path=typing.cast("pathlib.Path | None", args.inject),
    )
    scoped = codecs_raw is not None or sizes_raw is not None or directions_raw is not None
    _validate(parser, options, scoped=scoped)
    return options


@dataclasses.dataclass(frozen=True, slots=True)
class RunConfig:
    codecs: tuple[str, ...] | None = None
    sizes: tuple[tuple[str, int], ...] | None = None
    directions: tuple[str, ...] = DIRECTIONS
    repeat: int = timing.REPEAT
    target: float = timing.TARGET_SECONDS
    reference_number: int = REFERENCE_NUMBER
    force: bool = False


def _rows(
    impl: registry.Implementation, sizes: tuple[tuple[str, int], ...], config: RunConfig
) -> list[model.Measurement]:
    rows: list[model.Measurement] = []
    for direction in config.directions:
        for label, size in sizes:
            data = payloads.payload(size)
            value = data if direction == "encode" else impl.encode(data)
            rows.append(_one_row(impl, direction, (label, size), value, config))
    return rows


def _one_row(
    impl: registry.Implementation,
    direction: str,
    size_row: tuple[str, int],
    value: bytes | str,
    config: RunConfig,
) -> model.Measurement:
    label, size = size_row
    func = impl.encode if direction == "encode" else impl.decode
    reference = impl.reference_encode if direction == "encode" else impl.reference_decode
    number = timing.calibrate(func, value, config.target)  # pyright: ignore[reportArgumentType]
    ns = timing.seconds_per_call(func, value, number, config.repeat) * 1e9  # pyright: ignore[reportArgumentType]
    reference_ns: float | None = None
    if label == registry.RATIO_SIZE_LABEL and reference is not None:
        reference_ns = (
            timing.seconds_per_call(reference, value, config.reference_number, config.repeat) * 1e9  # pyright: ignore[reportArgumentType]
        )
    return model.Measurement(impl.codec, direction, label, size, ns, number, config.repeat, reference_ns, impl.name)


def run(config: RunConfig | None = None) -> model.RunResult:
    config = RunConfig() if config is None else config
    env = environment.capture()
    if not env.optimized and not config.force:
        msg = (
            "refusing to benchmark a non-optimized build (radixly._core.OPTIMIZED is False); "
            "rebuild with `uv sync --reinstall-package radixly`, or pass --force to measure anyway"
        )
        raise SystemExit(msg)
    chosen_sizes = registry.SIZES if config.sizes is None else config.sizes

    measurements: list[model.Measurement] = []
    for impl in registry.implementations(config.codecs):
        measurements.extend(_rows(impl, chosen_sizes, config))
    return model.RunResult(model.SCHEMA_VERSION, env, tuple(measurements))


def _measured_result(options: Options, repeat: int, target: float, reference_number: int) -> model.RunResult:
    result = run(
        RunConfig(
            codecs=options.codecs,
            sizes=options.sizes,
            directions=options.directions,
            repeat=repeat,
            target=target,
            reference_number=reference_number,
            force=options.force,
        )
    )
    known = baseline.find_baseline(result.environment)
    if known is not None:
        for warning in baseline.floor_warnings(result, known):
            print(f"warning: {warning}", file=sys.stderr)
    return result


def _write_outputs(options: Options, result: model.RunResult) -> None:
    if options.markdown_path is not None or options.inject_path is not None:
        wrapped = markdown.fragment(result)
        if options.markdown_path is not None:
            options.markdown_path.write_text(wrapped, encoding="utf-8")
        if options.inject_path is not None:
            document = options.inject_path.read_text(encoding="utf-8")
            options.inject_path.write_text(markdown.inject(document, wrapped), encoding="utf-8")
    if options.graphs_dir is not None:
        for path in graphs.write_charts(result, options.graphs_dir):
            print(f"wrote {path}", file=sys.stderr)


def _ci_gate(result: model.RunResult) -> int:
    """Gate the run, write the step summary; the exit code is the verdict."""
    summary = markdown.table(result)
    failures = ci.check_gates(result, ci.load_gates())
    if failures:
        summary += "\n**Gate failures:**\n\n" + "\n".join(f"- {failure}" for failure in failures) + "\n"
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with pathlib.Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(f"## radixly benchmarks\n\n{summary}")
    for failure in failures:
        print(f"gate failure: {failure}", file=sys.stderr)
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    options = parse_options(argv)
    quick = options.quick or options.ci_mode
    repeat = QUICK_REPEAT if quick else timing.REPEAT
    target = QUICK_TARGET if quick else timing.TARGET_SECONDS
    reference_number = QUICK_REFERENCE_NUMBER if quick else REFERENCE_NUMBER

    result: model.RunResult | None = None
    exit_code = 0
    if options.render_from is not None:
        result = model.from_json(options.render_from.read_text(encoding="utf-8"))
        print(console.render(result))
    elif options.ci_mode or options.suite in {"codecs", "all"}:
        result = _measured_result(options, repeat, target, reference_number)
        print(console.render(result))
        if options.json_path is not None:
            options.json_path.write_text(model.to_json(result), encoding="utf-8")
        if options.ci_mode:
            exit_code = _ci_gate(result)

    if result is not None:
        _write_outputs(options, result)
    if options.render_from is None and not options.ci_mode and options.suite in {"wrapper", "all"}:
        print(wrapper.render(wrapper.measure(repeat, target)))
    return exit_code
