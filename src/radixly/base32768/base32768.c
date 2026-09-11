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
#include "base32768.h"

#include "_common/errors.h"
#include "_common/internal.h"

enum {
    BITS_PER_CHAR = 15,
    MAX_CHAR = 0xFFFF,
    REV_INVALID = MAX_CHAR,
    CEIL_PAD = BITS_PER_CHAR - 1,
};

static const uint16_t REV_7BIT_FLAG = 0x8000;
static const uint32_t REV_VALUE_MASK = 0x7FFF;

static uint16_t REV[MAX_CHAR + 1];

int
radixly_base32768_exec(PyObject *Py_UNUSED(module))
{
    for (size_t i = 0; i < RADIXLY_ARRAY_SIZE(REV); i++) {
        REV[i] = REV_INVALID;
    }

    for (size_t i = 0; i < RADIXLY_ARRAY_SIZE(RADIXLY_B32768_FWD15); i++) {
        REV[RADIXLY_B32768_FWD15[i]] = (uint16_t)i;
    }

    for (size_t i = 0; i < RADIXLY_ARRAY_SIZE(RADIXLY_B32768_FWD7); i++) {
        REV[RADIXLY_B32768_FWD7[i]] = (uint16_t)(REV_7BIT_FLAG | i);
    }
    return 0;
}

const char radixly_base32768_encode_doc[] =
    PyDoc_STR("base32768_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base32768 text.\n"
              "\n"
              "15 payload bits per character; a leftover of 1 to 7 bits ends in a short\n"
              "character from a second alphabet of 128, 8 to 14 in a padded 15-bit one.\n"
              "``n`` bytes become ``ceil(8 * n / 15)`` characters.\n"
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
              ">>> from radixly import base32768\n"
              ">>> len(base32768.encode(b'hi'))\n"
              "2\n"
              ">>> base32768.decode(base32768.encode(b'hi'))\n"
              "b'hi'");
PyObject *
radixly_base32768_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len == 0) {
        PyBuffer_Release(&view);
        return PyUnicode_New(0, 0);
    }
    if (view.len > (PY_SSIZE_T_MAX - CEIL_PAD) / BITS_PER_BYTE) {
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    const Py_ssize_t n_chars = ((BITS_PER_BYTE * view.len) + CEIL_PAD) / BITS_PER_CHAR;

    PyObject *result = PyUnicode_New(n_chars, MAX_CHAR);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return result;
    }
    Py_UCS2 *out = PyUnicode_2BYTE_DATA(result);

    const unsigned char *data = view.buf;
    uint32_t acc = 0;
    unsigned num_bits = 0;
    Py_ssize_t out_i = 0;
    for (Py_ssize_t i = 0; i < view.len; i++) {
        acc = (acc << (unsigned)BITS_PER_BYTE) | data[i];
        num_bits += BITS_PER_BYTE;

        while (num_bits >= BITS_PER_CHAR) {
            num_bits -= BITS_PER_CHAR;
            out[out_i] = RADIXLY_B32768_FWD15[acc >> num_bits];
            out_i++;
            acc &= (1U << num_bits) - 1;
        }
    }

    if (num_bits > 0) {
        unsigned width;
        const uint16_t *table;
        if (num_bits <= (BITS_PER_CHAR - BITS_PER_BYTE)) {
            width = BITS_PER_CHAR - BITS_PER_BYTE;
            table = RADIXLY_B32768_FWD7;
        }
        else {
            width = BITS_PER_CHAR;
            table = RADIXLY_B32768_FWD15;
        }

        const unsigned gap = width - num_bits;
        acc = (acc << gap) | ((1U << gap) - 1);
        out[out_i] = table[acc];
        out_i++;
    }
    assert(out_i == n_chars);
    PyBuffer_Release(&view);
    return result;
}

