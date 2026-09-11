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
#include "_tables.h"
#include "base65536.h"

#include "_common/errors.h"
#include "_common/internal.h"

enum {
    BLOCK_SHIFT = 8,
    MAX_CODE_POINT = 0x10FFFF,
    REV_SIZE = (0x10FFFF >> 8) + 1, /* MAX_CODE_POINT >> BLOCK_SHIFT; literals keep the shift unsigned */
    REV_INVALID = 0xFFFF,
    REV_PAD = 0x0100, /* the 8-bit tail block; no block index reaches it */
    BMP_MAX_CHAR = 0xFFFF,
};

/* Indexed by code point >> 8: the block index, REV_PAD, or REV_INVALID. */
static uint16_t REV[REV_SIZE];
_Static_assert((unsigned)RADIXLY_B65536_PAD_START <= (unsigned)MAX_CODE_POINT,
               "the tail block must index REV");

int
radixly_base65536_exec(PyObject *Py_UNUSED(module))
{
    for (size_t i = 0; i < RADIXLY_ARRAY_SIZE(REV); i++) {
        REV[i] = REV_INVALID;
    }

    /* A corrupt generated header must fail the import, not write past REV. */
    for (size_t i = 0; i < RADIXLY_ARRAY_SIZE(RADIXLY_B65536_BLOCK_START); i++) {
        if (RADIXLY_B65536_BLOCK_START[i] > MAX_CODE_POINT) {
            PyErr_SetString(PyExc_SystemError, "base65536 block start out of range");
            return -1;
        }
        REV[RADIXLY_B65536_BLOCK_START[i] >> (unsigned)BLOCK_SHIFT] = (uint16_t)i;
    }
    REV[(unsigned)RADIXLY_B65536_PAD_START >> (unsigned)BLOCK_SHIFT] = REV_PAD;
    return 0;
}

const char radixly_base65536_encode_doc[] =
    PyDoc_STR("base65536_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base65536 text.\n"
              "\n"
              "Two bytes per character from 256 blocks of 256 code points; a final odd\n"
              "byte becomes one character from a separate block. ``n`` bytes become\n"
              "``ceil(n / 2)`` characters.\n"
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
              ">>> from radixly import base65536\n"
              ">>> len(base65536.encode(b'hi'))\n"
              "1\n"
              ">>> base65536.decode(base65536.encode(b'hi'))\n"
              "b'hi'");
PyObject *
radixly_base65536_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len == 0) {
        PyBuffer_Release(&view);
        return PyUnicode_New(0, 0);
    }
    const unsigned char *data = view.buf;
    const Py_ssize_t n_pairs = view.len / 2;
    const Py_ssize_t odd = view.len % 2;
    const Py_ssize_t n_chars = n_pairs + odd;

    /* The string's kind must be known up front: any second byte from FIRST_ASTRAL_BLOCK on leaves the BMP. */
    int astral = 0;
    for (Py_ssize_t i = 0; i < n_pairs; i++) {
        if (data[(2 * i) + 1] >= RADIXLY_B65536_FIRST_ASTRAL_BLOCK) {
            astral = 1;
            break;
        }
    }

    PyObject *result = PyUnicode_New(n_chars, astral ? MAX_CODE_POINT : BMP_MAX_CHAR);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return result;
    }

    if (astral) {
        Py_UCS4 *out = PyUnicode_4BYTE_DATA(result);
        for (Py_ssize_t i = 0; i < n_pairs; i++) {
            out[i] = RADIXLY_B65536_BLOCK_START[data[(2 * i) + 1]] + data[2 * i];
        }
        if (odd) {
            out[n_pairs] = RADIXLY_B65536_PAD_START + data[view.len - 1];
        }
    }
    else {
        Py_UCS2 *out = PyUnicode_2BYTE_DATA(result);
        for (Py_ssize_t i = 0; i < n_pairs; i++) {
            out[i] = (Py_UCS2)(RADIXLY_B65536_BLOCK_START[data[(2 * i) + 1]] + data[2 * i]);
        }
        if (odd) {
            out[n_pairs] = (Py_UCS2)(RADIXLY_B65536_PAD_START + data[view.len - 1]);
        }
    }
    PyBuffer_Release(&view);
    return result;
}

