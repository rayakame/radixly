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
