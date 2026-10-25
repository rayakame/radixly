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
#include "base85.h"

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 4,
    GROUP_CHARS = 5,
    BASE = 85,
    TOP_DIGIT = 84, /* the '~' the stdlib appends, the largest digit */
};

static const uint64_t WORD_MAX = 0xFFFFFFFFU;
static const uint32_t FOUR_SPACES = 0x20202020U;

/* The encoder's cursor and the two folds the stdlib's list comprehension applies per word. */
typedef struct {
    unsigned char *out;
    int last_chunk_len;
    int folded_spaces; /* -1 until the first word that is not zero, when the stdlib reads foldspaces */
    int fold_nuls;
    PyObject *fold_spaces;
    int which;
} encoder;

/* One word as 'z', 'y' or five digits; -1 when reading foldspaces fails. */
static int
put_word(encoder *state, uint32_t word)
{
    if (state->fold_nuls && word == 0) {
        *state->out++ = 'z';
        state->last_chunk_len = 1;
        return 0;
    }
    if (state->folded_spaces < 0) {
        state->folded_spaces = radixly_compat_truth(state->fold_spaces);
        if (state->folded_spaces < 0) {
            return -1;
        }
    }
    if (state->folded_spaces && word == FOUR_SPACES) {
        *state->out++ = 'y';
        state->last_chunk_len = 1;
        return 0;
    }
    radixly_b85_digits(word, state->out, state->which);
    state->out += GROUP_CHARS;
    state->last_chunk_len = GROUP_CHARS;
    return 0;
}

/* Drop the tail's padding characters; a folded 'z' is spelled out first, as the stdlib does. */
static void
cut_padding(encoder *state, Py_ssize_t padding)
{
    if (state->last_chunk_len == 1) {
        unsigned char *chunk = state->out - 1;
        memset(chunk, radixly_b85_alphabet(state->which)[0], GROUP_CHARS);
        state->out = chunk + GROUP_CHARS;
    }
    state->out -= padding;
}

