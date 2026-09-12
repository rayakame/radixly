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
#include "args.h"

#if PY_VERSION_HEX >= 0x030D0000
/* From 3.13 a Python function suggests the nearest keyword; this is Python/suggestions.c reduced to that. */
enum { MOVE_COST = 2, CASE_COST = 1, MAX_STRING_SIZE = 40, THIRD_SCALE = 6, THIRD_SLACK = 3 };
static const unsigned FIVE_BITS = 31U;

static size_t
substitution_cost(char first, char second)
{
    if (((unsigned)first & FIVE_BITS) != ((unsigned)second & FIVE_BITS)) {
        return MOVE_COST;
    }
    if (first == second) {
        return 0;
    }
    if (Py_TOLOWER((unsigned char)first) == Py_TOLOWER((unsigned char)second)) {
        return CASE_COST;
    }
    return MOVE_COST;
}

static size_t
levenshtein_distance(const char *first, size_t first_size, const char *second, size_t second_size,
                     size_t max_cost, size_t *buffer)
{
    while (first_size && second_size && first[0] == second[0]) {
        first++;
        first_size--;
        second++;
        second_size--;
    }
    while (first_size && second_size && first[first_size - 1] == second[second_size - 1]) {
        first_size--;
        second_size--;
    }
    if (first_size == 0 || second_size == 0) {
        return (first_size + second_size) * MOVE_COST;
    }
    if (first_size > MAX_STRING_SIZE || second_size > MAX_STRING_SIZE) {
        return max_cost + 1;
    }
    if (second_size < first_size) {
        const char *swap = first;
        first = second;
        second = swap;
        const size_t swap_size = first_size;
        first_size = second_size;
        second_size = swap_size;
    }
    if ((second_size - first_size) * MOVE_COST > max_cost) {
        return max_cost + 1;
    }
    for (size_t index = 0; index < first_size; index++) {
        buffer[index] = (index + 1) * MOVE_COST;
    }
    size_t result = 0;
    for (size_t second_index = 0; second_index < second_size; second_index++) {
        const char code = second[second_index];
        size_t distance = result = second_index * MOVE_COST;
        size_t minimum = SIZE_MAX;
        for (size_t index = 0; index < first_size; index++) {
            const size_t substitute = distance + substitution_cost(code, first[index]);
            distance = buffer[index];
            const size_t insert_delete = Py_MIN(result, distance) + MOVE_COST;
            result = Py_MIN(insert_delete, substitute);
            buffer[index] = result;
            if (result < minimum) {
                minimum = result;
            }
        }
        if (minimum > max_cost) {
            return max_cost + 1;
        }
    }
    return result;
}

/* The parameter name nearest to the unknown keyword by CPython's measure, or NULL. */
static const char *
suggest_keyword(PyObject *name, const radixly_param *params, Py_ssize_t num_params)
{
    Py_ssize_t name_size;
    const char *name_str = PyUnicode_AsUTF8AndSize(name, &name_size);
    if (name_str == NULL) {
        PyErr_Clear();
        return NULL;
    }
    size_t buffer[MAX_STRING_SIZE];
    const char *suggestion = NULL;
    size_t suggestion_distance = SIZE_MAX;
    for (Py_ssize_t i = 0; i < num_params; i++) {
        const char *item = params[i].name;
        if (item == NULL) {
            continue;
        }
        const size_t item_size = strlen(item);
        size_t max_distance = ((size_t)name_size + item_size + THIRD_SLACK) * MOVE_COST / THIRD_SCALE;
        max_distance = Py_MIN(max_distance, suggestion_distance - 1);
        const size_t distance =
            levenshtein_distance(name_str, (size_t)name_size, item, item_size, max_distance, buffer);
        if (distance > max_distance) {
            continue;
        }
        if (suggestion == NULL || distance < suggestion_distance) {
            suggestion = item;
            suggestion_distance = distance;
        }
    }
    return suggestion;
}
#endif

static void
raise_unexpected_keyword(const char *function, PyObject *name, const radixly_param *params,
                         Py_ssize_t num_params)
{
#if PY_VERSION_HEX >= 0x030D0000
    const char *suggestion = suggest_keyword(name, params, num_params);
    if (suggestion != NULL) {
        PyErr_Format(PyExc_TypeError, "%s() got an unexpected keyword argument '%U'. Did you mean '%s'?",
                     function, name, suggestion);
        return;
    }
#else
    (void)params;
    (void)num_params;
#endif
    PyErr_Format(PyExc_TypeError, "%s() got an unexpected keyword argument '%U'", function, name);
}

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
            raise_unexpected_keyword(function, name, params, num_params);
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
