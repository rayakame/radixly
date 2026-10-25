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
#ifndef RADIXLY_BASE16_H
#define RADIXLY_BASE16_H
#include <Python.h>

extern int radixly_base16_exec(PyObject *module);

/* The engine every base16 shape shares. */

enum { RADIXLY_HEX_UPPER, RADIXLY_HEX_ANY };

/* The reverse table: RADIXLY_HEX_UPPER reads 0-9 and A-F, RADIXLY_HEX_ANY a-f as well; a cell of 16 or more
 * is not a digit. */
const uint8_t *radixly_hex_table(int which);

/* The two uppercase digits of every byte. */
void radixly_hex_fill(const unsigned char *data, Py_ssize_t len, unsigned char *out);

/* Decode whole pairs from the start; returns the digits consumed, an even count, stopping before the first
 * pair that holds a non-digit. */
Py_ssize_t radixly_hex_pairs(const unsigned char *digits, Py_ssize_t len, unsigned char *out,
                             const uint8_t *rev);

extern const char radixly_base16_encode_doc[];
PyObject *radixly_base16_encode(PyObject *self, PyObject *arg);
extern const char radixly_base16_decode_doc[];
PyObject *radixly_base16_decode(PyObject *self, PyObject *arg);

/* The drop-in: base16/compat.c. */
extern const char radixly_b16encode_doc[];
PyObject *radixly_b16encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b16decode_doc[];
PyObject *radixly_b16decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b16encode_py315_doc[];
PyObject *radixly_b16encode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b16decode_py315_doc[];
PyObject *radixly_b16decode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

#endif // RADIXLY_BASE16_H