PyObject *
radixly_85_encode(const unsigned char *data, Py_ssize_t len, int which, PyObject *pad, int fold_nuls,
                  PyObject *fold_spaces)
{
    if (len > (PY_SSIZE_T_MAX / GROUP_CHARS) * GROUP_BYTES) {
        return PyErr_NoMemory();
    }
    const Py_ssize_t padding = (GROUP_BYTES - (len % GROUP_BYTES)) % GROUP_BYTES;
    const Py_ssize_t words = (len + padding) / GROUP_BYTES;
    PyObject *result = PyBytes_FromStringAndSize(NULL, GROUP_CHARS * words);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    encoder state = {out, 0, -1, fold_nuls, fold_spaces, which};
    Py_ssize_t offset = 0;
    if (!fold_nuls) {
        /* Without the 'z' fold every whole word spells five digits, which the engine writes at speed. */
        offset = radixly_b85_fill(data, len, out, which);
        state.out += (offset / GROUP_BYTES) * GROUP_CHARS;
        state.last_chunk_len = offset != 0 ? GROUP_CHARS : 0;
    }
    for (; offset + GROUP_BYTES <= len; offset += GROUP_BYTES) {
        const uint32_t word = ((uint32_t)data[offset] << 24U) | ((uint32_t)data[offset + 1] << 16U) |
                              ((uint32_t)data[offset + 2] << 8U) | data[offset + 3];
        if (put_word(&state, word) < 0) {
            Py_DECREF(result);
            return NULL;
        }
    }
    if (offset < len && put_word(&state, radixly_b85_word(data + offset, len - offset)) < 0) {
        Py_DECREF(result);
        return NULL;
    }
    if (padding != 0) {
        const int keep_padding = radixly_compat_truth(pad);
        if (keep_padding < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (!keep_padding) {
            cut_padding(&state, padding);
        }
    }
    return radixly_compat_finish(result, state.out - out);
}

/* The stdlib's `raise ValueError(...) from None` inside its except clauses: the TypeError or struct.error it
 * caught rides along as the hidden context. */
static PyObject *
raise_decode_error(const char *format, Py_ssize_t position, const char *codec, PyObject *context)
{
    if (context == NULL) {
        return NULL;
    }
    PyObject *message = PyUnicode_FromFormat(format, codec, position);
    return radixly_raise_from(PyExc_ValueError, message, context);
}

PyObject *
radixly_85_decode(const unsigned char *data, Py_ssize_t len, int which, const char *codec)
{
    if (len > PY_SSIZE_T_MAX - GROUP_CHARS) {
        return PyErr_NoMemory();
    }
    const unsigned char *rev = radixly_b85_table(which);
    const Py_ssize_t padding = (GROUP_CHARS - (len % GROUP_CHARS)) % GROUP_CHARS;
    const Py_ssize_t chunks = (len + padding) / GROUP_CHARS;
    PyObject *result = PyBytes_FromStringAndSize(NULL, GROUP_BYTES * chunks);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    /* Whole groups of digits at speed; the group that stops the run, and the padded tail, one digit at a
     * time.
     */
    const Py_ssize_t consumed = radixly_b85_groups(data, len, out, rev, 0);
    for (Py_ssize_t chunk = consumed / GROUP_CHARS; chunk < chunks; chunk++) {
        const Py_ssize_t start = GROUP_CHARS * chunk;
        uint64_t acc = 0;
        for (Py_ssize_t j = 0; j < GROUP_CHARS; j++) {
            const Py_ssize_t position = start + j;
            const unsigned value = position < len ? rev[data[position]] : TOP_DIGIT;
            if (value == RADIXLY_B85_INVALID) {
                Py_DECREF(result);
                PyObject *context = PyObject_CallFunction(
                    PyExc_TypeError, "s", "unsupported operand type(s) for +: 'int' and 'NoneType'");
                return raise_decode_error("bad %s character at position %zd", position, codec, context);
            }
            acc = (acc * BASE) + value;
        }
        if (acc > WORD_MAX) {
            Py_DECREF(result);
            PyObject *context = radixly_struct_error("'I' format requires 0 <= number <= 4294967295");
            return raise_decode_error("%s overflow in hunk starting at byte %zd", start, codec, context);
        }
        radixly_b85_put_word(out + (GROUP_BYTES * chunk), (uint32_t)acc, GROUP_BYTES);
    }
    const Py_ssize_t out_len = Py_MAX(0, (GROUP_BYTES * chunks) - padding);
    return radixly_compat_finish(result, out_len);
}

/* The stdlib's b85encode and z85encode: memoryview(b).tobytes() for the input, no folding. */
static PyObject *
encode_85(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames, int which,
          const char *param, int with_pad)
{
    PyObject *arg = NULL;
    PyObject *pad = NULL;
    radixly_param params[] = {{param, &arg}, {"pad", &pad}};
    const Py_ssize_t num_params = with_pad ? 2 : 1;
    if (radixly_bind_args(function, args, nargs, kwnames, params, num_params, 1, num_params) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_buffer_input(arg, &source) < 0) {
        return NULL;
    }
    PyObject *result = radixly_85_encode(source.data, source.len, which, pad, 0, NULL);
    radixly_compat_input_release(&source);
    return result;
}

const char radixly_b85encode_doc[] =
    PyDoc_STR("b85encode($module, /, b, pad=False)\n"
              "--\n"
              "\n"
              "Encode bytes-like object b in base85 format and return a bytes object.\n"
              "\n"
              "The input is padded with b'\\0' so its length is a multiple of 4\n"
              "bytes before encoding.  If pad is true, all the resulting\n"
              "characters are retained in the output, which will always be a\n"
              "multiple of 5 bytes.");
PyObject *
radixly_b85encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return encode_85("b85encode", args, nargs, kwnames, RADIXLY_B85_STD, "b", 1);
}

const char radixly_b85decode_doc[] =
    PyDoc_STR("b85decode($module, /, b)\n"
              "--\n"
              "\n"
              "Decode the base85-encoded bytes-like object or ASCII string b\n"
              "\n"
              "The result is returned as a bytes object.");
