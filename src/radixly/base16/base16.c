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
#include <string.h>
#include "base16.h"

#include "_common/errors.h"
#include "_common/internal.h"

enum {
    TABLE_SIZE = 256,
    NUM_DIGITS = 16,
    FIRST_LETTER = 10,
    ASCII_MAX = 0x7F,
    INVALID = 0xFF,
};

static const unsigned NIBBLE = 4U;
static const unsigned NIBBLE_MASK = 0xFU;
static const char DIGITS[] = "0123456789ABCDEF";

static uint16_t PAIRS[TABLE_SIZE]; /* both digits of a byte, written as one 16-bit store */
static uint8_t REV[2][TABLE_SIZE];

int
radixly_base16_exec(PyObject *Py_UNUSED(module))
{
    for (unsigned byte = 0; byte < TABLE_SIZE; byte++) {
        const unsigned char pair[2] = {
            (unsigned char)DIGITS[byte >> NIBBLE],
            (unsigned char)DIGITS[byte & NIBBLE_MASK],
        };
        memcpy(&PAIRS[byte], pair, sizeof(pair));
    }
    memset(REV, INVALID, sizeof(REV));
    for (unsigned value = 0; value < NUM_DIGITS; value++) {
        REV[RADIXLY_HEX_UPPER][(unsigned char)DIGITS[value]] = (uint8_t)value;
        REV[RADIXLY_HEX_ANY][(unsigned char)DIGITS[value]] = (uint8_t)value;
    }
    for (unsigned value = FIRST_LETTER; value < NUM_DIGITS; value++) {
        REV[RADIXLY_HEX_ANY][(unsigned char)('a' + (value - FIRST_LETTER))] = (uint8_t)value;
    }
    return 0;
}

const uint8_t *
radixly_hex_table(int which)
{
    return REV[which];
}

void
radixly_hex_fill(const unsigned char *data, Py_ssize_t len, unsigned char *out)
{
    const unsigned char *end = data + len;
    for (; data < end; data++, out += 2) {
        memcpy(out, &PAIRS[*data], sizeof(uint16_t));
    }
}

Py_ssize_t
radixly_hex_pairs(const unsigned char *digits, Py_ssize_t len, unsigned char *out, const uint8_t *rev)
{
    const unsigned char *cursor = digits;
    const unsigned char *end = digits + (len - (len % 2));
    for (; cursor < end; cursor += 2, out++) {
        const unsigned high = rev[cursor[0]];
        const unsigned low = rev[cursor[1]];
        if (((high | low) & ~NIBBLE_MASK) != 0) {
            break;
        }
        *out = (unsigned char)((high << NIBBLE) | low);
    }
    return cursor - digits;
}

const char radixly_base16_encode_doc[] =
    PyDoc_STR("base16_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base16 text.\n"
              "\n"
              "Two uppercase hexadecimal digits per byte, RFC 4648 section 8: ``n``\n"
              "bytes become ``2 * n`` characters.\n"
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
              ">>> from radixly import base16\n"
              ">>> base16.encode(b'hi')\n"
              "'6869'\n"
              ">>> base16.decode(base16.encode(b'hi'))\n"
              "b'hi'");
PyObject *
radixly_base16_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len == 0) {
        PyBuffer_Release(&view);
        return PyUnicode_New(0, 0);
    }
    if (view.len > PY_SSIZE_T_MAX / 2) {
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    PyObject *result = PyUnicode_New(2 * view.len, ASCII_MAX);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return NULL;
    }
    radixly_hex_fill(view.buf, view.len, PyUnicode_1BYTE_DATA(result));
    PyBuffer_Release(&view);
    return result;
}

/* A 2- or 4-byte str always holds a character outside ASCII, so the wide path only locates the first invalid
 * one. */
static Py_ssize_t
first_invalid_wide(int kind, const void *data, Py_ssize_t num_chars)
{
    for (Py_ssize_t i = 0; i < num_chars; i++) {
        const Py_UCS4 code_point = PyUnicode_READ(kind, data, i);
        if (code_point > ASCII_MAX || REV[RADIXLY_HEX_UPPER][code_point] == INVALID) {
            return i;
        }
    }
    return -1;
}

/* The index of the first character the strict codec refuses, or -1; an odd length is judged afterwards. */
static Py_ssize_t
first_invalid(const unsigned char *digits, Py_ssize_t num_chars, Py_ssize_t consumed)
{
    const uint8_t *rev = REV[RADIXLY_HEX_UPPER];
    if (consumed < num_chars - (num_chars % 2)) {
        return rev[digits[consumed]] == INVALID ? consumed : consumed + 1;
    }
    if ((num_chars % 2) != 0 && rev[digits[num_chars - 1]] == INVALID) {
        return num_chars - 1;
    }
    return -1;
}

const char radixly_base16_decode_doc[] =
    PyDoc_STR("base16_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base16 text back to bytes.\n"
              "\n"
              "Strict: uppercase digits only, an even number of them, nothing else.\n"
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
              "    On a character outside ``0-9A-F`` (``position`` is its index) or an\n"
              "    odd length (``position`` is the length, where the missing digit\n"
              "    would be).\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> import radixly\n"
              ">>> try:\n"
              "...     radixly.base16.decode('6a')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "1");
PyObject *
radixly_base16_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    if (!PyUnicode_Check(arg)) {
        PyErr_Format(PyExc_TypeError, "expected str, not %.200s", Py_TYPE(arg)->tp_name);
        return NULL;
    }
#if PY_VERSION_HEX < 0x030C0000
    /* 3.11 can still meet legacy, non-ready strings; GET_LENGTH/KIND/DATA on one is UB. Compiles out
     * on 3.12+. */
    if (PyUnicode_READY(arg) == -1) {
        return NULL;
    }
#endif
    const Py_ssize_t num_chars = PyUnicode_GET_LENGTH(arg);
    if (num_chars == 0) {
        return PyBytes_FromStringAndSize("", 0);
    }
    const int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);
    if (kind != PyUnicode_1BYTE_KIND) {
        const Py_ssize_t bad = first_invalid_wide(kind, data, num_chars);
        if (bad == -1) {
            PyErr_SetString(PyExc_SystemError, "a non-ASCII str kind held only ASCII characters");
            return NULL;
        }
        return radixly_raise_decode_error(bad, "invalid base16 character U+%x at index %zd",
                                          (unsigned)PyUnicode_READ(kind, data, bad), bad);
    }
    /* Characters raise left to right at their own index; an odd length raises at the end, where the missing
     * digit would be, so an invalid character earlier in the text wins. */
    const unsigned char *digits = data;
    PyObject *result = PyBytes_FromStringAndSize(NULL, num_chars / 2);
    if (result == NULL) {
        return NULL;
    }
    const Py_ssize_t consumed = radixly_hex_pairs(
        digits, num_chars, (unsigned char *)PyBytes_AS_STRING(result), REV[RADIXLY_HEX_UPPER]);
    const Py_ssize_t bad = first_invalid(digits, num_chars, consumed);
    if (bad != -1) {
        Py_DECREF(result);
        return radixly_raise_decode_error(bad, "invalid base16 character U+%x at index %zd",
                                          (unsigned)digits[bad], bad);
    }
    if ((num_chars % 2) != 0) {
        Py_DECREF(result);
        return radixly_raise_decode_error(
            num_chars, "odd length: %zd characters, the last byte needs two digits", num_chars);
    }
    return result;
}
