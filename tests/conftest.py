"""Shared vector machinery, loaded by pytest for every module in tests/.

The pairs glob lives here, once. Any test function that declares a
``bin_path`` parameter is parametrized over all vector payloads by the
`pytest_generate_tests` hook below; tests that want the whole list instead
(the presence guard) take the ``vector_pairs`` fixture.
"""

from pathlib import Path

import pytest

VECTOR_DIR = Path(__file__).parent / "vectors" / "base32768"
PAIRS: list[Path] = sorted((VECTOR_DIR / "pairs").rglob("*.bin"))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "bin_path" in metafunc.fixturenames:
        metafunc.parametrize("bin_path", PAIRS, ids=lambda path: path.stem)


@pytest.fixture
def vector_dir() -> Path:
    return VECTOR_DIR


@pytest.fixture
def vector_pairs() -> list[Path]:
    return PAIRS
