"""Task runner for reproducible dev invocations.

The day-to-day inner loop stays `uv run pytest`. These sessions exist so that
CI and a local machine run byte-identical commands.

Sessions arriving with later milestones: asan/ubsan + fuzz (M5), bench (M8).
"""

from __future__ import annotations

from pathlib import Path

import nox

nox.options.default_venv_backend = "uv"
nox.options.sessions = ["reformat", "pytest", "tidy"]

PATHS = ["noxfile.py", "scripts", "src", "tests"]
C_PATHS = sorted(str(p) for p in Path("src").rglob("*.[ch]"))


def sync(session: nox.Session, /, *groups: str, project: bool = True) -> None:
    """Install dependency groups (and by default the project) into the session venv.

    ``project=False`` skips building/installing radixly itself, for sessions
    that only need a tool — no point compiling a C extension to run a linter.
    """
    if project:
        args = ["--no-default-groups"]
        for group in groups:
            args += ["--group", group]
    else:
        args = []
        for group in groups:
            args += ["--only-group", group]
    session.run_install(
        "uv",
        "sync",
        "--locked",
        *args,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session(reuse_venv=True)
def reformat(session: nox.Session) -> None:
    """Rewrite files: apply formatting and safe lint fixes."""
    sync(session, "ruff", "clang", project=False)
    session.run("ruff", "format", *PATHS)
    session.run("ruff", "check", "--fix-only", *PATHS)
    if C_PATHS:
        session.run("clang-format", "-i", *C_PATHS)


@nox.session(reuse_venv=True)
def lint(session: nox.Session) -> None:
    """Check-only twin of reformat, for CI: fails instead of rewriting."""
    sync(session, "ruff", "clang", project=False)
    session.run("ruff", "format", "--check", *PATHS)
    session.run("ruff", "check", *PATHS)
    if C_PATHS:
        session.run("clang-format", "--dry-run", "-Werror", *C_PATHS)


def _write_compiledb() -> None:
    """clang-tidy needs compile_commands.json to know how the C is built.

    Machine-specific (absolute include paths), so it is generated on demand
    and gitignored rather than committed.
    """
    import json
    import sysconfig

    include = sysconfig.get_config_var("INCLUDEPY")
    sources = [p for p in C_PATHS if p.endswith(".c")]
    entries = [
        {
            "directory": str(Path.cwd()),
            "file": path,
            # -std matches PEP 7's target (C11); analysis-side only until the
            # build pins its own -std with the M5 hardening flags.
            "arguments": ["cc", "-std=c11", "-I", include, "-c", path],
        }
        for path in sources
    ]
    Path("compile_commands.json").write_text(json.dumps(entries, indent=2))


@nox.session(reuse_venv=True)
def tidy(session: nox.Session) -> None:
    """Static analysis for the C sources. Enforced in CI; warnings are errors."""
    sync(session, "clang", project=False)
    _write_compiledb()
    sources = [p for p in C_PATHS if p.endswith(".c")]
    if sources:
        session.run("clang-tidy", "-p", ".", *sources)


@nox.session(reuse_venv=True)
def pytest(session: nox.Session) -> None:
    """Build and install the package into a clean venv, then run the suite.

    Extra args pass through: ``nox -s pytest -- -k import``.
    """
    sync(session, "pytest")
    session.run("pytest", *session.posargs)