PyObject *
radixly_b85decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    radixly_param params[] = {{"b", &arg}};
    if (radixly_bind_args("b85decode", args, nargs, kwnames, params, 1, 1, 1) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    PyObject *result = radixly_85_decode(source.data, source.len, RADIXLY_B85_STD, "base85");
    radixly_compat_input_release(&source);
    return result;
}

const char radixly_z85encode_doc[] =
    PyDoc_STR("z85encode($module, /, s)\n"
              "--\n"
              "\n"
              "Encode bytes-like object b in z85 format and return a bytes object.");
PyObject *
radixly_z85encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return encode_85("z85encode", args, nargs, kwnames, RADIXLY_B85_Z85, "s", 0);
}

const char radixly_z85decode_doc[] = PyDoc_STR("z85decode($module, /, s)\n"
                                               "--\n"
                                               "\n"
                                               "Decode the z85-encoded bytes-like object or ASCII string b\n"
                                               "\n"
                                               "The result is returned as a bytes object.");
PyObject *
radixly_z85decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    radixly_param params[] = {{"s", &arg}};
    if (radixly_bind_args("z85decode", args, nargs, kwnames, params, 1, 1, 1) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    /* The stdlib decodes as base85 and rewords the ValueError with `from None`, the base85 one as context. */
    PyObject *result = radixly_85_decode(source.data, source.len, RADIXLY_B85_Z85, "base85");
    radixly_compat_input_release(&source);
    if (result != NULL || !PyErr_ExceptionMatches(PyExc_ValueError)) {
        return result;
    }
    PyObject *inner = radixly_compat_take_raised();
    PyObject *text = PyObject_Str(inner);
    PyObject *message = text == NULL ? NULL : PyObject_CallMethod(text, "replace", "ss", "base85", "z85");
    Py_XDECREF(text);
    return radixly_raise_from(PyExc_ValueError, message, inner);
}

/* Python 3.15 made the 85 pair shells over binascii.b2a_base85 and a2b_base85. */

size_t
radixly_b85_bound(Py_ssize_t len, size_t wrapcol, int pad, size_t frame)
{
    size_t out_len = ((((size_t)len + GROUP_BYTES - 1U) / GROUP_BYTES) * GROUP_CHARS) + frame;
    if (pad == 0 && (len % GROUP_BYTES) != 0) {
        out_len -= (size_t)(GROUP_BYTES - (len % GROUP_BYTES));
    }
    if (wrapcol != 0 && out_len != 0 && out_len <= (size_t)PY_SSIZE_T_MAX) {
        out_len += (out_len - 1U) / wrapcol;
    }
    return out_len;
}

