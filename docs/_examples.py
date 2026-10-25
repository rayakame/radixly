"""Run the pages' Python examples and hold each ``expression  # result`` comment to what the code returns."""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import io
import pathlib
import re
import tokenize

# A closing fence repeats the opener's backticks, at least as many, and nothing else on its line.
_BLOCK = re.compile(r"^(?P<fence>`{3,})python[ \t]*\n(?P<code>.*?)^(?P=fence)`*[ \t]*$", re.DOTALL | re.MULTILINE)
_UNSET = object()


def _comments(source: str) -> dict[int, str]:
    found: dict[int, str] = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            found[token.start[0]] = token.string.lstrip("#").strip()
    return found


def _expected(comment: str) -> object:
    """The literal a comment states, an exception name ending in Error, or _UNSET for prose."""
    for candidate in (comment, comment.split(": ", 1)[0]):
        try:
            return ast.literal_eval(candidate)
        except (ValueError, SyntaxError):
            continue
    word = comment.split(maxsplit=1)[0].rstrip(":") if comment else ""
    return _Raises(word) if word.endswith("Error") and word.isidentifier() else _UNSET


@dataclasses.dataclass(frozen=True, slots=True)
class _Raises:
    """An exception the comment says the statement raises."""

    name: str


def _run(statement: ast.stmt, where: str, namespace: dict[str, object]) -> object:
    """Execute one statement; an expression's value, or a single name's new value, else _UNSET."""
    if isinstance(statement, ast.Expr):
        return eval(compile(ast.Expression(statement.value), where, "eval"), namespace)  # ruff: ignore[suspicious-eval-usage] -- the docs' own examples
    exec(compile(ast.Module([statement], []), where, "exec"), namespace)  # ruff: ignore[exec-builtin] -- the docs' own examples
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
        return namespace[statement.targets[0].id]
    return _UNSET


def _check_block(source: str, where: str, offset: int, namespace: dict[str, object]) -> list[str]:
    comments = _comments(source)
    failures: list[str] = []
    for statement in ast.parse(source).body:
        line = statement.end_lineno or statement.lineno
        at = f"{where}:{offset + line}"
        expected = _expected(comments[line]) if line in comments else _UNSET
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                value = _run(statement, where, namespace)
        except Exception as error:  # ruff: ignore[blind-except] -- any exception is either the stated one or a failure
            if not (isinstance(expected, _Raises) and type(error).__name__ == expected.name):
                failures.append(f"{at}: raised {type(error).__name__}: {error}")
            continue
        if isinstance(expected, _Raises):
            failures.append(f"{at}: expected {expected.name}, got {value!r}")
        elif expected is not _UNSET and value is not _UNSET and value != expected:
            failures.append(f"{at}: the comment says {expected!r}, the code returns {value!r}")
    return failures


def check(docs: pathlib.Path) -> None:
    """Raise with every example whose stated result is not what it returns."""
    failures: list[str] = []
    for page in sorted(docs.rglob("*.md")):
        if "_build" in page.parts or page.parent.name == "benchmarks":
            continue
        text = page.read_text(encoding="utf-8")
        namespace: dict[str, object] = {}  # a page's blocks build on each other, like a reader's session
        for match in _BLOCK.finditer(text):
            code = match.group("code")
            if "sys.modules" in code:
                continue  # swapping modules would swap them under Sphinx too
            offset = text.count("\n", 0, match.start("code"))
            failures += _check_block(code, str(page.relative_to(docs)), offset, namespace)
    if failures:
        raise RuntimeError("examples disagree with the code:\n" + "\n".join(failures))
