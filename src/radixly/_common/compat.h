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
#ifndef RADIXLY_COMPAT_H
#define RADIXLY_COMPAT_H
#include <Python.h>

/* The bytes an stdlib-shaped function reads: a view when the argument is contiguous, a private copy
 * otherwise. */
typedef struct {
    const unsigned char *data;
    Py_ssize_t len;
    Py_buffer view;
    PyObject *copy;
    int has_view;
} radixly_compat_input;

int radixly_compat_exec(PyObject *module);

/* binascii.Error(message); always returns NULL. */
PyObject *radixly_binascii_error(const char *message);

/* The stdlib's _bytes_from_decode_data: an ASCII str, or anything memoryview accepts, copied when strided. */
int radixly_compat_decode_input(PyObject *arg, radixly_compat_input *input);

/* memoryview(arg).tobytes(): any buffer, copied when strided, str refused with memoryview's own words. */
int radixly_compat_buffer_input(PyObject *arg, radixly_compat_input *input);

void radixly_compat_input_release(radixly_compat_input *input);

/* PyObject_IsTrue for an optional flag; absent means false. Returns -1 with an exception on failure. */
int radixly_compat_truth(PyObject *arg);

#endif // RADIXLY_COMPAT_H
