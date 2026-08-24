from __future__ import annotations

from importlib.machinery import EXTENSION_SUFFIXES

import radixly
import radixly._core


def test_import() -> None:

    assert radixly.__author__ == "rayakame"
    assert radixly.__url__ == "https://github.com/rayakame/radixly"
    assert radixly.__license__ == "MIT"


def test_extension_import() -> None:

    assert radixly._core.__file__.endswith(tuple(EXTENSION_SUFFIXES))
