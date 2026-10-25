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
#ifndef RADIXLY_BASE32_H
#define RADIXLY_BASE32_H
#include <Python.h>

extern int radixly_base32_exec(PyObject *module);

/* The engine every base32 shape shares. */

enum { RADIXLY_B32_STD, RADIXLY_B32_HEX };
enum { RADIXLY_B32_PAD_VALUE = 32, RADIXLY_B32_INVALID = 0xFF, RADIXLY_B32_TABLE_SIZE = 256 };

const char *radixly_b32_alphabet(int which);

/* The reverse table of an alphabet: its 32 values, '=' as RADIXLY_B32_PAD_VALUE, everything else invalid; the
 * fold table reads lowercase letters as well. */
const unsigned char *radixly_b32_table(int which);
const unsigned char *radixly_b32_fold_table(int which);

/* Encode whole quints; returns the bytes consumed, a multiple of five. */
Py_ssize_t radixly_b32_fill(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which);

/* The characters of a one- to four-byte tail, no padding; returns their count. */
int radixly_b32_tail(const unsigned char *data, Py_ssize_t leftover, unsigned char *out, int which);

/* RFC 4648 with padding: 8 * ceil(len / 5) characters. */
void radixly_b32_encode(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which);

/* Decode whole octas of alphabet characters from the start; returns the characters consumed, a multiple of
 * eight, stopping before the first octa holding a pad or a non-alphabet byte. */
Py_ssize_t radixly_b32_octas(const unsigned char *text, Py_ssize_t len, unsigned char *out,
                             const unsigned char *rev);

/* The bytes a decode can produce at most: whole groups rounded up, less what the trailing pads cannot carry
 * when '=' is the pad. */
Py_ssize_t radixly_b32_decode_bound(const unsigned char *text, Py_ssize_t len, const unsigned char *rev);

PyObject *radixly_base32_encode_with(PyObject *arg, int which);
PyObject *radixly_base32_decode_with(PyObject *arg, int which);
extern const char radixly_base32_encode_doc[];
PyObject *radixly_base32_encode(PyObject *self, PyObject *arg);
extern const char radixly_base32_decode_doc[];
PyObject *radixly_base32_decode(PyObject *self, PyObject *arg);

/* The drop-in: base32/compat.c. */
PyObject *radixly_b32encode_with(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames, int which);
PyObject *radixly_b32decode_with(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames, int which);
extern const char radixly_b32encode_doc[];
PyObject *radixly_b32encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b32decode_doc[];
PyObject *radixly_b32decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
PyObject *radixly_b32encode_with_py315(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                       PyObject *kwnames, int which);
PyObject *radixly_b32decode_with_py315(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                       PyObject *kwnames, int which);
extern const char radixly_b32encode_py315_doc[];
PyObject *radixly_b32encode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b32decode_py315_doc[];
PyObject *radixly_b32decode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

#endif // RADIXLY_BASE32_H
