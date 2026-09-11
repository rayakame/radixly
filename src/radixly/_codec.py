# Copyright (c) 2026-present rayakame
"""The Codec value type and the name registry shared by every codec."""

from __future__ import annotations

import dataclasses
import types
import typing

if typing.TYPE_CHECKING:
    import collections.abc

    from _typeshed import ReadableBuffer

__all__ = ("CODECS", "Codec", "get_codec", "register")


@dataclasses.dataclass(frozen=True, slots=True)
class Codec:
    """One codec as a value: its C functions bound as instance attributes, plus its numbers.

    ``encode``, ``decode``, ``encoded_len`` and ``max_bytes`` are the codec
    module's own functions bound as attributes. Calling ``codec.encode(data)``
    is one attribute load and the C call, never a Python frame.

    Attributes
    ----------
    name
        The registry key, e.g. ``"base32768"``.
    bits_per_char
        Payload bits carried by one output character.
    """

    name: str
    bits_per_char: int
    encode: collections.abc.Callable[[ReadableBuffer], str]
    decode: collections.abc.Callable[[str], bytes]
    encoded_len: collections.abc.Callable[[int], int]
    max_bytes: collections.abc.Callable[[int], int]


_registry: dict[str, Codec] = {}
CODECS = types.MappingProxyType(_registry)


def register(codec: Codec) -> None:
    """Add ``codec`` to the registry under its name; a taken name is refused, never overwritten.

    Parameters
    ----------
    codec
        The codec to register.

    Raises
    ------
    ValueError
        If ``codec.name`` is already registered.
    """
    if codec.name in _registry:
        msg = f"codec {codec.name!r} is already registered"
        raise ValueError(msg)

    _registry[codec.name] = codec


def get_codec(name: str) -> Codec:
    """Look up a registered codec by name; ``CODECS`` is the mapping view of the same registry.

    Parameters
    ----------
    name
        The registry key.

    Returns
    -------
    Codec
        The registered codec.

    Raises
    ------
    KeyError
        If no codec is registered under ``name``; the message lists the registered names.

    Examples
    --------
    >>> import radixly
    >>> radixly.get_codec("uro14").bits_per_char
    14
    """
    codec = _registry.get(name)
    if codec is None:
        msg = f"unknown codec {name!r}; registered: {', '.join(sorted(_registry))}"
        raise KeyError(msg)
    return codec
