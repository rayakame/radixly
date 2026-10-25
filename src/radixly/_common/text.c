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
#include <string.h>
#include "text.h"

enum { ASCII_MAX = 0x7F, PLACEHOLDER = 0x80 }; /* the placeholder is in no alphabet */

int
radixly_text_init(radixly_text *text, PyObject *arg, int group_chars)
{
    if (!PyUnicode_Check(arg)) {
        PyErr_Format(PyExc_TypeError, "expected str, not %.200s", Py_TYPE(arg)->tp_name);
        return -1;
    }
#if PY_VERSION_HEX < 0x030C0000
    /* 3.11 can still meet legacy, non-ready strings; GET_LENGTH/KIND/DATA on one is UB. Compiles out
     * on 3.12+. */
    if (PyUnicode_READY(arg) == -1) {
        return -1;
    }
#endif
    const Py_ssize_t num_chars = PyUnicode_GET_LENGTH(arg);
    text->len = num_chars;
    text->wide_index = -1;
    text->wide_code_point = 0;
    text->scratch = NULL;
    if (PyUnicode_KIND(arg) == PyUnicode_1BYTE_KIND) {
        text->text = PyUnicode_1BYTE_DATA(arg);
        return 0;
    }
    const int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);
    Py_ssize_t wide = 0;
    while (wide < num_chars && PyUnicode_READ(kind, data, wide) <= ASCII_MAX) {
        wide++;
    }
    if (wide == num_chars) {
        PyErr_SetString(PyExc_SystemError, "a non-ASCII str kind held only ASCII characters");
        return -1;
    }
    const Py_ssize_t len = Py_MIN(num_chars, group_chars * ((wide / group_chars) + 1));
    text->scratch = PyMem_Malloc((size_t)len);
    if (text->scratch == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    for (Py_ssize_t i = 0; i < wide; i++) {
        text->scratch[i] = (unsigned char)PyUnicode_READ(kind, data, i);
    }
    memset(text->scratch + wide, PLACEHOLDER, (size_t)(len - wide));
    text->text = text->scratch;
    text->len = len;
    text->wide_index = wide;
    text->wide_code_point = PyUnicode_READ(kind, data, wide);
    return 0;
}

void
radixly_text_release(radixly_text *text)
{
    PyMem_Free(text->scratch);
    text->scratch = NULL;
}

Py_UCS4
radixly_text_code_point(const radixly_text *text, Py_ssize_t index)
{
    return index == text->wide_index ? text->wide_code_point : text->text[index];
}
