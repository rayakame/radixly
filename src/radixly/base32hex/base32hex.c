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
#include "base32hex.h"

#include "base32/base32.h"

const char radixly_base32hex_encode_doc[] =
    PyDoc_STR("base32hex_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base32hex text.\n"
              "\n"
              "RFC 4648 section 7: base32 with the alphabet ``0-9A-V``, so unpadded\n"
              "text sorts in byte order. ``n`` bytes become\n"
              "``8 * ceil(n / 5)`` characters.\n"
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
              ">>> from radixly import base32hex\n"
              ">>> base32hex.encode(b'hi')\n"
              "'D1KG===='\n"
              ">>> base32hex.decode(base32hex.encode(b'hi'))\n"
              "b'hi'");
PyObject *
radixly_base32hex_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base32_encode_with(arg, 1);
}

const char radixly_base32hex_decode_doc[] =
    PyDoc_STR("base32hex_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base32hex text back to bytes.\n"
              "\n"
              "Strict RFC 4648: uppercase alphabet only, groups of eight, padding only\n"
              "at the end in the four shapes the encoder produces, pad bits zero.\n"
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
              "    the offending character, or the length when the text stops short of\n"
              "    a full group.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> import radixly\n"
              ">>> try:\n"
              "...     radixly.base32hex.decode('d1kg====')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "0");
PyObject *
radixly_base32hex_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base32_decode_with(arg, 1);
}

const char radixly_b32hexencode_doc[] =
    PyDoc_STR("b32hexencode($module, /, s)\n"
              "--\n"
              "\n"
              "Encode the bytes-like objects using base32hex and return a bytes object.");
PyObject *
radixly_b32hexencode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b32encode_with("b32hexencode", args, nargs, kwnames, 1);
}

const char radixly_b32hexdecode_doc[] =
    PyDoc_STR("b32hexdecode($module, /, s, casefold=False)\n"
              "--\n"
              "\n"
              "Decode the base32hex encoded bytes-like object or ASCII string s.\n"
              "\n"
              "Optional casefold is a flag specifying whether a lowercase alphabet is\n"
              "acceptable as input.  For security purposes, the default is False.\n"
              "\n"
              "The result is returned as a bytes object.  A binascii.Error is raised if\n"
              "the input is incorrectly padded or if there are non-alphabet\n"
              "characters present in the input.");
PyObject *
radixly_b32hexdecode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b32decode_with("b32hexdecode", args, nargs, kwnames, 1);
}
