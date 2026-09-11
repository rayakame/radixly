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
"""The committed lookup headers are what the generator writes, and the generator's alphabets are the oracles'."""

from __future__ import annotations

import importlib.util
import pathlib
import typing

import pytest

from tests.reference import base2048 as base2048_reference
from tests.reference import base32768 as base32768_reference
from tests.reference import base65536 as base65536_reference

if typing.TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = pathlib.Path(__file__).parent.parent
GENERATOR = REPO_ROOT / "scripts" / "py" / "gen_tables.py"


class Generator(typing.Protocol):
    """The parts of scripts/py/gen_tables.py these tests touch."""

    BASE_2048_PAIR_STRINGS: tuple[str, ...]
    BASE_32768_PAIR_STRINGS: tuple[str, ...]
    BASE_65536_PAIR_STRINGS: tuple[str, ...]
    BASE_2048_PATH: pathlib.Path
    BASE_32768_PATH: pathlib.Path
    BASE_65536_PATH: pathlib.Path

    @staticmethod
    def write_base_2048_table(path: pathlib.Path) -> None: ...
    @staticmethod
    def write_base_32768_table(path: pathlib.Path) -> None: ...
    @staticmethod
    def write_base_65536_table(path: pathlib.Path) -> None: ...


def _load_generator() -> Generator:
    """Load the script by path; it is tooling, not a package, and stays off the import path."""
    spec = importlib.util.spec_from_file_location("gen_tables", GENERATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return typing.cast("Generator", typing.cast("object", module))


gen_tables = _load_generator()

_WRITERS: dict[str, tuple[Callable[[pathlib.Path], None], pathlib.Path]] = {
    "base2048": (gen_tables.write_base_2048_table, gen_tables.BASE_2048_PATH),
    "base32768": (gen_tables.write_base_32768_table, gen_tables.BASE_32768_PATH),
    "base65536": (gen_tables.write_base_65536_table, gen_tables.BASE_65536_PATH),
}


@pytest.mark.parametrize("codec", sorted(_WRITERS))
def test_committed_header_matches_the_generator(codec: str, tmp_path: pathlib.Path) -> None:
    """A hand edit to _tables.h, or a generator change nobody re-ran, fails here."""
    write, committed = _WRITERS[codec]
    target = tmp_path / "_tables.h"
    write(target)
    assert target.read_bytes() == committed.read_bytes()


@pytest.mark.parametrize(
    ("generator_strings", "reference_strings"),
    [
        (gen_tables.BASE_2048_PAIR_STRINGS, base2048_reference.PAIR_STRINGS),
        (gen_tables.BASE_32768_PAIR_STRINGS, base32768_reference.PAIR_STRINGS),
        (gen_tables.BASE_65536_PAIR_STRINGS, base65536_reference.PAIR_STRINGS),
    ],
    ids=["base2048", "base32768", "base65536"],
)
def test_generator_alphabets_are_the_oracle_alphabets(
    generator_strings: tuple[str, ...], reference_strings: tuple[str, ...]
) -> None:
    """Two copies of each alphabet exist on purpose (the oracle never imports tooling); they must not drift."""
    assert generator_strings == reference_strings


@pytest.mark.parametrize(
    ("tail", "message"),
    [
        ("06", "3-bit repertoire has 7 code points"),
        ("8?", "repertoires overlap"),  # eight code points from U+0038, the first two also 11-bit
        ("\u1056\u105d", "outside"),
    ],
    ids=["short", "overlap", "out-of-range"],
)
def test_generator_refuses_a_corrupted_repertoire(
    tail: str, message: str, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """The checks must survive -O: a ValueError, never an assert, and no header is written."""
    monkeypatch.setattr(gen_tables, "BASE_2048_PAIR_STRINGS", (gen_tables.BASE_2048_PAIR_STRINGS[0], tail))
    with pytest.raises(ValueError, match=message):
        gen_tables.write_base_2048_table(tmp_path / "_tables.h")
    assert not (tmp_path / "_tables.h").exists()
