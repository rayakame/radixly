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
#include "base16.h"

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/internal.h"

enum { NUM_DIGITS = 16, DIGITS_PER_BYTE = 2 };
static const unsigned NIBBLE = 4U;

const char radixly_b16encode_doc[] =
    PyDoc_STR("b16encode($module, /, s)\n"
              "--\n"
              "\n"
              "Encode the bytes-like object s using Base16 and return a bytes object.");
PyObject *
radixly_b16encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    radixly_param params[] = {{"s", &arg}};
    if (radixly_bind_args("b16encode", args, nargs, kwnames, params, 1, 1, 1) < 0) {
        return NULL;
    }
    /* binascii.hexlify's contract: a C-contiguous buffer, str refused. */
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len >
        (PY_SSIZE_T_MAX / 2) - 1) { /* hexlify's own bound, one length tighter than PyUnicode_New's */
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, 2 * view.len);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return NULL;
    }
    radixly_hex_fill(view.buf, view.len, (unsigned char *)PyBytes_AS_STRING(result));
    PyBuffer_Release(&view);
    return result;
}

const char radixly_b16decode_doc[] =
    PyDoc_STR("b16decode($module, /, s, casefold=False)\n"
              "--\n"
              "\n"
              "Decode the Base16 encoded bytes-like object or ASCII string s.\n"
              "\n"
              "Optional casefold is a flag specifying whether a lowercase alphabet is\n"
              "acceptable as input.  For security purposes, the default is False.\n"
              "\n"
              "The result is returned as a bytes object.  A binascii.Error is raised if\n"
              "s is incorrectly padded or if there are non-alphabet characters present\n"
              "in the input.");
PyObject *
radixly_b16decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    PyObject *casefold = NULL;
    radixly_param params[] = {{"s", &arg}, {"casefold", &casefold}};
    if (radixly_bind_args("b16decode", args, nargs, kwnames, params, 2, 1, 2) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    /* The stdlib reads s before it looks at casefold, so a flag that raises comes second here too. */
    const int fold = radixly_compat_truth(casefold);
    if (fold < 0) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    const uint8_t *rev = radixly_hex_table(fold != 0 ? RADIXLY_HEX_ANY : RADIXLY_HEX_UPPER);
    PyObject *result = PyBytes_FromStringAndSize(NULL, source.len / DIGITS_PER_BYTE);
    if (result == NULL) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    /* The stdlib's order: every character is judged before the length. */
    const Py_ssize_t consumed =
        radixly_hex_pairs(source.data, source.len, (unsigned char *)PyBytes_AS_STRING(result), rev);
    const Py_ssize_t odd = source.len % DIGITS_PER_BYTE;
    const int invalid =
        consumed < source.len - odd || (odd != 0 && rev[source.data[source.len - 1]] >= NUM_DIGITS);
    radixly_compat_input_release(&source);
    if (invalid) {
        Py_DECREF(result);
        return radixly_binascii_error("Non-base16 digit found");
    }
    if (odd != 0) {
        Py_DECREF(result);
        return radixly_binascii_error("Odd-length string");
    }
    return result;
}

/* Python 3.15 made b16encode and b16decode shells over hexlify and unhexlify. */

static const char LOWER_HEX[] = "abcdef";

/* hexlify(data, sep=b'\n', bytes_per_sep=...).upper(): a negative count groups from the left, a positive one
 * from the right, zero or a count covering the whole input groups nothing. */
static PyObject *
hexlify_upper(const unsigned char *data, Py_ssize_t len, Py_ssize_t bytes_per_sep)
{
    size_t group = bytes_per_sep < 0 ? 0U - (size_t)bytes_per_sep : (size_t)bytes_per_sep;
    Py_ssize_t separators = 0;
    if (group != 0 && len > 0) {
        separators = (Py_ssize_t)(((size_t)len - 1U) / group);
    }
    if (len >= (PY_SSIZE_T_MAX / 2) - separators) {
        return PyErr_NoMemory();
    }
    if (group >= (size_t)len) {
        group = 0;
        separators = 0;
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, (len * DIGITS_PER_BYTE) + separators);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    if (group == 0) {
        radixly_hex_fill(data, len, out);
        return result;
    }
    /* The short group sits at the far end: first for a count from the right, last for one from the left. */
    const Py_ssize_t first = bytes_per_sep < 0 ? (Py_ssize_t)group : len - (separators * (Py_ssize_t)group);
    radixly_hex_fill(data, first, out);
    out += first * DIGITS_PER_BYTE;
    for (Py_ssize_t index = first; index < len; index += (Py_ssize_t)group) {
        *out++ = '\n';
        const Py_ssize_t chunk = Py_MIN((Py_ssize_t)group, len - index);
        radixly_hex_fill(data + index, chunk, out);
        out += chunk * DIGITS_PER_BYTE;
    }
    return result;
}