const char radixly_base65536_decode_doc[] =
    PyDoc_STR("base65536_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base65536 text back to bytes.\n"
              "\n"
              "Strict: every character must come from the alphabet, and the one-byte\n"
              "block may only end the text.\n"
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
              "    On an invalid character or a one-byte character before the end;\n"
              "    ``position`` is the index of the offending character.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> import radixly\n"
              ">>> try:\n"
              "...     radixly.base65536.decode('A')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "0");
PyObject *
radixly_base65536_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    if (!PyUnicode_Check(arg)) {
        PyErr_Format(PyExc_TypeError, "expected str, not %.200s", Py_TYPE(arg)->tp_name);
        return NULL;
    }
#if PY_VERSION_HEX < 0x030C0000
    /* 3.11 can still meet legacy, non-ready strings from other C extensions;
     * GET_LENGTH/KIND/DATA on one is UB. Deprecated call, compiles out on
     * 3.12+; a 3.11 -Werror build may need a suppression. */
    if (PyUnicode_READY(arg) == -1) {
        return NULL;
    }
#endif
    const Py_ssize_t num_chars = PyUnicode_GET_LENGTH(arg);
    if (num_chars == 0) {
        return PyBytes_FromStringAndSize("", 0);
    }
    if (num_chars > PY_SSIZE_T_MAX / 2) {
        return PyErr_NoMemory();
    }
    int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);

    /* Two bytes per character, one for a final tail character: allocate the bound, shrink once at the end. */
    PyObject *result = PyBytes_FromStringAndSize(NULL, 2 * num_chars);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);

    /* Everything before the final character must be a pair, so the hot loop carries no tail branch. */
    const Py_ssize_t last = num_chars - 1;
    for (Py_ssize_t i = 0; i < last; i++) {
        const Py_UCS4 code_point = PyUnicode_READ(kind, data, i);
        if (code_point > MAX_CODE_POINT) {
            Py_DECREF(result);
            return radixly_raise_decode_error(i, "invalid base65536 character U+%x at index %zd",
                                              (unsigned)code_point, i);
        }
        const uint16_t entry = REV[code_point >> (unsigned)BLOCK_SHIFT];
        if (entry == REV_INVALID) {
            Py_DECREF(result);
            return radixly_raise_decode_error(i, "invalid base65536 character U+%x at index %zd",
                                              (unsigned)code_point, i);
        }
        if (entry == REV_PAD) {
            Py_DECREF(result);
            return radixly_raise_decode_error(i, "8-bit character U+%x at index %zd, only valid at index %zd",
                                              (unsigned)code_point, i, last);
        }
        out[2 * i] = (unsigned char)(code_point & BYTE_MASK);
        out[(2 * i) + 1] = (unsigned char)entry;
    }

    const Py_UCS4 code_point = PyUnicode_READ(kind, data, last);
    if (code_point > MAX_CODE_POINT) {
        Py_DECREF(result);
        return radixly_raise_decode_error(last, "invalid base65536 character U+%x at index %zd",
                                          (unsigned)code_point, last);
    }
    const uint16_t entry = REV[code_point >> (unsigned)BLOCK_SHIFT];
    if (entry == REV_INVALID) {
        Py_DECREF(result);
        return radixly_raise_decode_error(last, "invalid base65536 character U+%x at index %zd",
                                          (unsigned)code_point, last);
    }
    out[2 * last] = (unsigned char)(code_point & BYTE_MASK);
    if (entry == REV_PAD) {
        if (_PyBytes_Resize(&result, (2 * num_chars) - 1) < 0) {
            return NULL; /* result already cleared and the exception set */
        }
        return result;
    }
    out[(2 * last) + 1] = (unsigned char)entry;
    return result;
}
