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
#include "args.h"

static void
raise_too_many(const char *function, Py_ssize_t nargs, Py_ssize_t required, Py_ssize_t max_positional)
{
    if (required == max_positional) {
        PyErr_Format(PyExc_TypeError, "%s() takes %zd positional argument%s but %zd were given", function,
                     max_positional, max_positional == 1 ? "" : "s", nargs);
    }
    else {
        PyErr_Format(PyExc_TypeError, "%s() takes from %zd to %zd positional arguments but %zd were given",
                     function, required, max_positional, nargs);
    }
}

int
radixly_bind_args(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                  radixly_param *params, Py_ssize_t num_params, Py_ssize_t required,
                  Py_ssize_t max_positional)
{
    /* A Python function judges the keywords before the positional count, so the drop-in does too. */
    for (Py_ssize_t i = 0; i < Py_MIN(nargs, max_positional); i++) {
        *params[i].value = args[i];
    }
    const Py_ssize_t num_kwargs = kwnames == NULL ? 0 : PyTuple_GET_SIZE(kwnames);
    for (Py_ssize_t k = 0; k < num_kwargs; k++) {
        PyObject *name = PyTuple_GET_ITEM(kwnames, k);
        Py_ssize_t found = -1;
        for (Py_ssize_t i = 0; i < num_params; i++) {
            if (params[i].name != NULL && PyUnicode_CompareWithASCIIString(name, params[i].name) == 0) {
                found = i;
                break;
            }
        }
        if (found == -1) {
            PyErr_Format(PyExc_TypeError, "%s() got an unexpected keyword argument '%U'", function, name);
            return -1;
        }
        if (found < nargs) {
            PyErr_Format(PyExc_TypeError, "%s() got multiple values for argument '%s'", function,
                         params[found].name);
            return -1;
        }
        *params[found].value = args[nargs + k];
    }
    if (nargs > max_positional) {
        raise_too_many(function, nargs, required, max_positional);
        return -1;
    }
    for (Py_ssize_t i = 0; i < required; i++) {
        if (*params[i].value == NULL) {
            PyErr_Format(PyExc_TypeError, "%s() missing 1 required positional argument: '%s'", function,
                         params[i].name);
            return -1;
        }
    }
    return 0;
}