const char radixly_base32768_decode_doc[] =
    PyDoc_STR("base32768_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base32768 text back to bytes.\n"
              "\n"
              "Strict and canonical: one payload, one accepted spelling.\n"
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
              "...     radixly.base32768.decode('A')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "0");
PyObject *
radixly_base32768_decode(PyObject *Py_UNUSED(self), PyObject *arg)
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
    if (num_chars > PY_SSIZE_T_MAX / BITS_PER_CHAR) {
        return PyErr_NoMemory();
    }
    int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);

    /* Single pass, validate-while-filling. Every character but the last
     * carries 15 bits and the last carries 7 or 15, so floor(15n/8)
     * overshoots the true output length by at most one byte -- allocate
     * the bound up front and shrink at the end instead of scanning twice.
     * Error precedence is unchanged: characters raise left to right the
     * moment they are read; canonicality and padding still lose the
     * position race to any invalid character because they are only
     * checked once every character has been. */
    const Py_ssize_t max_bytes = (BITS_PER_CHAR * num_chars) / BITS_PER_BYTE;
    PyObject *result = PyBytes_FromStringAndSize(NULL, max_bytes);
    if (result == NULL) {
        return NULL;
    }
    char *out = PyBytes_AS_STRING(result);

    uint32_t acc = 0;
    unsigned bits = 0;
    Py_ssize_t out_i = 0;

    /* Everything before the final character must be 15-bit, so the hot
     * loop shifts by a constant and carries no width or last-index branch. */
    for (Py_ssize_t i = 0; i < num_chars - 1; i++) {
        const Py_UCS4 code_point = PyUnicode_READ(kind, data, i);
        if (code_point > MAX_CHAR) {
            Py_DECREF(result);
            return radixly_raise_decode_error(i, "invalid base32768 character U+%x at index %zd",
                                              (unsigned)code_point, i);
        }
        const uint16_t rev_entry = REV[code_point];
        if (rev_entry == REV_INVALID) {
            Py_DECREF(result);
            return radixly_raise_decode_error(i, "invalid base32768 character U+%x at index %zd",
                                              (unsigned)code_point, i);
        }
        if (rev_entry & REV_7BIT_FLAG) {
            Py_DECREF(result);
            return radixly_raise_decode_error(i, "7-bit character U+%x at index %zd, only valid at index %zd",
                                              (unsigned)code_point, i, num_chars - 1);
        }
        acc = (acc << (unsigned)BITS_PER_CHAR) | rev_entry;
        bits += BITS_PER_CHAR;
        while (bits >= BITS_PER_BYTE) {
            bits -= BITS_PER_BYTE;
            out[out_i] = (char)((acc >> bits) & BYTE_MASK);
            out_i++;
            acc &= (1U << bits) - 1U;
        }
    }

    const Py_ssize_t last = num_chars - 1;
    const Py_UCS4 code_point = PyUnicode_READ(kind, data, last);
    if (code_point > MAX_CHAR) {
        Py_DECREF(result);
        return radixly_raise_decode_error(last, "invalid base32768 character U+%x at index %zd",
                                          (unsigned)code_point, last);
    }
    const uint16_t rev_entry = REV[code_point];
    if (rev_entry == REV_INVALID) {
        Py_DECREF(result);
        return radixly_raise_decode_error(last, "invalid base32768 character U+%x at index %zd",
                                          (unsigned)code_point, last);
    }
    const unsigned final_width = (rev_entry & REV_7BIT_FLAG) ? 7 : 15;
    acc = (acc << final_width) | (rev_entry & REV_VALUE_MASK);
    bits += final_width;
    while (bits >= BITS_PER_BYTE) {
        bits -= BITS_PER_BYTE;
        out[out_i] = (char)((acc >> bits) & BYTE_MASK);
        out_i++;
        acc &= (1U << bits) - 1U;
    }

    const unsigned num_pad = bits;
    /* Canonicality: the final character must carry at least one payload bit.
     * A 7-bit final character with 7 padding bits is pure filler, which the
     * encoder never emits (it stops instead of emitting an empty character).
     * Stated width-independently: reject when the final character is no wider
     * than the padding it would have to hold.
     *
     * NOTE: this deliberately diverges from qntm's reference JS, which accepts
     * such a string. radixly rejects it so that decode is injective: one
     * payload, exactly one accepted spelling. Mirrors the same check in
     * tests/reference/base32768.py — keep the two in lockstep. */
    if (final_width <= num_pad) {
        Py_DECREF(result);
        return radixly_raise_decode_error(
            last, "non-canonical input: %u-bit final character at index %zd carries no payload bits",
            final_width, last);
    }
    /* The drain loop masks acc after every byte, so acc holds exactly num_pad
     * bits here. Comparing all of acc — no mask — makes stray high bits
     * (payload that never reached the output) fail this check instead of
     * being silently stripped. */
    if (acc != (1U << num_pad) - 1U) {
        Py_DECREF(result);
        return radixly_raise_decode_error(
            last, "expected %u padding bits set to 1 in final character at index %zd", num_pad, last);
    }
    if (out_i != max_bytes) {
        assert(max_bytes - out_i == 1);
        if (_PyBytes_Resize(&result, out_i) < 0) {
            return NULL; /* result already cleared and the exception set */
        }
    }
    return result;
}
