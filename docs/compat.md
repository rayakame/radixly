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
still accepts nonzero pad bits. Even the exception chains match: where the
standard library writes `raise ... from None`, the port hides its own context
too, so tracebacks read the same.

Two gaps are left, and both take code that breaks its own contract to reach.
The port holds the buffer it decodes where the standard library may already
have copied it (`memoryview(s).tobytes()`, or the copy `translate` made), so a
`casefold`, `map01`, `altchars` or `validate` object whose `__bool__` or
`encode` resizes that buffer during the call gets `BufferError`, and a
same-length edit is read. Holding the buffer instead of copying it up front is
what makes the port allocation-free, and refusing a resize is the safe
direction. And an object that claims to be `bytes` without being one, or a
`str` subclass whose `encode` returns anything other than `bytes` or
`bytearray`, is judged by the buffer it offers rather than by the methods the
standard library would call on it (`translate`, `rstrip`, or `binascii`'s own
argument check), so the outcome can differ from the standard library's.

The 85 family keeps the standard library's shortcuts and its accidents alike:
`a85encode` folds four zero bytes to `z` and, on request, four spaces to `y`,
wraps and frames as `btoa` and PostScript do; the decoders pad a short tail
with their largest digit, so a lone trailing character is an overflow error,
as it is in the standard library.

`b64decode` is `binascii.a2b_base64` underneath in the standard library, and
that function's treatment of stray padding changed in CPython 3.12.4 and
again in 3.13.13 and 3.14.4. The port carries all three readings and picks
the one matching the running interpreter at import, so the drop-in agrees
with the `base64` next to it on every patch release.

The strict codecs in the rest of radixly are a different contract, see below.

## What runs in C

The port lands family by family. Functions not yet ported are the standard
library's own, so the module is complete at every step and only gets faster.

| functions | status |
|---|---|
| `b16encode`, `b16decode` | C |
| `b32encode`, `b32decode`, `b32hexencode`, `b32hexdecode` | C |
| `b64encode`, `b64decode`, `standard_b64encode`, `standard_b64decode`, `urlsafe_b64encode`, `urlsafe_b64decode` | C |
| `a85encode`, `a85decode`, `b85encode`, `b85decode`, `z85encode`, `z85decode` (3.13 and later) | C |
| `encode`, `decode`, `encodebytes`, `decodebytes` | standard library |

## Strict codecs versus the drop-in

Every RFC 4648 codec radixly registers ({doc}`codecs/base16`,
{doc}`codecs/base32`, {doc}`codecs/base32hex`, {doc}`codecs/base64`,
{doc}`codecs/base64url`) takes the strict reading of the RFC, and
{doc}`codecs/base85` and {doc}`codecs/z85` the same reading of theirs: characters
outside the alphabet, wrong padding, nonzero pad bits and, for the
single-case alphabets of base16, base32 and base32hex, the other case are
errors, so one payload has exactly one accepted spelling. The RFC requires
rejecting characters outside the alphabet (section 3.3) and permits
rejecting nonzero pad bits (section 3.5); its security considerations
(section 12) explain why a decoder would want all of it, case included. The
drop-in keeps the standard library's choices instead, because that is what
makes it a drop-in. Same C underneath, two contracts on top.
