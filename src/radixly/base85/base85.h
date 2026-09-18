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
#ifndef RADIXLY_BASE85_H
#define RADIXLY_BASE85_H
#include <Python.h>

extern int radixly_base85_exec(PyObject *module);

/* The stdlib's _85encode: four bytes to five characters of alphabet, the tail's padding dropped unless pad;
 * fold_nuls and fold_spaces are Ascii85's z and y. fold_spaces is read at the first word that is not zero, as
 * the stdlib reads it. Returns a new bytes, or NULL with the exception set. */
PyObject *radixly_85_encode(const unsigned char *data, Py_ssize_t len, const char *alphabet, PyObject *pad,
                            int fold_nuls, PyObject *fold_spaces);

/* Five characters to four bytes through rev (0xFF invalid), the stdlib's b85decode with codec in the
 * messages. */
PyObject *radixly_85_decode(const unsigned char *data, Py_ssize_t len, const unsigned char *rev,
                            const char *codec);

/* The strict codecs: zeromq selects the Z85 alphabet. */
PyObject *radixly_base85_encode_with(PyObject *arg, int zeromq);
PyObject *radixly_base85_decode_with(PyObject *arg, int zeromq);

extern const char radixly_base85_encode_doc[];
PyObject *radixly_base85_encode(PyObject *self, PyObject *arg);

extern const char radixly_base85_decode_doc[];
PyObject *radixly_base85_decode(PyObject *self, PyObject *arg);

extern const char radixly_b85encode_doc[];
PyObject *radixly_b85encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

extern const char radixly_b85decode_doc[];
PyObject *radixly_b85decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

extern const char radixly_z85encode_doc[];
PyObject *radixly_z85encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

extern const char radixly_z85decode_doc[];
PyObject *radixly_z85decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

#endif // RADIXLY_BASE85_H
