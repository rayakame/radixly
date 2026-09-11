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
"""Task runner for reproducible dev invocations."""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sysconfig
import tempfile

import nox

nox.options.default_venv_backend = "uv"
nox.options.sessions = ["reformat", "pytest", "pyright", "verifytypes", "tidy", "lint", "docs"]

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
    # Env CFLAGS displace the distro's -O flags; -O3 matches the distro base, so it never downgrades.
    env = {"UV_PROJECT_ENVIRONMENT": session.virtualenv.location, "CFLAGS": "-O3 -Wall -Wextra -Werror"}
    if build_env is not None:
        env |= build_env
    args: list[str]
    if project:
        # --refresh-package: uv's wheel cache ignores env vars, a CFLAGS change alone would serve the stale build.
        args = ["--no-default-groups", "--reinstall-package", "radixly", "--refresh-package", "radixly"]
        # setuptools reuses .o files across flag sets; a flag-digested build_base keeps asan and plain builds apart.
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
    """Check formatting and import order without rewriting: the CI counterpart of reformat."""
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


@nox.session(reuse_venv=True)
def docs(session: nox.Session) -> None:
    """Build the docs; every warning is an error (-W), every missing reference too (-n)."""
    sync(session, "docs")
    session.run(
        "sphinx-build",
        "-W",
        "-n",
        "-E",  # no doctree cache: a stale one can hide an autodoc drop behind a green build
        "--keep-going",
        "-b",
        "html",
        "docs",
        "docs/_build/html",
        *session.posargs,
        # Sphinx >= 8.2 prefers a .pyi next to a compiled module; the C docstrings would vanish.
        env={"SPHINX_AUTODOC_IGNORE_NATIVE_MODULE_TYPE_STUBS": "1"},
    )


@nox.session(name="docs-serve", reuse_venv=True)
def docs_serve(session: nox.Session) -> None:
    """Live-reloading docs at http://127.0.0.1:8000; rebuild the extension for C docstring changes."""
    sync(session, "docs")
    session.run(
        "sphinx-autobuild",
        "docs",
        "docs/_build/html",
        "--open-browser",
        *session.posargs,
        env={"SPHINX_AUTODOC_IGNORE_NATIVE_MODULE_TYPE_STUBS": "1"},
    )


@nox.session(reuse_venv=True)
def verifytypes(session: nox.Session) -> None:
    """PEP 561 gate from the consumer's seat.

    Non-editable install, run outside the repo so extraPaths cannot leak the tree.
    """
    # Fresh build: setuptools' persistent build/lib would still ship a deleted py.typed.
    for stale in pathlib.Path(session.create_tmp()).glob("build-*"):
        shutil.rmtree(stale)
    sync(session, "pyright", editable=False)
    python = str(pathlib.Path(session.virtualenv.bin) / "python")
    session.chdir(tempfile.mkdtemp(prefix="radixly-verifytypes-"))
    session.run("basedpyright", "--pythonpath", python, "--verifytypes", "radixly", "--ignoreexternal")


def _write_compiledb() -> None:
    """Write compile_commands.json for clang-tidy; machine-specific, so generated and gitignored."""
    include: object = sysconfig.get_config_var("INCLUDEPY")  # pyright: ignore[reportAny]
    assert isinstance(include, str), "INCLUDEPY missing from sysconfig"
    sources = [p for p in C_PATHS if p.endswith(".c")]
    entries = [
        {
            "directory": str(pathlib.Path.cwd()),
            "file": path,
            # -std is PEP 7's C11; src/radixly mirrors the build's include root so quoted includes resolve alike.
            "arguments": ["cc", "-std=c11", "-I", include, "-I", "src/radixly", "-c", path],
        }
        for path in sources
    ]
    pathlib.Path("compile_commands.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")


@nox.session(reuse_venv=True)
def tidy(session: nox.Session) -> None:
    """Run clang-tidy over the C sources; CI enforces it with warnings as errors."""
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
            "CFLAGS": f"-O3 -Wall -Wextra -Werror {_SANITIZE} -g -fno-omit-frame-pointer",
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
    # tests/bench stays out: matplotlib.pyplot under a preloaded libasan <= 13 dies in ASan's __cxa_throw interceptor.
    session.run("pytest", "--ignore=tests/bench", *session.posargs, env=asan_env)


@nox.session(reuse_venv=True)
def pytest(session: nox.Session) -> None:
    """Build into a clean venv and run the suite. Extra args pass through: nox -s pytest -- -k import."""
    sync(session, "pytest", "bench")
    session.run("pytest", *session.posargs)
