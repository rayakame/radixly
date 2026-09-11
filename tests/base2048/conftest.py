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
"""base2048 vector machinery, scoped by location to this codec's tests."""

from __future__ import annotations

import pathlib

import pytest

VECTOR_DIR = pathlib.Path(__file__).parent.parent / "vectors" / "base2048"
PAIRS: list[pathlib.Path] = sorted((VECTOR_DIR / "pairs").rglob("*.bin"))


def _path_id(path: pathlib.Path) -> str:
    return path.stem


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "base2048_bin_path" in metafunc.fixturenames:
        metafunc.parametrize("base2048_bin_path", tuple(PAIRS), ids=_path_id)


@pytest.fixture
def vector_dir() -> pathlib.Path:
    return VECTOR_DIR


@pytest.fixture
def vector_pairs() -> tuple[pathlib.Path, ...]:
    return tuple(PAIRS)
