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

    def __reduce__(self) -> tuple[type[DecodeError], tuple[int], str]:  # pyright: ignore[reportImplicitOverride]
        return (type(self), (self._position,), self._message)

    # State is deliberately narrower than BaseException's dict-or-None: the
    # pickle channel carries only the message. (typing.override needs 3.12;
    # the floor is 3.11, hence the ignores instead.)
    def __setstate__(self, state: str) -> None:  # pyright: ignore[reportImplicitOverride, reportIncompatibleMethodOverride]
        # Two stores where the C has one: _message feeds the property, args
        # feeds str() -- missing either would desynchronize the clone.
        self._message = state
        self.args = (state,)

    @property
    def message(self) -> str:
        return self._message

    @property
    def position(self) -> int:
        return self._position
