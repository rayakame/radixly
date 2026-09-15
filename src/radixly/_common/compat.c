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
#include "compat.h"

static PyObject *binascii_error = NULL;

int
radixly_compat_exec(PyObject *Py_UNUSED(module))
{
    /* The drop-in raises the stdlib's own exception type, fetched once and kept for the interpreter's life.
     */
    PyObject *binascii = PyImport_ImportModule("binascii");
    if (binascii == NULL) {
        return -1;
    }
    PyObject *error = PyObject_GetAttrString(binascii, "Error");
    Py_DECREF(binascii);
    if (error == NULL) {
        return -1;
    }
    Py_XSETREF(binascii_error, error);
    return 0;
}

/* The exception currently raised, as a new reference, with the error state cleared. */
static PyObject *
take_raised(void)
{
#if PY_VERSION_HEX >= 0x030C0000
    return PyErr_GetRaisedException();
#else
    PyObject *type;
    PyObject *value;
    PyObject *traceback;
    PyErr_Fetch(&type, &value, &traceback);
    PyErr_NormalizeException(&type, &value, &traceback);
    if (traceback != NULL) {
        PyException_SetTraceback(value, traceback);
    }
    Py_XDECREF(traceback);
    Py_XDECREF(type);
    return value;
#endif
}

/* Raise error with context behind it; suppress hides it, the way `raise ... from None` does. Steals both. */
static int
raise_with_context(PyObject *error, PyObject *context, int suppress)
{
    if (error == NULL) {
        Py_XDECREF(context);
        return -1;
    }
    PyException_SetContext(error, context); /* steals context */
    if (suppress != 0 && PyObject_SetAttrString(error, "__suppress_context__", Py_True) < 0) {
        Py_DECREF(error);
        return -1;
    }
#if PY_VERSION_HEX >= 0x030C0000
    PyErr_SetRaisedException(error);
#else
    PyErr_Restore(Py_NewRef(Py_TYPE(error)), error, NULL);
#endif
    return -1;
}

PyObject *
radixly_binascii_error(const char *message)
{
    if (binascii_error == NULL) {
        PyErr_SetString(PyExc_SystemError, "radixly._core was not initialised");
        return NULL;
    }
    PyErr_SetString(binascii_error, message);
    return NULL;
}

PyObject *
radixly_binascii_error_from(const char *message, PyObject *context)
{
    if (context == NULL) {
        return NULL; /* the caller's own failure is already set */
    }
    if (binascii_error == NULL) {
        Py_DECREF(context);
        PyErr_SetString(PyExc_SystemError, "radixly._core was not initialised");
        return NULL;
    }
    PyObject *error = PyObject_CallFunction(binascii_error, "s", message);
    raise_with_context(error, context, 1);
    return NULL;
}

static int
input_from_view(radixly_compat_input *input)
{
    if (PyBuffer_IsContiguous(&input->view, 'C')) {
        input->data = input->view.buf;
        input->len = input->view.len;
        input->has_view = 1;
        return 0;
    }
    input->copy = PyBytes_FromStringAndSize(NULL, input->view.len);
    if (input->copy == NULL) {
        PyBuffer_Release(&input->view);
        return -1;
    }
    if (PyBuffer_ToContiguous(PyBytes_AS_STRING(input->copy), &input->view, input->view.len, 'C') < 0) {
        PyBuffer_Release(&input->view);
        Py_CLEAR(input->copy);
        return -1;
    }
    PyBuffer_Release(&input->view);
    input->data = (const unsigned char *)PyBytes_AS_STRING(input->copy);
    input->len = PyBytes_GET_SIZE(input->copy);
    return 0;
}

/* The stdlib raises this inside `except UnicodeEncodeError`, so the traceback shows that error as context. */
static int
raise_non_ascii(PyObject *arg)
{
    PyObject *encoded = PyUnicode_AsASCIIString(arg);
    if (encoded != NULL) {
        Py_DECREF(encoded); /* unreachable: the caller saw a non-ASCII character */
        PyErr_SetString(PyExc_ValueError, "string argument should contain only ASCII characters");
        return -1;
    }
    PyObject *context = take_raised();
    PyObject *error =
        PyObject_CallFunction(PyExc_ValueError, "s", "string argument should contain only ASCII characters");
    return raise_with_context(error, context, 0);
}

/* The stdlib's `s.encode('ascii')`, for anything that is a str without being exactly one. */
static int
input_from_encode(PyObject *arg, radixly_compat_input *input)
{
    PyObject *encoded = PyObject_CallMethod(arg, "encode", "s", "ascii");
    if (encoded == NULL) {
        if (!PyErr_ExceptionMatches(PyExc_UnicodeEncodeError)) {
            return -1; /* the stdlib converts only UnicodeEncodeError */
        }
        PyObject *context = take_raised();
        PyObject *error = PyObject_CallFunction(PyExc_ValueError, "s",
                                                "string argument should contain only ASCII characters");
        return raise_with_context(error, context, 0);
    }
    // NOLINTNEXTLINE(hicpp-signed-bitwise)
    const int failed = PyObject_GetBuffer(encoded, &input->view, PyBUF_FULL_RO) < 0;
    Py_DECREF(encoded); /* the view holds its own reference */
    if (failed) {
        return -1;
    }
    return input_from_view(input);
}

