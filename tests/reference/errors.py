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
"""The reference DecodeError: the message and pickle contract the C type must match."""

from __future__ import annotations

import typing

__all__ = ("DecodeError",)


@typing.final
class DecodeError(ValueError):
    __slots__ = ("_message", "_position")

    def __init__(self, position: int, *, message: str | None = None) -> None:
        self._position = position
        if message is not None:
            self._message = message
        else:
            self._message = f"Decode Error at position {position}"
        super().__init__(self._message)

    def __reduce__(self) -> tuple[type[DecodeError], tuple[int], tuple[object, object]]:  # pyright: ignore[reportImplicitOverride]
        # args and __dict__ both travel, so add_note and user attributes survive pickle and copy.
        return (type(self), (self._position,), (self.args, self.__dict__))

    # State is a pair where BaseException has a plain dict; typing.override needs 3.12, hence the ignores.
    def __setstate__(self, state: object) -> None:  # pyright: ignore[reportImplicitOverride]
        if isinstance(state, str):  # pickles written before the state carried args and __dict__
            self._message = state
            self.args = (state,)
            return
        name = type(state).__name__
        pair = typing.cast("tuple[object, ...] | None", state if isinstance(state, tuple) else None)
        if pair is None or len(pair) != 2:
            msg = f"DecodeError.__setstate__() state must be str or a 2-tuple, not {name}"
            raise TypeError(msg)
        args, namespace = pair
        if args is not None and not isinstance(args, tuple):
            msg = "DecodeError.__setstate__() args must be a tuple"
            raise TypeError(msg)
        if namespace is not None and not isinstance(namespace, dict):
            msg = "DecodeError.__setstate__() the instance dict must be a dict"
            raise TypeError(msg)
        if args is not None:
            # Two stores where the C has one: _message feeds the property, args feeds str().
            values = typing.cast("tuple[object, ...]", args)
            self.args = values
            self._message = str(values[0]) if values else self._message
        if namespace is not None:
            self.__dict__.update(typing.cast("dict[str, object]", namespace))

    @property
    def message(self) -> str:
        return self._message

    @property
    def position(self) -> int:
        return self._position
