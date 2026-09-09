"""Sphinx configuration: Furo, MyST, autodoc + napoleon (NumPy style), msgspec's shape."""

from __future__ import annotations

import radixly

project = "radixly"
author = radixly.__author__
copyright = radixly.__copyright__  # noqa: A001 -- Sphinx's own config name
release = radixly.__version__
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
]

# The public functions are C builtins: autodoc gets their signature from
# __text_signature__ and their text from the docstring, but no annotations.
# Types live in the NumPy docstring sections, like msgspec; the .pyi stub is
# for type checkers, not for the docs.
autodoc_typehints = "none"
autodoc_member_order = "bysource"
napoleon_numpy_docstring = True
napoleon_google_docstring = False

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

myst_enable_extensions = ["colon_fence", "deflist", "attrs_inline"]
myst_heading_anchors = 3

nitpicky = True
nitpick_ignore = [
    ("py:class", "ReadableBuffer"),  # typeshed alias, no public docs target
    ("py:class", "collections.abc.Callable"),
]

templates_path: list[str] = []
exclude_patterns = ["_build"]

html_theme = "furo"
html_title = "radixly"
html_theme_options = {
    "light_css_variables": {"color-brand-primary": "#1F6F8B", "color-brand-content": "#1F6F8B"},
    "dark_css_variables": {"color-brand-primary": "#5FB3CF", "color-brand-content": "#5FB3CF"},
    "source_repository": radixly.__url__,
    "source_branch": "main",
    "source_directory": "docs/",
}
