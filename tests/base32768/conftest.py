"""base32768 vector machinery, scoped by location to this codec's tests."""

from __future__ import annotations

import pathlib

import pytest

VECTOR_DIR = pathlib.Path(__file__).parent.parent / "vectors" / "base32768"
PAIRS: list[pathlib.Path] = sorted((VECTOR_DIR / "pairs").rglob("*.bin"))


def _path_id(path: pathlib.Path) -> str:
    return path.stem


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "base32768_bin_path" in metafunc.fixturenames:
        metafunc.parametrize("base32768_bin_path", tuple(PAIRS), ids=_path_id)


@pytest.fixture
def vector_dir() -> pathlib.Path:
    return VECTOR_DIR


@pytest.fixture
def vector_pairs() -> tuple[pathlib.Path, ...]:
    return tuple(PAIRS)
