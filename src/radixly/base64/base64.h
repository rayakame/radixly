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
#ifndef RADIXLY_BASE64_H
#define RADIXLY_BASE64_H
#include <Python.h>

extern int radixly_base64_exec(PyObject *module);

/* The shared engine: url selects the base64url alphabet; the compat decoder takes it as the stdlib's urlsafe
 * translation, on top of the standard alphabet. */
PyObject *radixly_base64_encode_with(PyObject *arg, int url);
PyObject *radixly_base64_decode_with(PyObject *arg, int url);
PyObject *radixly_b64encode_with(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames, int url, int with_altchars);
PyObject *radixly_b64decode_with(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames, int url, int with_options);

extern const char radixly_a2b_base64_variant_doc[];
PyObject *radixly_a2b_base64_variant(PyObject *self, PyObject *arg);

extern const char radixly_base64_encode_doc[];
PyObject *radixly_base64_encode(PyObject *self, PyObject *arg);

extern const char radixly_base64_decode_doc[];
PyObject *radixly_base64_decode(PyObject *self, PyObject *arg);

extern const char radixly_b64encode_doc[];
PyObject *radixly_b64encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

extern const char radixly_b64decode_doc[];
PyObject *radixly_b64decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

extern const char radixly_standard_b64encode_doc[];
PyObject *radixly_standard_b64encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs,
                                     PyObject *kwnames);

extern const char radixly_standard_b64decode_doc[];
PyObject *radixly_standard_b64decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs,
                                     PyObject *kwnames);

#endif // RADIXLY_BASE64_H
