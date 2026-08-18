"""Task runner for reproducible dev invocations.

The day-to-day inner loop stays `uv run pytest`. These sessions exist so that
CI and a local machine run byte-identical commands.

Sessions arriving with later milestones: asan/ubsan + fuzz (M5), bench (M8).
"""

from __future__ import annotations

import nox

nox.options.default_venv_backend = "uv"
nox.options.sessions = ["reformat", "pytest"]

PATHS = ["noxfile.py", "src", "tests"]


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
    sync(session, "ruff", project=False)
    session.run("ruff", "format", *PATHS)
    session.run("ruff", "check", "--fix-only", *PATHS)


@nox.session(reuse_venv=True)
def lint(session: nox.Session) -> None:
    """Check-only twin of reformat, for CI: fails instead of rewriting."""
    sync(session, "ruff", project=False)
    session.run("ruff", "format", "--check", *PATHS)
    session.run("ruff", "check", *PATHS)


@nox.session(reuse_venv=True)
def pytest(session: nox.Session) -> None:
    """Build and install the package into a clean venv, then run the suite.

    Extra args pass through: ``nox -s pytest -- -k import``.
    """
    sync(session, "pytest")
    session.run("pytest", *session.posargs)
