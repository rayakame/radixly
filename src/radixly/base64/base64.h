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

/* The engine every base64 shape shares. */

enum { RADIXLY_B64_STD, RADIXLY_B64_URL };
enum { RADIXLY_B64_PAD_VALUE = 64, RADIXLY_B64_INVALID = 0xFF, RADIXLY_B64_TABLE_SIZE = 256 };

const char *radixly_b64_alphabet(int which);

/* The reverse table of an alphabet: its 64 values, '=' as RADIXLY_B64_PAD_VALUE, everything else invalid. */
const unsigned char *radixly_b64_table(int which);

/* binascii's reverse table of any 64-byte alphabet, later entries winning, '=' mapped to the pad value. */
void radixly_b64_reverse_table(const unsigned char *alphabet, unsigned char table[RADIXLY_B64_TABLE_SIZE]);

/* Encode whole trios; returns the bytes consumed, a multiple of three. */
Py_ssize_t radixly_b64_fill(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which);

/* The characters of a one- or two-byte tail, no padding; returns their count. */
int radixly_b64_tail(const unsigned char *data, Py_ssize_t leftover, unsigned char *out, int which);

/* RFC 4648 with padding: 4 * ceil(len / 3) characters. */
void radixly_b64_encode(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which);

/* Decode whole quads of alphabet characters from the start; returns the characters consumed, a multiple of
 * four, stopping before the first quad holding a pad or a non-alphabet byte. */
Py_ssize_t radixly_b64_quads(const unsigned char *text, Py_ssize_t len, unsigned char *out,
                             const unsigned char *rev);

/* The bytes a decode can produce at most: whole groups rounded up, less the trailing pads when '=' is the
 * pad. */
Py_ssize_t radixly_b64_decode_bound(const unsigned char *text, Py_ssize_t len, const unsigned char *rev);

PyObject *radixly_base64_encode_with(PyObject *arg, int which);
PyObject *radixly_base64_decode_with(PyObject *arg, int which);
extern const char radixly_base64_encode_doc[];
PyObject *radixly_base64_encode(PyObject *self, PyObject *arg);
extern const char radixly_base64_decode_doc[];
PyObject *radixly_base64_decode(PyObject *self, PyObject *arg);

/* The drop-in: base64/compat.c. */
extern int radixly_b64_compat_exec(PyObject *module);
PyObject *radixly_b64encode_with(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames, int url, int with_altchars);
PyObject *radixly_b64decode_with(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames, int url, int with_options);
extern const char radixly_encodebytes_doc[];
PyObject *radixly_encodebytes(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_decodebytes_doc[];
PyObject *radixly_decodebytes(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_encode_doc[];
PyObject *radixly_encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_decode_doc[];
PyObject *radixly_decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_a2b_base64_variant_doc[];
PyObject *radixly_a2b_base64_variant(PyObject *self, PyObject *arg);
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

typedef enum { RADIXLY_B64_FULL, RADIXLY_B64_STANDARD, RADIXLY_B64_URLSAFE } radixly_b64_shape;
PyObject *radixly_b64encode_with_py315(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                       PyObject *kwnames, radixly_b64_shape shape);
PyObject *radixly_b64decode_with_py315(const char *function, PyObject *const *args, Py_ssize_t nargs,
                                       PyObject *kwnames, radixly_b64_shape shape);
extern const char radixly_b64encode_py315_doc[];
PyObject *radixly_b64encode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b64decode_py315_doc[];
PyObject *radixly_b64decode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
PyObject *radixly_standard_b64encode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs,
                                           PyObject *kwnames);
PyObject *radixly_standard_b64decode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs,
                                           PyObject *kwnames);
PyObject *radixly_encodebytes_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs,
                                    PyObject *kwnames);

#endif // RADIXLY_BASE64_H
