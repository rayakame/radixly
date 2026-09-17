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
#include "base64url.h"

#include "base64/base64.h"

const char radixly_base64url_encode_doc[] =
    PyDoc_STR("base64url_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base64url text.\n"
              "\n"
              "RFC 4648 section 5: base64 with ``-`` and ``_`` in place of ``+`` and\n"
              "``/``, so the text survives URLs and file names. ``n`` bytes become\n"
              "``4 * ceil(n / 3)`` characters, ``=`` padding included.\n"
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
              ">>> from radixly import base64url\n"
              ">>> base64url.encode(b'\\xfb\\xff')\n"
              "'-_8='\n"
              ">>> base64url.decode(base64url.encode(b'hi'))\n"
              "b'hi'");
PyObject *
radixly_base64url_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base64_encode_with(arg, 1);
}

const char radixly_base64url_decode_doc[] =
    PyDoc_STR("base64url_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base64url text back to bytes.\n"
              "\n"
              "Strict RFC 4648: the alphabet ``A-Za-z0-9-_`` only, groups of four,\n"
              "padding only at the end in the two shapes the encoder produces, pad\n"
              "bits zero.\n"
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
              "...     radixly.base64url.decode('+/8=')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "0");
PyObject *
radixly_base64url_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base64_decode_with(arg, 1);
}

const char radixly_urlsafe_b64encode_doc[] =
    PyDoc_STR("urlsafe_b64encode($module, /, s)\n"
              "--\n"
              "\n"
              "Encode bytes using the URL- and filesystem-safe Base64 alphabet.\n"
              "\n"
              "Argument s is a bytes-like object to encode.  The result is returned as a\n"
              "bytes object.  The alphabet uses '-' instead of '+' and '_' instead of\n"
              "'/'.");
PyObject *
radixly_urlsafe_b64encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs,
                          PyObject *kwnames)
{
    return radixly_b64encode_with("urlsafe_b64encode", args, nargs, kwnames, 1, 0);
}

const char radixly_urlsafe_b64decode_doc[] =
    PyDoc_STR("urlsafe_b64decode($module, /, s)\n"
              "--\n"
              "\n"
              "Decode bytes using the URL- and filesystem-safe Base64 alphabet.\n"
              "\n"
              "Argument s is a bytes-like object or ASCII string to decode.  The result\n"
              "is returned as a bytes object.  A binascii.Error is raised if the input\n"
              "is incorrectly padded.  Characters that are not in the URL-safe base-64\n"
              "alphabet, and are not a plus '+' or slash '/', are discarded prior to the\n"
              "padding check.\n"
              "\n"
              "The alphabet uses '-' instead of '+' and '_' instead of '/'.");
PyObject *
radixly_urlsafe_b64decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs,
                          PyObject *kwnames)
{
    return radixly_b64decode_with("urlsafe_b64decode", args, nargs, kwnames, 1, 0);
}
