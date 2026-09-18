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

/* The bytes a stdlib-shaped function reads: a view when the argument is contiguous, a private copy
 * otherwise. */
typedef struct {
    const unsigned char *data;
    Py_ssize_t len;
    Py_buffer view;
    PyObject *copy;
    PyObject *coerced; /* what the stdlib's _bytes_from_decode_data passes on as is; NULL where it makes fresh
                          bytes */
    int has_view;
} radixly_compat_input;

int radixly_compat_exec(PyObject *module);

/* binascii.Error(message); always returns NULL. */
PyObject *radixly_binascii_error(const char *message);

/* binascii.Error mit context dahinter, im Traceback verborgen, wie `raise ... from None`. Stiehlt context. */
PyObject *radixly_binascii_error_from(const char *message, PyObject *context);

/* binascii.Error(format % args), PyErr_Format style; always returns NULL. */
PyObject *radixly_binascii_error_format(const char *format, ...);

/* The exception currently raised, as a new reference, with the error state cleared. */
PyObject *radixly_compat_take_raised(void);

/* type(message) with context behind it, hidden as `raise ... from None` hides it. Steals message and
 * context; returns NULL. */
PyObject *radixly_raise_from(PyObject *type, PyObject *message, PyObject *context);

/* type(message) raised as `raise ... from cause`: the cause is the context too. Steals message and cause;
 * returns NULL. */
PyObject *radixly_raise_from_cause(PyObject *type, PyObject *message, PyObject *cause);

/* struct.error(message), the context the stdlib's 85-family decoders leave behind an overflow. */
PyObject *radixly_struct_error(const char *message);

/* The stdlib's _bytes_from_decode_data: an ASCII str, or anything memoryview accepts, copied when strided. */
int radixly_compat_decode_input(PyObject *arg, radixly_compat_input *input);

/* memoryview(arg).tobytes(): any buffer, copied when strided, str refused with memoryview's own words. */
int radixly_compat_buffer_input(PyObject *arg, radixly_compat_input *input);

/* binascii's ascii_buffer converter: an ASCII str's own bytes, or a C-contiguous buffer, with its wording. */
int radixly_compat_ascii_buffer_input(PyObject *arg, radixly_compat_input *input);

/* arg.__class__.__name__, which the stdlib names in its type errors; a new reference, or NULL. */
PyObject *radixly_compat_class_name(PyObject *arg);

/* Put context behind the exception now raised, as an active except block does. Steals context. */
void radixly_compat_set_context(PyObject *context);

void radixly_compat_input_release(radixly_compat_input *input);

/* PyObject_IsTrue for an optional flag; absent means false. Returns -1 with an exception on failure. */
int radixly_compat_truth(PyObject *arg);

/* Whether the interpreter runs with -O, where the stdlib's asserts are gone and maketrans raises instead. */
int radixly_compat_optimized(void);

/* The stdlib's `assert len(x) == expected, repr(x)` on a _bytes_from_decode_data result, then maketrans's own
 * check of the buffer: 0 when both pass; -1 with the AssertionError, or with maketrans's ValueError. */
int radixly_compat_check_length(const radixly_compat_input *input, Py_ssize_t expected);

#endif // RADIXLY_COMPAT_H
