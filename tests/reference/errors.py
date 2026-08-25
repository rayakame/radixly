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

    @property
    def message(self) -> str:
        return self._message

    @property
    def position(self) -> int:
        return self._position
