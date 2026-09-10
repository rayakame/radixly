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
    "sphinx_autodoc_typehints",
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
]

# The public functions are C builtins: autodoc gets their signature from
# __text_signature__ and their text from the docstring, but no annotations.
# sphinx-autodoc-typehints lifts the types from _core.pyi (and from the
# annotations of the Python-level functions) into each parameter list, so
# the stub stays the single source of truth for types.
autodoc_member_order = "bysource"
typehints_document_rtype = True
typehints_use_signature = True
typehints_use_signature_return = True


def typehints_formatter(annotation: object, _config: object = None) -> str | None:
    """``ReadableBuffer`` exists only in typeshed; its public name is the Buffer protocol.

    Called with one argument from the signature hook and two from the
    docstring hook; a required second parameter makes autodoc drop the
    function silently.
    """
    if getattr(annotation, "__forward_arg__", None) == "ReadableBuffer" or annotation == "ReadableBuffer":
        return ":class:`~collections.abc.Buffer`"
    return None


# Signatures show ``Buffer``, not ``collections.abc.Buffer``, while still linking.
python_use_unqualified_type_names = True


# The TYPE_CHECKING import of _typeshed cannot resolve at runtime by design.
suppress_warnings = [
    "sphinx_autodoc_typehints.guarded_import",
    "sphinx_autodoc_typehints.forward_reference",
]
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
html_static_path = ["_static"]
html_logo = "_static/logo-wordmark.svg"
html_favicon = "_static/logo.svg"
html_css_files = ["custom.css"]
html_theme_options = {
    "sidebar_hide_name": True,  # the wordmark carries the name
    "light_css_variables": {"color-brand-primary": "#1F6F8B", "color-brand-content": "#1F6F8B"},
    "dark_css_variables": {"color-brand-primary": "#5FB3CF", "color-brand-content": "#5FB3CF"},
    "source_repository": radixly.__url__,
    "source_branch": "main",
    "source_directory": "docs/",
}
