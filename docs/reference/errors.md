# Errors

Decoding failures raise {class}`~radixly.DecodeError`, a `ValueError` that
carries the position of the offending character. Passing the wrong type,
such as a `str` to `encode`, raises a plain `TypeError`.

```{eval-rst}
.. autoexception:: radixly.DecodeError(position: int, *, message: str | None = None)
   :members: position, message
```
