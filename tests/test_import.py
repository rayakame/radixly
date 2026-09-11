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
"""The tripwire: the compiled extension, not a stray pure-Python file, is what imported."""

from __future__ import annotations

import importlib.machinery

import radixly
import radixly._core


def test_import() -> None:

    assert radixly.__author__ == "rayakame"
    assert radixly.__url__ == "https://github.com/rayakame/radixly"
    assert radixly.__license__ == "MIT"


def test_extension_import() -> None:

    assert radixly._core.__file__.endswith(tuple(importlib.machinery.EXTENSION_SUFFIXES))


def test_extension_build_is_optimized() -> None:
    """The benchmark harness refuses non-optimized builds; keep the signal true."""
    assert radixly._core.OPTIMIZED is True