/* binascii.b2a_base85: the whole words, then the tail as five digits or its bytes plus one. */
static PyObject *
b2a_base85(const unsigned char *data, Py_ssize_t len, int pad, size_t wrapcol, int which)
{
    if (wrapcol != 0) {
        /* Each line should encode a whole number of bytes. */
        wrapcol = wrapcol < GROUP_CHARS ? GROUP_CHARS : wrapcol / GROUP_CHARS * GROUP_CHARS;
    }
    const size_t out_len = radixly_b85_bound(len, wrapcol, pad, 0);
    if (out_len > (size_t)PY_SSIZE_T_MAX) {
        return radixly_binascii_error("Too much data for Base85");
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    const Py_ssize_t whole = radixly_b85_fill(data, len, start, which);
    unsigned char *out = start + ((whole / GROUP_BYTES) * GROUP_CHARS);
    if (whole < len) {
        unsigned char digits[GROUP_CHARS];
        radixly_b85_digits(radixly_b85_word(data + whole, len - whole), digits, which);
        const Py_ssize_t group_len = pad != 0 ? GROUP_CHARS : len - whole + 1;
        memcpy(out, digits, (size_t)group_len);
        out += group_len;
    }
    if (wrapcol != 0 && out_len != 0) {
        out = start + radixly_compat_wraplines(start, out - start, wrapcol);
    }
    return radixly_compat_finish(result, out - start);
}

int
radixly_b85_chunk_length(Py_ssize_t len)
{
    return len < 1 ? GROUP_BYTES - 1 + (int)len : GROUP_BYTES;
}

int
radixly_b85_take_digit(uint32_t *leftchar, int *group_pos, unsigned digit)
{
    if (*group_pos == GROUP_CHARS - 1 &&
        (*leftchar > UINT32_MAX / BASE || *leftchar * BASE > UINT32_MAX - digit)) {
        return 1;
    }
    *leftchar = (*leftchar * BASE) + digit;
    (*group_pos)++;
    return 0;
}

/* binascii.a2b_base85: whole groups of digits at speed, everything else one character at a time, the input
 * padded with the top digit to a whole last group. */
static PyObject *
a2b_base85(const unsigned char *data, Py_ssize_t len, int which, const unsigned char *ignore,
           Py_ssize_t ignore_len, int canonical)
{
    const unsigned char *rev = radixly_b85_table(which);
    radixly_ignore_set skip;
    radixly_ignore_set_init(&skip, ignore, ignore_len);
    PyObject *result = PyBytes_FromStringAndSize(
        NULL, (Py_ssize_t)((((size_t)len + GROUP_CHARS - 1U) / GROUP_CHARS) * GROUP_BYTES));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    unsigned char *out = start;
    uint32_t leftchar = 0;
    int group_pos = 0;
    const Py_ssize_t total = len;
    for (; len > 0 || group_pos != 0; len--, data++) {
        if (group_pos == 0 && len > 0) {
            const Py_ssize_t consumed = radixly_b85_groups(data, len, out, rev, 0);
            data += consumed;
            len -= consumed;
            out += (consumed / GROUP_CHARS) * GROUP_BYTES;
            if (len == 0) {
                break;
            }
        }
        unsigned char this_ch = 0;
        unsigned digit = TOP_DIGIT; /* the padding digit once the input is spent */
        if (len > 0) {
            this_ch = *data;
            digit = rev[this_ch];
        }
        if (digit < BASE) {
            if (radixly_b85_take_digit(&leftchar, &group_pos, digit) != 0) {
                Py_DECREF(result);
                return radixly_binascii_error_format("Base85 overflow in hunk starting at byte %zd",
                                                     (total - len) / GROUP_CHARS * GROUP_CHARS);
            }
        }
        else if (radixly_ignored(&skip, this_ch) == 0) {
            Py_DECREF(result);
            return radixly_binascii_error_format("bad Base85 character at position %zd", total - len);
        }
        if (group_pos != GROUP_CHARS) {
            continue;
        }
        const int chunk_len = radixly_b85_chunk_length(len);
        if (chunk_len == 0) {
            Py_DECREF(result);
            return radixly_binascii_error("Incomplete Base85 group");
        }
        radixly_b85_put_word(out, leftchar, chunk_len);
        out += chunk_len;
        if (canonical != 0 && chunk_len < GROUP_BYTES &&
            radixly_b85_canonical_tail(leftchar, chunk_len) == 0) {
            Py_DECREF(result);
            return radixly_binascii_error("Non-zero padding bits");
        }
        group_pos = 0;
        leftchar = 0;
    }
    return radixly_compat_finish(result, out - start);
}

/* b85encode(b, pad=False, *, wrapcol=0) and z85encode(s, pad=False, *, wrapcol=0). */
static PyObject *
encode_85_py315(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames, int which,
                const char *param)
{
    PyObject *arg = NULL;
    PyObject *pad = NULL;
    PyObject *wrapcol = NULL;
    radixly_param params[] = {{param, &arg}, {"pad", &pad}, {"wrapcol", &wrapcol}};
    if (radixly_bind_args(function, args, nargs, kwnames, params, 3, 1, 2) < 0) {
        return NULL;
    }
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) < 0) {
        return NULL;
    }
    PyObject *result = NULL;
    size_t width = 0;
    const int padding = radixly_compat_truth(pad);
    if (padding >= 0 && (wrapcol == NULL || radixly_compat_size_t(wrapcol, &width) == 0)) {
        result = b2a_base85(view.buf, view.len, padding, width, which);
    }
    PyBuffer_Release(&view);
    return result;
}

