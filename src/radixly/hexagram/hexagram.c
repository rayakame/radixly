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
#include "hexagram.h"

#include "_common/block.h"

enum {
    HEXAGRAM_START = 0x4DC0,
    HEXAGRAM_BITS_PER_CHAR = 6,
};

const char radixly_hexagram_encode_doc[] =
    PyDoc_STR("hexagram_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as Yijing hexagrams.\n"
              "\n"
              "Six bits per character from U+4DC0..U+4DFF; ``n`` bytes become\n"
              "``ceil(8 * n / 6)`` characters, padding bits set to one.\n"
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
              ">>> from radixly import hexagram\n"
              ">>> len(hexagram.encode(b'hi'))\n"
              "3\n"
              ">>> hexagram.decode(hexagram.encode(b'hi'))\n"
              "b'hi'");
PyObject *
radixly_hexagram_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_block_encode(arg, HEXAGRAM_START, HEXAGRAM_BITS_PER_CHAR);
}

const char radixly_hexagram_decode_doc[] =
    PyDoc_STR("hexagram_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode hexagram symbols back to bytes.\n"
              "\n"
              "Strict and canonical: only U+4DC0..U+4DFF, padding all ones, no\n"
              "payload-free final character.\n"
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
              "    On malformed input; ``position`` is the index of the offending\n"
              "    character.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> import radixly\n"
              ">>> try:\n"
              "...     radixly.hexagram.decode('!')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "0");
PyObject *
radixly_hexagram_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_block_decode(arg, HEXAGRAM_START, HEXAGRAM_BITS_PER_CHAR);
}