/* The stdlib names s.__class__.__name__ and writes `from None`, so context stays hidden. Steals context. */
static int
raise_not_bytes_like(PyObject *arg, PyObject *context)
{
    PyObject *cls = PyObject_GetAttrString(arg, "__class__");
    if (cls == NULL) {
        Py_XDECREF(context);
        return -1;
    }
    PyObject *name = PyObject_GetAttrString(cls, "__name__");
    Py_DECREF(cls);
    if (name == NULL) {
        Py_XDECREF(context);
        return -1;
    }
    PyObject *message =
        PyUnicode_FromFormat("argument should be a bytes-like object or ASCII string, not %R", name);
    Py_DECREF(name);
    if (message == NULL) {
        Py_XDECREF(context);
        return -1;
    }
    PyObject *error = PyObject_CallOneArg(PyExc_TypeError, message);
    Py_DECREF(message);
    return raise_with_context(error, context, 1);
}

int
radixly_compat_decode_input(PyObject *arg, radixly_compat_input *input)
{
    input->copy = NULL;
    input->has_view = 0;
    if (PyUnicode_CheckExact(arg)) {
#if PY_VERSION_HEX < 0x030C0000
        /* 3.11 can still meet legacy, non-ready strings; IS_ASCII on one is UB. Compiles out on 3.12+. */
        if (PyUnicode_READY(arg) == -1) {
            return -1;
        }
#endif
        if (!PyUnicode_IS_ASCII(arg)) {
            return raise_non_ascii(arg);
        }
        input->data = PyUnicode_1BYTE_DATA(arg);
        input->len = PyUnicode_GET_LENGTH(arg);
        return 0;
    }
    /* The stdlib dispatches on isinstance(s, str), so a subclass's own encode and a proxy's __class__ decide.
     * bytes and bytearray answer first: they are the common case and can never be a str. */
    if (!PyBytes_CheckExact(arg) && !PyByteArray_CheckExact(arg)) {
        const int is_str = PyObject_IsInstance(arg, (PyObject *)&PyUnicode_Type);
        if (is_str < 0) {
            return -1;
        }
        if (is_str != 0) {
            return input_from_encode(arg, input);
        }
    }
    // NOLINTNEXTLINE(hicpp-signed-bitwise)
    if (PyObject_GetBuffer(arg, &input->view, PyBUF_FULL_RO) < 0) {
        /* The stdlib rewords only the TypeError out of memoryview(s); anything else is the object's own. */
        if (!PyErr_ExceptionMatches(PyExc_TypeError)) {
            return -1;
        }
        return raise_not_bytes_like(arg, take_raised());
    }
    return input_from_view(input);
}

int
radixly_compat_buffer_input(PyObject *arg, radixly_compat_input *input)
{
    input->copy = NULL;
    input->has_view = 0;
    /* memoryview(s) has its own words for an object without the protocol and passes every other error on. */
    if (!PyObject_CheckBuffer(arg)) {
        PyErr_Format(PyExc_TypeError, "memoryview: a bytes-like object is required, not '%.200s'",
                     Py_TYPE(arg)->tp_name);
        return -1;
    }
    // NOLINTNEXTLINE(hicpp-signed-bitwise)
    if (PyObject_GetBuffer(arg, &input->view, PyBUF_FULL_RO) < 0) {
        return -1;
    }
    return input_from_view(input);
}

void
radixly_compat_input_release(radixly_compat_input *input)
{
    if (input->has_view) {
        PyBuffer_Release(&input->view);
        input->has_view = 0;
    }
    Py_CLEAR(input->copy);
}

int
radixly_compat_truth(PyObject *arg)
{
    return arg == NULL ? 0 : PyObject_IsTrue(arg);
}

PyObject *
radixly_binascii_error_format(const char *format, ...)
{
    if (binascii_error == NULL) {
        PyErr_SetString(PyExc_SystemError, "radixly._core was not initialised");
        return NULL;
    }
    va_list args;
    va_start(args, format);
    PyErr_FormatV(binascii_error, format, args);
    va_end(args);
    return NULL;
}

int
radixly_compat_optimized(void)
{
    PyObject *flags = PySys_GetObject("flags"); /* borrowed */
    if (flags == NULL) {
        return 0;
    }
    PyObject *optimize = PyObject_GetAttrString(flags, "optimize");
    if (optimize == NULL) {
        PyErr_Clear();
        return 0;
    }
    const long level = PyLong_AsLong(optimize);
    Py_DECREF(optimize);
    if (level == -1 && PyErr_Occurred()) {
        PyErr_Clear();
        return 0;
    }
    return level > 0;
}

int
radixly_compat_check_length(PyObject *arg, const radixly_compat_input *input, Py_ssize_t expected)
{
    if (input->len == expected) {
        return 0;
    }
    if (radixly_compat_optimized()) {
        PyErr_SetString(PyExc_ValueError, "maketrans arguments must have same length");
        return -1;
    }
    PyObject *shown;
    if (PyBytes_Check(arg) || PyByteArray_Check(arg)) {
        shown = Py_NewRef(arg); /* bytes and bytearray pass through the stdlib's coercion untouched */
    }
    else {
        shown = PyBytes_FromStringAndSize((const char *)input->data, input->len);
    }
    if (shown == NULL) {
        return -1;
    }
    PyObject *repr = PyObject_Repr(shown);
    Py_DECREF(shown);
    if (repr == NULL) {
        return -1;
    }
    PyErr_SetObject(PyExc_AssertionError, repr);
    Py_DECREF(repr);
    return -1;
}
