"""Task runner for reproducible dev invocations."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sysconfig

import nox

nox.options.default_venv_backend = "uv"
nox.options.sessions = ["reformat", "pytest", "pyright", "tidy", "lint"]

PATHS = ["noxfile.py", "benchmarks", "scripts", "src", "tests"]
C_PATHS = sorted(str(p) for p in pathlib.Path("src").rglob("*.[ch]"))


def sync(
    session: nox.Session,
    /,
    *groups: str,
    project: bool = True,
    editable: bool = True,
    build_env: dict[str, str] | None = None,
) -> None:
    """Install dependency groups (and by default the project) into the session venv."""
    # Env CFLAGS displace the distro's optimized flags here (only OPT survives
    # composition) -- proven by _core.OPTIMIZED reading False without the -O3.
    # -O3 matches the distro base, so it cannot downgrade under either
    # replace or append semantics.
    env = {"UV_PROJECT_ENVIRONMENT": session.virtualenv.location, "CFLAGS": "-O3 -Werror"}
    if build_env is not None:
        env |= build_env
    args: list[str]
    if project:
        # --refresh-package busts uv's built-wheel cache: its key ignores env
        # vars, so a CFLAGS change alone would keep serving the stale build.
        args = ["--no-default-groups", "--reinstall-package", "radixly", "--refresh-package", "radixly"]
        # Sessions build with per-session flags, but setuptools reuses .o files
        # from the shared in-tree build/ without checking what flags built them
        # -- an asan session would poison later plain builds and vice versa.
        # The build_base carries a digest of the flags, not just the session
        # name: create_tmp persists across runs, so a flag edit within one
        # session name would otherwise reuse the stale objects too.
        digest = hashlib.sha256(env["CFLAGS"].encode()).hexdigest()[:12]
        session_tmp = pathlib.Path(session.create_tmp())
        dist_cfg = session_tmp / "dist-extra.cfg"
        dist_cfg.write_text(f"[build]\nbuild_base = {session_tmp / f'build-{digest}'}\n", encoding="utf-8")
        env["DIST_EXTRA_CONFIG"] = str(dist_cfg)
        if not editable:
            args.append("--no-editable")
        for group in groups:
            args += ["--group", group]
    else:
        args = []
        for group in groups:
            args += ["--only-group", group]
    session.run_install("uv", "sync", "--locked", *args, env=env)


@nox.session(reuse_venv=True)
def reformat(session: nox.Session) -> None:
    """Rewrite files: apply formatting and safe lint fixes."""
    sync(session, "ruff", "clang", project=False)
    session.run("ruff", "format", *PATHS, *session.posargs)
    session.run(
        "ruff",
        "check",
        *PATHS,
        "--select",
        "I,RUF022,RUF023",
        "--fix",
        *session.posargs,
    )
    if C_PATHS:
        session.run("clang-format", "-i", *C_PATHS)


@nox.session(name="format-check", reuse_venv=True)
def reformat_check(session: nox.Session) -> None:
    # Non-mutating counterpart to `reformat`, for CI.
    sync(session, "ruff", "clang", project=False)
    session.run("ruff", "format", "--check", *PATHS, *session.posargs)
    session.run("ruff", "check", *PATHS, "--select", "I,RUF022,RUF023", *session.posargs)
    if C_PATHS:
        session.run("clang-format", "--dry-run", "-Werror", *C_PATHS)


@nox.session(reuse_venv=True)
def lint(session: nox.Session) -> None:
    """Check-only twin of reformat, for CI: fails instead of rewriting."""
    sync(session, "ruff", "clang", project=False)
    session.run("ruff", "check", *PATHS, *session.posargs)


@nox.session(reuse_venv=True)
def pyright(session: nox.Session) -> None:
    """Type-check with basedpyright (recommended mode; warnings fail)."""
    sync(session, "nox", "pyright", "pytest", "bench")
    session.run("basedpyright", "--pythonpath", str(pathlib.Path(session.virtualenv.bin) / "python"))


def _write_compiledb() -> None:
    """clang-tidy needs compile_commands.json to know how the C is built.

    Machine-specific (absolute include paths), so it is generated on demand
    and gitignored rather than committed.
    """

    include: object = sysconfig.get_config_var("INCLUDEPY")  # pyright: ignore[reportAny]
    assert isinstance(include, str), "INCLUDEPY missing from sysconfig"
    sources = [p for p in C_PATHS if p.endswith(".c")]
    entries = [
        {
            "directory": str(pathlib.Path.cwd()),
            "file": path,
            # -std matches PEP 7's target (C11); analysis-side only until the
            # build pins its own -std.
            # src/radixly mirrors the build's include root so quoted
            # includes resolve identically for the compiler and the tools.
            "arguments": ["cc", "-std=c11", "-I", include, "-I", "src/radixly", "-c", path],
        }
        for path in sources
    ]
    pathlib.Path("compile_commands.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")


@nox.session(reuse_venv=True)
def tidy(session: nox.Session) -> None:
    """Static analysis for the C sources. Enforced in CI; warnings are errors."""
    sync(session, "clang", project=False)
    _write_compiledb()
    sources = [p for p in C_PATHS if p.endswith(".c")]
    if sources:
        session.run("clang-tidy", "-p", ".", *sources)


_SANITIZE = "-fsanitize=address,undefined"


@nox.session(reuse_venv=True)
def asan(session: nox.Session) -> None:
    """Run the suite with the extension built under ASan+UBSan. CI gate; on demand locally."""
    sync(
        session,
        "pytest",
        "bench",
        editable=False,
        build_env={
            "CFLAGS": f"-O3 -Werror {_SANITIZE} -g -fno-omit-frame-pointer",
            "LDFLAGS": _SANITIZE,
        },
    )
    libasan = session.run("cc", "-print-file-name=libasan.so", silent=True, external=True)
    assert isinstance(libasan, str), "cc -print-file-name=libasan.so produced no output"
    asan_env = {
        "LD_PRELOAD": libasan.strip(),
        "PYTHONMALLOC": "malloc",
        "PYTHONUNBUFFERED": "1",
        "ASAN_OPTIONS": "detect_leaks=0",
        "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1",
    }
    # tests/bench stays out of the sanitized process: importing
    # matplotlib.pyplot under a preloaded libasan <= 13 dies in ASan's
    # __cxa_throw interceptor (CHECK failed, asan_interceptors.cpp) when
    # matplotlib's C++ throws during init. Those tests are pure Python,
    # audit none of our C, and run in every plain pytest job.
    session.run("pytest", "--ignore=tests/bench", *session.posargs, env=asan_env)


@nox.session(reuse_venv=True)
def pytest(session: nox.Session) -> None:
    """Build and install the package into a clean venv, then run the suite.

    Extra args pass through: ``nox -s pytest -- -k import``.
    """
    sync(session, "pytest", "bench")
    session.run("pytest", *session.posargs)
