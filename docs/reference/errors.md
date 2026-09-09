# Errors

Every radixly error roots at `ValueError`. Decoding failures carry the
position of the offending character.

```{eval-rst}
.. autoexception:: radixly.DecodeError(position: int, *, message: str | None = None)
   :members: position, message
```
