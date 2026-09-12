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

The functions radixly has ported run in C; the others are the standard library's own until their port lands.
"""

from __future__ import annotations

import sys
from base64 import a85decode
from base64 import a85encode
from base64 import b64decode
from base64 import b64encode
from base64 import b85decode
from base64 import b85encode
from base64 import decode
from base64 import decodebytes
from base64 import encode
from base64 import encodebytes
from base64 import standard_b64decode
from base64 import standard_b64encode
from base64 import urlsafe_b64decode
from base64 import urlsafe_b64encode

from radixly._core import b16decode
from radixly._core import b16encode
from radixly._core import b32decode
from radixly._core import b32encode
from radixly._core import b32hexdecode
from radixly._core import b32hexencode

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
    # z85 joined the standard library in 3.13; until radixly's own port lands, older interpreters have none.
    from base64 import z85decode  # pyright: ignore[reportUnreachable] -- the checker's floor is 3.11
    from base64 import z85encode

    __all__ += ["z85decode", "z85encode"]
