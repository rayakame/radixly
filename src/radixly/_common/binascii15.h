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
#ifndef RADIXLY_BINASCII15_H
#define RADIXLY_BINASCII15_H
#include <Python.h>

/* CPython 3.15 rebuilt the standard library's base64 as a shell over new binascii functions. These are those
 * functions, ported line for line from Modules/binascii.c, so the drop-in says on 3.15 what the standard
 * library says. Every function returns a new bytes, or NULL with binascii.Error (or the converter's own
 * exception) set. An ignore set of length zero ignores nothing. */

enum { RADIXLY_PY315_TABLE_SIZE = 256 };

/* binascii's reverse table of an alphabet: every byte invalid (0xFF), the alphabet's own indexes, later
 * entries winning, and the pad character (or -1 for none) mapped to size. */
void radixly_py315_reverse_table(const unsigned char *alphabet, unsigned size, int pad,
                                 unsigned char table[RADIXLY_PY315_TABLE_SIZE]);

/* Argument Clinic's size_t converter as 3.15 has it: __index__ accepted, a negative value a ValueError, one
 * past size_t an OverflowError. 0 on success, -1 with the exception set. */
int radixly_py315_size_t(PyObject *arg, size_t *value);

PyObject *radixly_py315_a2b_base64(const unsigned char *data, Py_ssize_t len, int strict, int padded,
                                   const unsigned char *table, const unsigned char *ignore,
                                   Py_ssize_t ignore_len, int canonical);
PyObject *radixly_py315_b2a_base64(const unsigned char *data, Py_ssize_t len, int padded, size_t wrapcol,
                                   int newline, const unsigned char *alphabet);

PyObject *radixly_py315_a2b_base32(const unsigned char *data, Py_ssize_t len, int padded,
                                   const unsigned char *table, const unsigned char *ignore,
                                   Py_ssize_t ignore_len, int canonical);
PyObject *radixly_py315_b2a_base32(const unsigned char *data, Py_ssize_t len, int padded, size_t wrapcol,
                                   const unsigned char *alphabet);

PyObject *radixly_py315_a2b_base85(const unsigned char *data, Py_ssize_t len, const unsigned char *table,
                                   const unsigned char *ignore, Py_ssize_t ignore_len, int canonical);
PyObject *radixly_py315_b2a_base85(const unsigned char *data, Py_ssize_t len, int pad, size_t wrapcol,
                                   const unsigned char *alphabet);

PyObject *radixly_py315_a2b_ascii85(const unsigned char *data, Py_ssize_t len, int foldspaces, int adobe,
                                    const unsigned char *ignore, Py_ssize_t ignore_len, int canonical);
PyObject *radixly_py315_b2a_ascii85(const unsigned char *data, Py_ssize_t len, int foldspaces, size_t wrapcol,
                                    int pad, int adobe);

PyObject *radixly_py315_a2b_hex(const unsigned char *data, Py_ssize_t len, const unsigned char *ignore,
                                Py_ssize_t ignore_len);

/* hexlify(data, sep=b'\n', bytes_per_sep=...).upper(): a negative count groups from the left, a positive one
 * from the right, zero or a count covering the whole input groups nothing. */
PyObject *radixly_py315_hexlify_upper(const unsigned char *data, Py_ssize_t len, Py_ssize_t bytes_per_sep);

#endif // RADIXLY_BINASCII15_H
