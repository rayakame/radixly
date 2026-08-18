from importlib.machinery import EXTENSION_SUFFIXES


def test_import() -> None:
    import radixly

    assert radixly.__author__ == "rayakame"
    assert radixly.__url__ == "https://github.com/rayakame/radixly"
    assert radixly.__license__ == "MIT"


def test_extension_import() -> None:
    import radixly._core

    assert radixly._core.__file__.endswith(tuple(EXTENSION_SUFFIXES))
