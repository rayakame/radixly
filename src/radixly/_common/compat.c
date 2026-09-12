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

int
radixly_compat_decode_input(PyObject *arg, radixly_compat_input *input)
{
    input->copy = NULL;
    input->has_view = 0;
    if (PyUnicode_Check(arg)) {
        if (!PyUnicode_IS_ASCII(arg)) {
            PyErr_SetString(PyExc_ValueError, "string argument should contain only ASCII characters");
            return -1;
        }
        input->data = PyUnicode_1BYTE_DATA(arg);
        input->len = PyUnicode_GET_LENGTH(arg);
        return 0;
    }
    // NOLINTNEXTLINE(hicpp-signed-bitwise)
    if (PyObject_GetBuffer(arg, &input->view, PyBUF_FULL_RO) < 0) {
        PyErr_Clear();
        PyErr_Format(PyExc_TypeError, "argument should be a bytes-like object or ASCII string, not '%.200s'",
                     Py_TYPE(arg)->tp_name);
        return -1;
    }
    return input_from_view(input);
}

int
radixly_compat_buffer_input(PyObject *arg, radixly_compat_input *input)
{
    input->copy = NULL;
    input->has_view = 0;
    // NOLINTNEXTLINE(hicpp-signed-bitwise)
    if (PyObject_GetBuffer(arg, &input->view, PyBUF_FULL_RO) < 0) {
        PyErr_Clear();
        PyErr_Format(PyExc_TypeError, "memoryview: a bytes-like object is required, not '%.200s'",
                     Py_TYPE(arg)->tp_name);
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
