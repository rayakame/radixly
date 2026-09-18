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
"""A drop-in for the standard library's ``base64``: the same names, arguments, results and errors.

Every function runs in C. The surface is ``base64.__all__``; undocumented module attributes such as
``MAXLINESIZE`` are not carried over.
Two gaps are left, and both take code that breaks its own contract to reach. The port holds the buffer it
decodes where the standard library may already have copied it, so a ``casefold``, ``map01``, ``altchars`` or
``validate`` hook that resizes that buffer during the call gets ``BufferError``, and a same-length edit is read.
And an object that claims to be ``bytes`` without being one, or a ``str`` subclass whose ``encode`` returns
anything other than ``bytes`` or ``bytearray``, is judged by the buffer it offers rather than by the methods the
standard library would call on it, so the outcome can differ from the standard library's. The same holds for a
flag or a width that is not the plain ``bool`` or ``int`` it is meant to be: ``foldspaces`` is read once where
the standard library reads it again per group, ``adobe`` once where it reads it two to four times, and
``wrapcol`` is converted once where the standard library threads the object through ``max``, ``range`` and the
slice.
"""

from __future__ import annotations

import sys

from radixly._core import a85decode
from radixly._core import a85encode
from radixly._core import b16decode
from radixly._core import b16encode
from radixly._core import b32decode
from radixly._core import b32encode
from radixly._core import b32hexdecode
from radixly._core import b32hexencode
from radixly._core import b64decode
from radixly._core import b64encode
from radixly._core import b85decode
from radixly._core import b85encode
from radixly._core import decode
from radixly._core import decodebytes
from radixly._core import encode
from radixly._core import encodebytes
from radixly._core import standard_b64decode
from radixly._core import standard_b64encode
from radixly._core import urlsafe_b64decode
from radixly._core import urlsafe_b64encode

__all__ = [
    "a85decode",
    "a85encode",
    "b16decode",
    "b16encode",
    "b32decode",
    "b32encode",
    "b32hexdecode",
    "b32hexencode",
    "b64decode",
    "b64encode",
    "b85decode",
    "b85encode",
    "decode",
    "decodebytes",
    "encode",
    "encodebytes",
    "standard_b64decode",
    "standard_b64encode",
    "urlsafe_b64decode",
    "urlsafe_b64encode",
]

if sys.version_info >= (3, 13):
    # z85 joined the standard library in 3.13, below the checker's 3.11 floor, so it reads as unreachable.
    from radixly._core import z85decode  # pyright: ignore[reportUnreachable]
    from radixly._core import z85encode

    __all__ += ["z85decode", "z85encode"]
