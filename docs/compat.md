# Standard library drop-in

`radixly.compat.base64` is the standard library's `base64` module with the
same names, arguments, results and errors, one import away:

```python
from radixly.compat import base64

base64.b32encode(b"hello")           # b'NBSWY3DP', as the stdlib returns it
base64.b32decode("nbswy3dp", True)   # b'hello', casefold and all
```

It is a drop-in in the strict sense: CPython's own `test_base64` suite runs
against it, with the import redirected and the few edits listed in
`tests/compat/README.md`, and the functions are also compared with the
standard library on random input, including the exception type and message
on bad input. The lenient behaviors stay lenient: `b64decode` still discards
characters outside the alphabet unless you pass `validate=True`, `b32decode`
still accepts nonzero pad bits. Two things are not reproduced: the
`__context__` of an exception the standard library raises with `from None`,
which a traceback never shows, and the reading of a `bytearray` that a
`casefold` or `map01` hook resizes mid-call, which the port refuses with
`BufferError`. The strict codecs in the rest of radixly are a different
contract, see below.

## What runs in C

The port lands family by family. Functions not yet ported are the standard
library's own, so the module is complete at every step and only gets faster.

| functions | status |
|---|---|
| `b16encode`, `b16decode` | C |
| `b32encode`, `b32decode`, `b32hexencode`, `b32hexdecode` | C |
| `b64encode`, `b64decode`, `standard_b64encode`, `standard_b64decode`, `urlsafe_b64encode`, `urlsafe_b64decode` | standard library |
| `a85encode`, `a85decode`, `b85encode`, `b85decode`, `z85encode`, `z85decode` (3.13 and later) | standard library |
| `encode`, `decode`, `encodebytes`, `decodebytes` | standard library |

## Strict codecs versus the drop-in

Every RFC 4648 codec radixly registers ({doc}`codecs/base16`,
{doc}`codecs/base32`, {doc}`codecs/base32hex`) takes the strict reading of
the RFC: characters outside the alphabet, lowercase, wrong padding and
nonzero pad bits are errors, so one payload has exactly one accepted
spelling. The RFC requires rejecting characters outside the alphabet
(section 3.3) and permits rejecting nonzero pad bits (section 3.5); its
security considerations (section 12) explain why a decoder would want all of
it, case included. The drop-in keeps the
standard library's choices instead, because that is what makes it a
drop-in. Same C underneath, two contracts on top.