/* The stdlib's `-(wrapcol // 2)` after its two comparisons, as an object: hexlify converts it in its own
 * turn.
 */
static PyObject *
hex_bytes_per_sep(PyObject *wrapcol)
{
    PyObject *zero = PyLong_FromLong(0);
    if (zero == NULL) {
        return NULL;
    }
    const int negative = PyObject_RichCompareBool(wrapcol, zero, Py_LT);
    Py_DECREF(zero);
    if (negative < 0) {
        return NULL;
    }
    if (negative != 0) {
        PyErr_SetString(PyExc_ValueError, "Negative wrapcol");
        return NULL;
    }
    PyObject *two = PyLong_FromLong(2);
    if (two == NULL) {
        return NULL;
    }
    const int narrow = PyObject_RichCompareBool(wrapcol, two, Py_LT);
    PyObject *half = narrow < 0 ? NULL : PyNumber_FloorDivide(narrow != 0 ? two : wrapcol, two);
    Py_DECREF(two);
    if (half == NULL) {
        return NULL;
    }
    PyObject *per_sep = PyNumber_Negative(half);
    Py_DECREF(half);
    return per_sep;
}

/* hexlify's bytes_per_sep conversion: __index__, then a C ssize_t. */
static int
bytes_per_sep_value(PyObject *per_sep, Py_ssize_t *value)
{
    PyObject *index = PyNumber_Index(per_sep);
    if (index == NULL) {
        return -1;
    }
    *value = PyLong_AsSsize_t(index);
    Py_DECREF(index);
    return *value == -1 && PyErr_Occurred() ? -1 : 0;
}

const char radixly_b16encode_py315_doc[] =
    PyDoc_STR("b16encode($module, /, s, *, wrapcol=0)\n"
              "--\n"
              "\n"
              "Encode the bytes-like object s using Base16 and return a bytes object.\n"
              "\n"
              "If wrapcol is non-zero, insert a newline (b'\\n') character after at most\n"
              "every wrapcol characters.");
PyObject *
radixly_b16encode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    PyObject *wrapcol = NULL;
    radixly_param params[] = {{"s", &arg}, {"wrapcol", &wrapcol}};
    if (radixly_bind_args("b16encode", args, nargs, kwnames, params, 2, 1, 1) < 0) {
        return NULL;
    }
    /* `if not wrapcol` comes before hexlify sees s. */
    const int wrapped = radixly_compat_truth(wrapcol);
    if (wrapped < 0) {
        return NULL;
    }
    PyObject *per_sep = NULL;
    if (wrapped != 0) {
        per_sep = hex_bytes_per_sep(wrapcol);
        if (per_sep == NULL) {
            return NULL;
        }
    }
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) < 0) {
        Py_XDECREF(per_sep);
        return NULL;
    }
    Py_ssize_t bytes_per_sep = 0;
    if (per_sep != NULL) {
        const int converted = bytes_per_sep_value(per_sep, &bytes_per_sep);
        Py_DECREF(per_sep);
        if (converted < 0) {
            PyBuffer_Release(&view);
            return NULL;
        }
    }
    PyObject *result = hexlify_upper(view.buf, view.len, bytes_per_sep);
    PyBuffer_Release(&view);
    return result;
}

/* binascii.a2b_hex: whole pairs at speed, a lone digit or a non-digit one byte at a time. With skip_lower the
 * table refuses a-f and they pass as ignored, which is the stdlib's translate(None, b'abcdef') without the
 * copy. */
static PyObject *
a2b_hex(const unsigned char *data, Py_ssize_t len, const uint8_t *rev, int skip_lower,
        const unsigned char *ignore, Py_ssize_t ignore_len)
{
    radixly_ignore_set skip;
    radixly_ignore_set_init(&skip, ignore, ignore_len);
    PyObject *result = PyBytes_FromStringAndSize(NULL, len / DIGITS_PER_BYTE);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    unsigned char *out = start;
    unsigned leftchar = 0;
    int pair_pos = 0;
    Py_ssize_t index = 0;
    while (index < len) {
        if (pair_pos == 0) {
            const Py_ssize_t consumed = radixly_hex_pairs(data + index, len - index, out, rev);
            index += consumed;
            out += consumed / DIGITS_PER_BYTE;
            if (index >= len) {
                break;
            }
        }
        const unsigned char this_ch = data[index++];
        const unsigned digit = rev[this_ch];
        if (digit < NUM_DIGITS) {
            if (pair_pos == 0) {
                leftchar = digit;
                pair_pos = 1;
            }
            else {
                *out++ = (unsigned char)((leftchar << NIBBLE) | digit);
                pair_pos = 0;
            }
            continue;
        }
        if (skip_lower != 0 && this_ch >= 'a' && this_ch <= 'f') {
            continue;
        }
        if (radixly_ignored(&skip, this_ch) == 0) {
            Py_DECREF(result);
            return radixly_binascii_error("Non-hexadecimal digit found");
        }
    }
    if (pair_pos != 0) {
        Py_DECREF(result);
        return radixly_binascii_error("Odd number of hexadecimal digits");
    }
    return radixly_compat_finish(result, out - start);
}

