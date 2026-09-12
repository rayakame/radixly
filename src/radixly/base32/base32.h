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

/* The shared engine: hex selects the base32hex alphabet and, for the compat decoder, drops the map01 keyword.
 */
PyObject *radixly_base32_encode_with(PyObject *arg, int hex);
PyObject *radixly_base32_decode_with(PyObject *arg, int hex);
PyObject *radixly_b32encode_with(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames, int hex);
PyObject *radixly_b32decode_with(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames, int hex);

extern const char radixly_base32_encode_doc[];
PyObject *radixly_base32_encode(PyObject *self, PyObject *arg);

extern const char radixly_base32_decode_doc[];
PyObject *radixly_base32_decode(PyObject *self, PyObject *arg);

extern const char radixly_b32encode_doc[];
PyObject *radixly_b32encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

extern const char radixly_b32decode_doc[];
PyObject *radixly_b32decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

#endif // RADIXLY_BASE32_H
