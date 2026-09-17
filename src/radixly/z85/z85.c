/*
 * Copyright (c) 2026-present rayakame
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "z85.h"

#include "base85/base85.h"

const char radixly_z85_encode_doc[] =
    PyDoc_STR("z85_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as Z85 text.\n"
              "\n"
              "ZeroMQ's Z85: base85 with an alphabet that stays clear of quotes,\n"
              "backslashes and the shell's punctuation. Five characters per four\n"
              "bytes; a shorter tail becomes one character more than its bytes, so\n"
              "``n`` bytes become ``5 * (n // 4)`` characters plus ``n % 4 + 1`` when\n"
              "``n`` is not a multiple of four.\n"
              "\n"
              "Parameters\n"
              "----------\n"
              "data\n"
              "    The bytes to encode: anything supporting the buffer protocol.\n"
              "\n"
              "Returns\n"
              "-------\n"
              "str\n"
              "    The encoded text; empty input encodes to the empty string.\n"
              "\n"
              "Raises\n"
              "------\n"
              "TypeError\n"
              "    If ``data`` is a ``str`` or otherwise not bytes-like.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> from radixly import z85\n"
              ">>> z85.encode(b'hello')\n"
              "'xK#0@zV'\n"
              ">>> z85.decode(z85.encode(b'hello'))\n"
              "b'hello'");
PyObject *
radixly_z85_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base85_encode_with(arg, 1);
}

const char radixly_z85_decode_doc[] =
    PyDoc_STR("z85_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode Z85 text back to bytes.\n"
              "\n"
              "Strict: the Z85 alphabet only, groups of five, a tail of two to four\n"
              "characters only in the spelling the encoder produces, no group above\n"
              "32 bits.\n"
              "\n"
              "Parameters\n"
              "----------\n"
              "data\n"
              "    The text to decode.\n"
              "\n"
              "Returns\n"
              "-------\n"
              "bytes\n"
              "    The decoded payload; the empty string decodes to ``b''``.\n"
              "\n"
              "Raises\n"
              "------\n"
              "TypeError\n"
              "    If ``data`` is not a ``str``.\n"
              "DecodeError\n"
              "    On malformed or non-canonical input; ``position`` is the index of\n"
              "    the offending character.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> import radixly\n"
              ">>> try:\n"
              "...     radixly.z85.decode('xK#0@zV~')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "7");
PyObject *
radixly_z85_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base85_decode_with(arg, 1);
}