/* With casefold the stdlib hands s and ignorechars straight to unhexlify. */
static PyObject *
b16decode_folded_py315(PyObject *arg, PyObject *ignorechars)
{
    radixly_compat_input source;
    if (radixly_compat_ascii_buffer_input(arg, &source) < 0) {
        return NULL;
    }
    radixly_compat_bytes ignore;
    if (radixly_compat_bytes_init(&ignore, ignorechars, NULL, 0) < 0) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    PyObject *result =
        a2b_hex(source.data, source.len, radixly_hex_table(RADIXLY_HEX_ANY), 0, ignore.data, ignore.len);
    radixly_compat_bytes_release(&ignore);
    radixly_compat_input_release(&source);
    return result;
}

/* The stdlib's `bytes(memoryview(ignorechars))`, unless it already is bytes. */
static PyObject *
ignorechars_as_bytes(PyObject *ignorechars)
{
    if (ignorechars == NULL) {
        return PyBytes_FromStringAndSize("", 0);
    }
    if (PyBytes_Check(ignorechars)) {
        return Py_NewRef(ignorechars);
    }
    PyObject *view = PyMemoryView_FromObject(ignorechars);
    if (view == NULL) {
        return NULL;
    }
    PyObject *copy = PyBytes_FromObject(view);
    Py_DECREF(view);
    return copy;
}

/* The stdlib refuses a lowercase digit that ignorechars does not admit before it reads any digit. */
static int
refuse_lowercase(const radixly_compat_input *source, PyObject *ignore)
{
    for (size_t i = 0; i < sizeof(LOWER_HEX) - 1; i++) {
        const unsigned char code = (unsigned char)LOWER_HEX[i];
        if (memchr(source->data, code, (size_t)source->len) == NULL) {
            continue;
        }
        PyObject *value = PyLong_FromLong(code);
        if (value == NULL) {
            return -1;
        }
        const int admitted = PySequence_Contains(ignore, value);
        Py_DECREF(value);
        if (admitted < 0) {
            return -1;
        }
        if (admitted == 0) {
            radixly_binascii_error("Non-base16 digit found");
            return -1;
        }
    }
    return 0;
}

static PyObject *
b16decode_strict_py315(PyObject *arg, PyObject *ignorechars)
{
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    PyObject *result = NULL;
    PyObject *ignore = ignorechars_as_bytes(ignorechars);
    if (ignore != NULL && refuse_lowercase(&source, ignore) == 0) {
        result = a2b_hex(source.data, source.len, radixly_hex_table(RADIXLY_HEX_UPPER), 1,
                         (const unsigned char *)PyBytes_AS_STRING(ignore), PyBytes_GET_SIZE(ignore));
    }
    Py_XDECREF(ignore);
    radixly_compat_input_release(&source);
    return result;
}

const char radixly_b16decode_py315_doc[] =
    PyDoc_STR("b16decode($module, /, s, casefold=False, *, ignorechars=b'')\n"
              "--\n"
              "\n"
              "Decode the Base16 encoded bytes-like object or ASCII string s.\n"
              "\n"
              "Optional casefold is a flag specifying whether a lowercase alphabet is\n"
              "acceptable as input.  For security purposes, the default is False.\n"
              "\n"
              "ignorechars should be a byte string containing characters to ignore\n"
              "from the input.\n"
              "\n"
              "The result is returned as a bytes object.  A binascii.Error is raised if\n"
              "s is incorrectly padded or if there are non-alphabet characters present\n"
              "in the input.");
PyObject *
radixly_b16decode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    PyObject *casefold = NULL;
    PyObject *ignorechars = NULL;
    radixly_param params[] = {{"s", &arg}, {"casefold", &casefold}, {"ignorechars", &ignorechars}};
    if (radixly_bind_args("b16decode", args, nargs, kwnames, params, 3, 1, 2) < 0) {
        return NULL;
    }
    /* `if not casefold` is the stdlib's first move, before it looks at s. */
    const int fold = radixly_compat_truth(casefold);
    if (fold < 0) {
        return NULL;
    }
    return fold != 0 ? b16decode_folded_py315(arg, ignorechars) : b16decode_strict_py315(arg, ignorechars);
}
