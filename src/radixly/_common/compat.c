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

PyObject *
radixly_binascii_error(const char *message)
{
    assert(binascii_error != NULL);
    PyErr_SetString(binascii_error, message);
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
#if PY_VERSION_HEX >= 0x030C0000
    PyObject *context = PyErr_GetRaisedException();
#else
    PyObject *type;
    PyObject *context;
    PyObject *traceback;
    PyErr_Fetch(&type, &context, &traceback);
    PyErr_NormalizeException(&type, &context, &traceback);
    if (traceback != NULL) {
        PyException_SetTraceback(context, traceback);
    }
    Py_XDECREF(traceback);
    Py_XDECREF(type);
#endif
    PyObject *error =
        PyObject_CallFunction(PyExc_ValueError, "s", "string argument should contain only ASCII characters");
    if (error == NULL) {
        Py_XDECREF(context);
        return -1;
    }
    PyException_SetContext(error, context); /* steals context */
#if PY_VERSION_HEX >= 0x030C0000
    PyErr_SetRaisedException(error);
#else
    PyErr_Restore(Py_NewRef(Py_TYPE(error)), error, NULL);
#endif
    return -1;
}

/* The stdlib names s.__class__.__name__, which an object may spell differently from its type. */
static int
raise_not_bytes_like(PyObject *arg)
{
    PyObject *cls = PyObject_GetAttrString(arg, "__class__");
    if (cls == NULL) {
        return -1;
    }
    PyObject *name = PyObject_GetAttrString(cls, "__name__");
    Py_DECREF(cls);
    if (name == NULL) {
        return -1;
    }
    PyErr_Format(PyExc_TypeError, "argument should be a bytes-like object or ASCII string, not %R", name);
    Py_DECREF(name);
    return -1;
}

int
radixly_compat_decode_input(PyObject *arg, radixly_compat_input *input)
{
    input->copy = NULL;
    input->has_view = 0;
    if (PyUnicode_Check(arg)) {
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
    // NOLINTNEXTLINE(hicpp-signed-bitwise)
    if (PyObject_GetBuffer(arg, &input->view, PyBUF_FULL_RO) < 0) {
        /* The stdlib rewords only the TypeError out of memoryview(s); anything else is the object's own. */
        if (!PyErr_ExceptionMatches(PyExc_TypeError)) {
            return -1;
        }
        PyErr_Clear();
        return raise_not_bytes_like(arg);
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
