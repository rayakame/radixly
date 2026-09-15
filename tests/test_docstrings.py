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
"""The examples in the docstrings are executed, so a stale one fails here instead of shipping."""

from __future__ import annotations

import doctest
import importlib
import sys

import pytest

import radixly

# The C docstrings plus every codec face; a new codec joins the list by being registered.
MODULE_NAMES = ["radixly._core", *(f"radixly.{name}._api" for name in radixly.CODECS)]

# -OO drops every docstring, so there is nothing left to run or to count.
pytestmark = pytest.mark.skipif(sys.flags.optimize >= 2, reason="-OO strips docstrings")


@pytest.mark.parametrize("name", MODULE_NAMES)
def test_docstring_examples_run(name: str) -> None:
    """Nothing else executes them: pytest has no --doctest-modules and Sphinx no doctest builder."""
    assert doctest.testmod(importlib.import_module(name), verbose=False).failed == 0, name


def test_the_examples_are_still_there() -> None:
    """Vanished examples would leave the run above with nothing to do and still pass."""
    counts = {name: doctest.testmod(importlib.import_module(name), verbose=False).attempted for name in MODULE_NAMES}
    assert counts["radixly._core"] >= 59
    # braille's face carries no example yet; every other module must keep its own.
    assert [name for name, count in counts.items() if count == 0] == ["radixly.braille._api"]
