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
#include "base16.h"

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/errors.h"

enum {
    REV_INVALID = 0xFF,
    TABLE_SIZE = 256,
    NUM_DIGITS = 16,
    FIRST_LETTER = 10,
    ASCII_MAX = 0x7F,
};

static const unsigned NIBBLE_SHIFT = 4U;
static const unsigned NIBBLE_MASK = 0xFU;

static const char DIGITS[] = "0123456789ABCDEF";

static uint8_t REV_STRICT[TABLE_SIZE]; /* 0-9 and A-F */
static uint8_t REV_FOLD[TABLE_SIZE];   /* the compat casefold: a-f as well */

int
radixly_base16_exec(PyObject *Py_UNUSED(module))
{
    for (unsigned code = 0; code < TABLE_SIZE; code++) {
        REV_STRICT[code] = REV_INVALID;
        REV_FOLD[code] = REV_INVALID;
    }
    for (unsigned value = 0; value < NUM_DIGITS; value++) {
        REV_STRICT[(unsigned char)DIGITS[value]] = (uint8_t)value;
        REV_FOLD[(unsigned char)DIGITS[value]] = (uint8_t)value;
    }
    for (unsigned value = FIRST_LETTER; value < NUM_DIGITS; value++) {
        REV_FOLD[(unsigned char)('a' + value - FIRST_LETTER)] = (uint8_t)value;
    }
    return 0;
}

static void
fill(const unsigned char *source, Py_ssize_t num_bytes, unsigned char *out)
{
    for (Py_ssize_t i = 0; i < num_bytes; i++) {
        out[2 * i] = (unsigned char)DIGITS[source[i] >> NIBBLE_SHIFT];
        out[(2 * i) + 1] = (unsigned char)DIGITS[source[i] & NIBBLE_MASK];
    }
}

/* Decode num_digits digits (an even count) into out; returns the index of the first non-digit, or -1. */
static Py_ssize_t
unfill(const unsigned char *source, Py_ssize_t num_digits, unsigned char *out, const uint8_t *rev)
{
    for (Py_ssize_t i = 0; i < num_digits; i += 2) {
        const unsigned high = rev[source[i]];
        const unsigned low = rev[source[i + 1]];
        if (high == REV_INVALID) {
            return i;
        }
        if (low == REV_INVALID) {
            return i + 1;
        }
        out[i / 2] = (unsigned char)((high << NIBBLE_SHIFT) | low);
    }
    return -1;
}

/* A 2- or 4-byte str always holds a character outside ASCII, so the wide path only locates the first
 * invalid one. */
static Py_ssize_t
first_invalid_wide(int kind, const void *data, Py_ssize_t num_chars)
{
    for (Py_ssize_t i = 0; i < num_chars; i++) {
        const Py_UCS4 code_point = PyUnicode_READ(kind, data, i);
        if (code_point > ASCII_MAX || REV_STRICT[code_point] == REV_INVALID) {
            return i;
        }
    }
    return -1;
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
    fill(view.buf, view.len, PyUnicode_1BYTE_DATA(result));
    PyBuffer_Release(&view);
    return result;
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
    const int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);

    /* Characters raise left to right at their own index; an odd length raises at the end, where the missing
     * digit would be, so an invalid character earlier in the text wins. */
    PyObject *result = PyBytes_FromStringAndSize(NULL, num_chars / 2);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    Py_ssize_t bad;
    if (kind == PyUnicode_1BYTE_KIND) {
        const unsigned char *source = data;
        bad = unfill(source, num_chars - (num_chars % 2), out, REV_STRICT);
        if (bad == -1 && (num_chars % 2) != 0 && REV_STRICT[source[num_chars - 1]] == REV_INVALID) {
            bad = num_chars - 1;
        }
    }
    else {
        bad = first_invalid_wide(kind, data, num_chars);
        if (bad == -1) {
            Py_DECREF(result);
            PyErr_SetString(PyExc_SystemError, "a non-ASCII str kind held only ASCII characters");
            return NULL;
        }
    }
    if (bad != -1) {
        Py_DECREF(result);
        const Py_UCS4 code_point = PyUnicode_READ(kind, data, bad);
        return radixly_raise_decode_error(bad, "invalid base16 character U+%x at index %zd",
                                          (unsigned)code_point, bad);
    }
    if ((num_chars % 2) != 0) {
        Py_DECREF(result);
        return radixly_raise_decode_error(
            num_chars, "odd length: %zd characters, the last byte needs two digits", num_chars);
    }
    return result;
}

const char radixly_b16encode_doc[] =
    PyDoc_STR("b16encode($module, /, s)\n"
              "--\n"
              "\n"
              "Encode the bytes-like object s using Base16 and return a bytes object.");
PyObject *
radixly_b16encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    radixly_param params[] = {{"s", &arg}};
    if (radixly_bind_args("b16encode", args, nargs, kwnames, params, 1, 1, 1) < 0) {
        return NULL;
    }
    /* binascii.hexlify's contract: a C-contiguous buffer, str refused. */
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len > PY_SSIZE_T_MAX / 2) {
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, 2 * view.len);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return NULL;
    }
    fill(view.buf, view.len, (unsigned char *)PyBytes_AS_STRING(result));
    PyBuffer_Release(&view);
    return result;
}

const char radixly_b16decode_doc[] =
    PyDoc_STR("b16decode($module, /, s, casefold=False)\n"
              "--\n"
              "\n"
              "Decode the Base16 encoded bytes-like object or ASCII string s.\n"
              "\n"
              "Optional casefold is a flag specifying whether a lowercase alphabet is\n"
              "acceptable as input.  For security purposes, the default is False.\n"
              "\n"
              "The result is returned as a bytes object.  A binascii.Error is raised if\n"
              "s is incorrectly padded or if there are non-alphabet characters present\n"
              "in the input.");
PyObject *
radixly_b16decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    PyObject *casefold = NULL;
    radixly_param params[] = {{"s", &arg}, {"casefold", &casefold}};
    if (radixly_bind_args("b16decode", args, nargs, kwnames, params, 2, 1, 2) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    /* The stdlib reads s before it looks at casefold, so a flag that raises comes second here too. */
    const int fold = radixly_compat_truth(casefold);
    if (fold < 0) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    const uint8_t *rev = fold ? REV_FOLD : REV_STRICT;
    /* The stdlib order: every character checked first, then the length. */
    for (Py_ssize_t i = 0; i < source.len; i++) {
        if (rev[source.data[i]] == REV_INVALID) {
            radixly_compat_input_release(&source);
            return radixly_binascii_error("Non-base16 digit found");
        }
    }
    if ((source.len % 2) != 0) {
        radixly_compat_input_release(&source);
        return radixly_binascii_error("Odd-length string");
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, source.len / 2);
    if (result == NULL) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    const Py_ssize_t bad = unfill(source.data, source.len, (unsigned char *)PyBytes_AS_STRING(result), rev);
    assert(bad == -1);
    (void)bad;
    radixly_compat_input_release(&source);
    return result;
}