/* b85decode(b, *, ignorechars=b'', canonical=False) and z85decode(s, *, ignorechars=b'', canonical=False). */
static PyObject *
decode_85_py315(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames, int which,
                const char *param)
{
    PyObject *arg = NULL;
    PyObject *ignorechars = NULL;
    PyObject *canonical = NULL;
    radixly_param params[] = {{param, &arg}, {"ignorechars", &ignorechars}, {"canonical", &canonical}};
    if (radixly_bind_args(function, args, nargs, kwnames, params, 3, 1, 1) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_ascii_buffer_input(arg, &source) < 0) {
        return NULL;
    }
    PyObject *result = NULL;
    radixly_compat_bytes ignore;
    if (radixly_compat_bytes_init(&ignore, ignorechars, NULL, 0) == 0) {
        const int strict_tail = radixly_compat_truth(canonical);
        if (strict_tail >= 0) {
            result = a2b_base85(source.data, source.len, which, ignore.data, ignore.len, strict_tail);
        }
        radixly_compat_bytes_release(&ignore);
    }
    radixly_compat_input_release(&source);
    return result;
}

const char radixly_b85encode_py315_doc[] =
    PyDoc_STR("b85encode($module, /, b, pad=False, *, wrapcol=0)\n"
              "--\n"
              "\n"
              "Encode bytes-like object b in base85 format and return a bytes object.\n"
              "\n"
              "If wrapcol is non-zero, insert a newline (b'\\n') character after at most\n"
              "every wrapcol characters.\n"
              "\n"
              "The input is padded with b'\\0' so its length is a multiple of 4\n"
              "bytes before encoding.  If pad is true, all the resulting\n"
              "characters are retained in the output, which will always be a\n"
              "multiple of 5 bytes.");
PyObject *
radixly_b85encode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return encode_85_py315("b85encode", args, nargs, kwnames, RADIXLY_B85_STD, "b");
}

const char radixly_b85decode_py315_doc[] =
    PyDoc_STR("b85decode($module, /, b, *, ignorechars=b'', canonical=False)\n"
              "--\n"
              "\n"
              "Decode the base85-encoded bytes-like object or ASCII string b\n"
              "\n"
              "If canonical is true, non-canonical encodings are rejected.\n"
              "\n"
              "The result is returned as a bytes object.");
PyObject *
radixly_b85decode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return decode_85_py315("b85decode", args, nargs, kwnames, RADIXLY_B85_STD, "b");
}

const char radixly_z85encode_py315_doc[] =
    PyDoc_STR("z85encode($module, /, s, pad=False, *, wrapcol=0)\n"
              "--\n"
              "\n"
              "Encode bytes-like object b in z85 format and return a bytes object.\n"
              "\n"
              "If wrapcol is non-zero, insert a newline (b'\\n') character after at most\n"
              "every wrapcol characters.\n"
              "\n"
              "The input is padded with b'\\0' so its length is a multiple of\n"
              "bytes before encoding.  If pad is true, all the resulting\n"
              "characters are retained in the output, which will always be a\n"
              "multiple of 5 bytes, as required by the ZeroMQ standard.");
PyObject *
radixly_z85encode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return encode_85_py315("z85encode", args, nargs, kwnames, RADIXLY_B85_Z85, "s");
}

const char radixly_z85decode_py315_doc[] =
    PyDoc_STR("z85decode($module, /, s, *, ignorechars=b'', canonical=False)\n"
              "--\n"
              "\n"
              "Decode the z85-encoded bytes-like object or ASCII string b\n"
              "\n"
              "If canonical is true, non-canonical encodings are rejected.\n"
              "\n"
              "The result is returned as a bytes object.");
PyObject *
radixly_z85decode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return decode_85_py315("z85decode", args, nargs, kwnames, RADIXLY_B85_Z85, "s");
}
