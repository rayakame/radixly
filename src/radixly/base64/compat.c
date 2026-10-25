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
#include "base64.h"

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 3,
    GROUP_CHARS = 4,
    PAD = '=',
    ALPHABET_SIZE = 64,
    STD_ALPHABET_PREFIX = 62,
    ALTCHARS_LEN = 2,
};

static const unsigned BITS_PER_CHAR = 6U;
static const unsigned CHAR_MASK = 0x3FU;

/* The stdlib's switch on quad_pos, bit for bit: the bits a character leaves for the next output byte. */
static const unsigned LEFT_FOUR_BITS = 0x0FU;
static const unsigned LEFT_TWO_BITS = 0x03U;
static const unsigned SHIFT_TWO = 2U;
static const unsigned SHIFT_FOUR = 4U;

/* The stdlib's BASE64_MAXBIN: b2a_base64 refuses more with binascii.Error, never MemoryError. */
static const Py_ssize_t STDLIB_MAX_INPUT = (PY_SSIZE_T_MAX - 3) / 2;

/* urlsafe_b64decode before 3.15 translates '-_' to '+/' and decodes the standard alphabet, so all four
 * decode. */
static unsigned char URL_LENIENT_REV[RADIXLY_B64_TABLE_SIZE];

/* Which a2b_base64 the running interpreter ships; one wheel per minor version meets every patch release, so
 * the choice is made at import from Py_Version, not at compile time. */
enum a2b_variant {
    A2B_STOPS_AT_PADDING,       /* 3.11, 3.12.0 to 3.12.3: the padding ends the parse */
    A2B_REFUSES_EXCESS_PADDING, /* 3.12.4, 3.13.0 to 3.13.12, 3.14.0 to 3.14.3: plus "Excess padding" */
    A2B_READS_PAST_PADDING,     /* 3.13.13 and 3.14.4 on: padding is skipped, the parse continues */
};
static enum a2b_variant A2B_VARIANT = A2B_READS_PAST_PADDING;

/* The releases where a2b_base64 changed, as Py_Version's minor and micro fields. */
enum {
    MINOR_312 = 12,
    MINOR_313 = 13,
    MINOR_314 = 14,
    EXCESS_CHECK_FROM_312 = 4,
    READS_PAST_FROM_313 = 13,
    READS_PAST_FROM_314 = 4,
};

static enum a2b_variant
a2b_variant_for(unsigned long version)
{
    const unsigned long minor = (version >> (2U * BITS_PER_BYTE)) & BYTE_MASK;
    const unsigned long micro = (version >> BITS_PER_BYTE) & BYTE_MASK;
    if (minor < MINOR_312) {
        return A2B_STOPS_AT_PADDING;
    }
    if (minor == MINOR_312) {
        return micro < EXCESS_CHECK_FROM_312 ? A2B_STOPS_AT_PADDING : A2B_REFUSES_EXCESS_PADDING;
    }
    if (minor == MINOR_313) {
        return micro < READS_PAST_FROM_313 ? A2B_REFUSES_EXCESS_PADDING : A2B_READS_PAST_PADDING;
    }
    if (minor == MINOR_314) {
        return micro < READS_PAST_FROM_314 ? A2B_REFUSES_EXCESS_PADDING : A2B_READS_PAST_PADDING;
    }
    return A2B_READS_PAST_PADDING;
}

int
radixly_b64_compat_exec(PyObject *Py_UNUSED(module))
{
    memcpy(URL_LENIENT_REV, radixly_b64_table(RADIXLY_B64_STD), RADIXLY_B64_TABLE_SIZE);
    const char *url = radixly_b64_alphabet(RADIXLY_B64_URL);
    URL_LENIENT_REV[(unsigned char)url[STD_ALPHABET_PREFIX]] = STD_ALPHABET_PREFIX;
    URL_LENIENT_REV[(unsigned char)url[STD_ALPHABET_PREFIX + 1]] = STD_ALPHABET_PREFIX + 1;
    A2B_VARIANT = a2b_variant_for(Py_Version);
    return 0;
}

static Py_ssize_t
encoded_len(Py_ssize_t num_bytes)
{
    return GROUP_CHARS * ((num_bytes + GROUP_BYTES - 1) / GROUP_BYTES);
}

/* The stdlib's `assert len(altchars) == 2, repr(altchars)` then `bytes.maketrans(b'+/', altchars)`: the
 * length of the object itself, the bytes through the buffer protocol. Fills two bytes; -1 with the stdlib's
 * error. */
static int
encode_altchars(PyObject *altchars, unsigned char *pair)
{
    if (!radixly_compat_optimized()) {
        const Py_ssize_t length = PyObject_Size(altchars);
        if (length < 0) {
            return -1;
        }
        if (length != 2) {
            PyObject *repr = PyObject_Repr(altchars);
            if (repr == NULL) {
                return -1;
            }
            PyErr_SetObject(PyExc_AssertionError, repr);
            Py_DECREF(repr);
            return -1;
        }
    }
    Py_buffer view;
    if (PyObject_GetBuffer(altchars, &view, PyBUF_SIMPLE) == -1) {
        return -1;
    }
    if (view.len != 2) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError, "maketrans arguments must have same length");
        return -1;
    }
    pair[0] = ((const unsigned char *)view.buf)[0];
    pair[1] = ((const unsigned char *)view.buf)[1];
    PyBuffer_Release(&view);
    return 0;
}

/* The stdlib's encoded.translate(): '+' and '/' become the pair, every other byte stays. */
static void
translate_encoded(unsigned char *encoded, Py_ssize_t length, const unsigned char *pair)
{
    for (Py_ssize_t i = 0; i < length; i++) {
        if (encoded[i] == '+') {
            encoded[i] = pair[0];
        }
        else if (encoded[i] == '/') {
            encoded[i] = pair[1];
        }
    }
}

PyObject *
radixly_b64encode_with(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                       int url, int with_altchars)
{
    PyObject *arg = NULL;
    PyObject *altchars = NULL;
    radixly_param params[] = {{"s", &arg}, {"altchars", &altchars}};
    const Py_ssize_t num_params = with_altchars ? 2 : 1;
    if (radixly_bind_args(function, args, nargs, kwnames, params, num_params, 1, num_params) < 0) {
        return NULL;
    }
    /* binascii.b2a_base64's contract: a C-contiguous buffer, str refused, before altchars is looked at. */
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len > STDLIB_MAX_INPUT) {
        PyBuffer_Release(&view);
        return radixly_binascii_error("Too much data for base64 line");
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, encoded_len(view.len));
    if (result == NULL) {
        PyBuffer_Release(&view);
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    radixly_b64_encode(view.buf, view.len, out, url);
    PyBuffer_Release(&view);
    if (altchars != NULL && altchars != Py_None) {
        unsigned char pair[2];
        if (encode_altchars(altchars, pair) < 0) {
            Py_DECREF(result);
            return NULL;
        }
        translate_encoded(out, PyBytes_GET_SIZE(result), pair);
    }
    return result;
}

/* The parse state of the stdlib's a2b_base64 loop. */
typedef struct {
    int quad_pos;
    unsigned char leftchar;
    unsigned char *out;
} a2b_state;

/* One data character into the state: the stdlib's switch on quad_pos. */
static void
take_char(a2b_state *state, unsigned value)
{
    switch (state->quad_pos) {
    case 0:
        state->quad_pos = 1;
        state->leftchar = (unsigned char)value;
        break;
    case 1:
        state->quad_pos = 2;
        *state->out++ = (unsigned char)(((unsigned)state->leftchar << SHIFT_TWO) | (value >> SHIFT_FOUR));
        state->leftchar = (unsigned char)(value & LEFT_FOUR_BITS);
        break;
    case 2:
        state->quad_pos = 3;
        *state->out++ = (unsigned char)(((unsigned)state->leftchar << SHIFT_FOUR) | (value >> SHIFT_TWO));
        state->leftchar = (unsigned char)(value & LEFT_TWO_BITS);
        break;
    default:
        state->quad_pos = 0;
        *state->out++ = (unsigned char)(((unsigned)state->leftchar << BITS_PER_CHAR) | value);
        state->leftchar = 0;
        break;
    }
}

/* binascii's checks after its loop; the count in the message is its arithmetic on bytes written. */
static PyObject *
finish(PyObject *result, const a2b_state *state, const unsigned char *start, int incomplete, int canonical)
{
    if (state->quad_pos == 1) {
        Py_DECREF(result);
        return radixly_binascii_error_format("Invalid base64-encoded string: number of data characters (%zd) "
                                             "cannot be 1 more than a multiple of 4",
                                             ((state->out - start) / GROUP_BYTES * GROUP_CHARS) + 1);
    }
    if (incomplete) {
        Py_DECREF(result);
        return radixly_binascii_error("Incorrect padding");
    }
    if (canonical != 0 && state->leftchar != 0) {
        Py_DECREF(result);
        return radixly_binascii_error("Non-zero padding bits");
    }
    return radixly_compat_finish(result, state->out - start);
}

/* A '=' in the stopping variants: -1 with the error, 1 when the padding ends the parse, 0 to carry on. */
static int
pad_stopping(const a2b_state *state, int *pads, Py_ssize_t index, Py_ssize_t length, int strict,
             int excess_check)
{
    if (excess_check && strict && state->quad_pos == 0) {
        radixly_binascii_error("Excess padding not allowed");
        return -1;
    }
    if (state->quad_pos < 2) {
        return 0;
    }
    (*pads)++;
    if (state->quad_pos + *pads < GROUP_CHARS) {
        return 0;
    }
    if (strict && index + 1 < length) {
        radixly_binascii_error("Excess data after padding");
        return -1;
    }
    return 1;
}

/* The state of the stopping variants' parse beyond take_char's. */
typedef struct {
    a2b_state chars;
    int pads;
    int padding_started;
    int strict;
    int excess_check;
    const unsigned char *rev;
    Py_ssize_t length;
} stopping_parse;

/* One character of the stopping variants: 1 to go on, 0 when the padding ends the parse, -1 with the error
 * set.
 */
static int
stopping_step(stopping_parse *parse, Py_ssize_t index, unsigned char this_ch)
{
    const unsigned value = parse->rev[this_ch];
    if (value == RADIXLY_B64_PAD_VALUE) {
        parse->padding_started = 1;
        const int outcome = pad_stopping(&parse->chars, &parse->pads, index, parse->length, parse->strict,
                                         parse->excess_check);
        return outcome < 0 ? -1 : outcome == 0;
    }
    if (value >= ALPHABET_SIZE) {
        if (parse->strict) {
            radixly_binascii_error("Only base64 data is allowed");
            return -1;
        }
        return 1;
    }
    if (parse->strict && parse->padding_started) {
        radixly_binascii_error("Discontinuous padding not allowed");
        return -1;
    }
    parse->pads = 0;
    take_char(&parse->chars, value);
    return 1;
}

/* a2b_base64 as 3.11 to 3.12.3 (stop at padding) and 3.12.4 to 3.13.12 (plus the excess-padding check) had
 * it. */
static PyObject *
a2b_stopping(const unsigned char *rev, const unsigned char *data, Py_ssize_t length, int strict,
             int excess_check)
{
    PyObject *result = PyBytes_FromStringAndSize(NULL, radixly_b64_decode_bound(data, length, rev));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    stopping_parse parse = {{0, 0, start}, 0, 0, strict, excess_check, rev, length};
    if (strict && length > 0 && rev[data[0]] == RADIXLY_B64_PAD_VALUE) {
        Py_DECREF(result);
        return radixly_binascii_error("Leading padding not allowed");
    }
    Py_ssize_t index = 0;
    while (index < length) {
        if (parse.chars.quad_pos == 0 && parse.pads == 0 && !parse.padding_started) {
            const Py_ssize_t consumed = radixly_b64_quads(data + index, length - index, parse.chars.out, rev);
            index += consumed;
            parse.chars.out += (consumed / GROUP_CHARS) * GROUP_BYTES;
            if (index >= length) {
                break;
            }
        }
        const int outcome = stopping_step(&parse, index, data[index]);
        if (outcome < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (outcome == 0) {
            /* The stdlib's goto done, past the checks below. */
            return radixly_compat_finish(result, parse.chars.out - start);
        }
        index++;
    }
    return finish(result, &parse.chars, start, parse.chars.quad_pos != 0, 0);
}

/* The stdlib's pad counter is an int that wraps under CPython's -fwrapv once the lenient reading-past loop
 * has counted 2**31 pad bytes; unsigned arithmetic gives the same wrap without the UB. */
static unsigned
wrapping_add(unsigned first, unsigned second)
{
    return first + second;
}

/* The state the reading-past parse carries beyond take_char's. */
typedef struct {
    a2b_state chars;
    unsigned pads;
    int strict;
    int padded;
    const unsigned char *rev;
    radixly_ignore_set skip;
} a2b_parse;

/* A '=': 1 to go on with the next character, 0 to stop reading (the one-extra error follows), -1 with the
 * error set. */
static int
pad_reading_past(a2b_parse *parse, const unsigned char *start)
{
    const a2b_state *state = &parse->chars;
    parse->pads = wrapping_add(parse->pads, 1U);
    if (state->quad_pos >= 2 && wrapping_add((unsigned)state->quad_pos, parse->pads) <= GROUP_CHARS) {
        return 1;
    }
    if (parse->strict == 0 || radixly_ignored(&parse->skip, PAD) != 0) {
        return 1;
    }
    if (state->quad_pos == 1) {
        return 0;
    }
    radixly_binascii_error(state->quad_pos == 0 && state->out == start ? "Leading padding not allowed"
                                                                       : "Excess padding not allowed");
    return -1;
}

/* One character of binascii's slow path: 1 to go on, 0 to leave the loop, -1 with the error set. */
static int
a2b_step(a2b_parse *parse, unsigned char this_ch, const unsigned char *start)
{
    const unsigned value = parse->rev[this_ch];
    if (parse->padded != 0 && value == RADIXLY_B64_PAD_VALUE) {
        return pad_reading_past(parse, start);
    }
    if (value >= ALPHABET_SIZE) {
        if (parse->strict != 0 && radixly_ignored(&parse->skip, this_ch) == 0) {
            radixly_binascii_error(this_ch == PAD ? "Padding not allowed" : "Only base64 data is allowed");
            return -1;
        }
        return 1;
    }
    if (parse->pads != 0 && parse->strict != 0 && radixly_ignored(&parse->skip, PAD) == 0) {
        radixly_binascii_error(wrapping_add((unsigned)parse->chars.quad_pos, parse->pads) == GROUP_CHARS
                                   ? "Excess data after padding"
                                   : "Discontinuous padding not allowed");
        return -1;
    }
    parse->pads = 0;
    take_char(&parse->chars, value);
    return 1;
}

/* binascii.a2b_base64 as 3.13.13, 3.14.4 and 3.15 read it: padding is skipped and the parse goes on. The
 * keywords 3.15 added default to padded, nothing ignored and pad bits unchecked. Whole quads of alphabet
 * characters go through the fast path, everything else one character at a time. */
static PyObject *
a2b_base64(const unsigned char *data, Py_ssize_t len, int strict, int padded, const unsigned char *rev,
           const unsigned char *ignore, Py_ssize_t ignore_len, int canonical)
{
    PyObject *result = PyBytes_FromStringAndSize(NULL, radixly_b64_decode_bound(data, len, rev));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    a2b_parse parse = {{0, 0, start}, 0, strict, padded, rev, {NULL, 0, {0}}};
    radixly_ignore_set_init(&parse.skip, ignore, strict != 0 ? ignore_len : 0);
    Py_ssize_t index = 0;
    while (index < len) {
        if (parse.chars.quad_pos == 0 && parse.pads == 0) {
            const Py_ssize_t consumed = radixly_b64_quads(data + index, len - index, parse.chars.out, rev);
            index += consumed;
            parse.chars.out += (consumed / GROUP_CHARS) * GROUP_BYTES;
            if (index >= len) {
                break;
            }
        }
        const int outcome = a2b_step(&parse, data[index++], start);
        if (outcome < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (outcome == 0) {
            break;
        }
    }
    const int incomplete = padded != 0 && parse.chars.quad_pos != 0 &&
                           wrapping_add((unsigned)parse.chars.quad_pos, parse.pads) < GROUP_CHARS;
    return finish(result, &parse.chars, start, incomplete, canonical);
}

/* A flag whose truth is read without running code: absent, a bool or an exact int. The stdlib reads its flags
 * while binascii holds the translated copy of s, not s itself, so only a flag that could edit s earns the
 * copy; every other call decodes s in place through a table with the altchars folded in. */
static int
inert_flag(PyObject *flag)
{
    return flag == NULL || !radixly_compat_specified(flag) || PyBool_Check(flag) || PyLong_CheckExact(flag);
}

/* A faithful port of binascii.a2b_base64 on translated bytes: the bytes result, or NULL with binascii.Error.
 */
static PyObject *
stdlib_a2b(const unsigned char *rev, const unsigned char *data, Py_ssize_t length, int strict)
{
    switch (A2B_VARIANT) {
    case A2B_STOPS_AT_PADDING:
        return a2b_stopping(rev, data, length, strict, 0);
    case A2B_REFUSES_EXCESS_PADDING:
        return a2b_stopping(rev, data, length, strict, 1);
    default:
        return a2b_base64(data, length, strict, 1, rev, NULL, 0, 0);
    }
}

/* The stdlib's altchars: _bytes_from_decode_data, the length assert, then translate(maketrans(altchars,
 * b'+/')) folded into the reverse table, later entries winning like maketrans. */
static int
decode_altchars(PyObject *altchars, unsigned char *rev)
{
    radixly_compat_input pair;
    if (radixly_compat_decode_input(altchars, &pair) < 0) {
        return -1;
    }
    if (radixly_compat_check_length(&pair, 2) < 0) {
        radixly_compat_input_release(&pair);
        return -1;
    }
    memcpy(rev, radixly_b64_table(RADIXLY_B64_STD), RADIXLY_B64_TABLE_SIZE);
    rev[pair.data[0]] = STD_ALPHABET_PREFIX;
    rev[pair.data[1]] = STD_ALPHABET_PREFIX + 1;
    radixly_compat_input_release(&pair);
    return 0;
}

/* The stdlib's strict_mode parameter: 3.11 declares it bool(accept={int}), so __index__ decides and a
 * plain object is a TypeError; 3.12 on take any object's truth. Returns -1 with an exception on failure. */
static int
strict_mode_flag(PyObject *validate)
{
#if PY_VERSION_HEX < 0x030C0000
    if (validate == NULL) {
        return 0;
    }
    const int value = _PyLong_AsInt(validate);
    if (value == -1 && PyErr_Occurred()) {
        return -1;
    }
    return value != 0;
#else
    return radixly_compat_truth(validate);
#endif
}

/* A faithful port of the stdlib's b64decode, standard_b64decode and urlsafe_b64decode. */
PyObject *
radixly_b64decode_with(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                       int url, int with_options)
{
    PyObject *arg = NULL;
    PyObject *altchars = NULL;
    PyObject *validate = NULL;
    radixly_param params[] = {{"s", &arg}, {"altchars", &altchars}, {"validate", &validate}};
    const Py_ssize_t num_params = with_options ? 3 : 1;
    if (radixly_bind_args(function, args, nargs, kwnames, params, num_params, 1, num_params) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    const unsigned char *rev = url ? URL_LENIENT_REV : radixly_b64_table(RADIXLY_B64_STD);
    unsigned char translated[RADIXLY_B64_TABLE_SIZE];
    PyObject *snapshot = NULL;
    if (altchars != NULL && altchars != Py_None) {
        if (decode_altchars(altchars, translated) < 0) {
            radixly_compat_input_release(&source);
            return NULL;
        }
        rev = translated;
    }
    if (rev == translated && !inert_flag(validate)) {
        snapshot = PyBytes_FromStringAndSize((const char *)source.data, source.len);
        radixly_compat_input_release(&source);
        if (snapshot == NULL) {
            return NULL;
        }
        source.data = (const unsigned char *)PyBytes_AS_STRING(snapshot);
        source.len = PyBytes_GET_SIZE(snapshot);
    }
    /* binascii holds the buffer of s while it reads strict_mode, so a hook that resizes s fails there too. */
    const int strict = strict_mode_flag(validate);
    if (strict < 0) {
        radixly_compat_input_release(&source);
        Py_XDECREF(snapshot);
        return NULL;
    }
    PyObject *result = stdlib_a2b(rev, source.data, source.len, strict);
    radixly_compat_input_release(&source);
    Py_XDECREF(snapshot);
    return result;
}

const char radixly_a2b_base64_variant_doc[] =
    PyDoc_STR("a2b_base64_variant($module, hexversion, /)\n"
              "--\n"
              "\n"
              "Which binascii.a2b_base64 the CPython release ``hexversion`` ships, as the\n"
              "drop-in's ``b64decode`` selects it at import: 0 stops at the padding, 1 adds\n"
              "the excess-padding check, 2 reads past the padding. For the test suite.");
PyObject *
radixly_a2b_base64_variant(PyObject *Py_UNUSED(self), PyObject *arg)
{
    const unsigned long version = PyLong_AsUnsignedLong(arg);
    if (version == (unsigned long)-1 && PyErr_Occurred()) {
        return NULL;
    }
    return PyLong_FromLong((long)a2b_variant_for(version));
}

/* The legacy file functions: 76-character lines, so 57 bytes of payload each. */
enum {
    MAXLINESIZE = 76,
    MAXBINSIZE = (MAXLINESIZE / GROUP_CHARS) * GROUP_BYTES,
};

/* binascii.b2a_base64 with its courtesy newline. */
static PyObject *
b2a_line(const unsigned char *data, Py_ssize_t len)
{
    if (len > STDLIB_MAX_INPUT) {
        return radixly_binascii_error("Too much data for base64 line");
    }
    const Py_ssize_t chars = encoded_len(len);
    PyObject *result = PyBytes_FromStringAndSize(NULL, chars + 1);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    radixly_b64_encode(data, len, out, RADIXLY_B64_STD);
    out[chars] = '\n';
    return result;
}

/* The stdlib's _input_type_check: memoryview(s), single-byte elements, one dimension. Fills length. */
static int
input_type_check(PyObject *arg, Py_ssize_t *length)
{
    PyObject *view = PyMemoryView_FromObject(arg);
    if (view == NULL) {
        if (!PyErr_ExceptionMatches(PyExc_TypeError)) {
            return -1; /* the stdlib catches only memoryview's TypeError */
        }
        PyObject *cause = radixly_compat_take_raised();
        PyObject *name = radixly_compat_class_name(arg);
        if (name == NULL) {
            /* The stdlib is still inside `except TypeError as err`, so that error is this one's context. */
            radixly_compat_set_context(cause);
            return -1;
        }
        PyObject *message = PyUnicode_FromFormat("expected bytes-like object, not %S", name);
        Py_DECREF(name);
        radixly_raise_from_cause(PyExc_TypeError, message, cause);
        return -1;
    }
    const Py_buffer *buffer = PyMemoryView_GET_BUFFER(view);
    const char *format = buffer->format == NULL ? "B" : buffer->format;
    const int single_byte =
        format[0] != '\0' && format[1] == '\0' && (format[0] == 'c' || format[0] == 'b' || format[0] == 'B');
    if (single_byte && buffer->ndim == 1) {
        *length = buffer->len; /* the stdlib names __class__ only when it raises, so nothing else is read */
        Py_DECREF(view);
        return 0;
    }
    /* format points into the view's buffer, so the message is built before the view goes. */
    PyObject *name = radixly_compat_class_name(arg);
    if (name != NULL) {
        if (!single_byte) {
            PyErr_Format(PyExc_TypeError, "expected single byte elements, not '%s' from %S", format, name);
        }
        else {
            PyErr_Format(PyExc_TypeError, "expected 1-D data, not %d-D data from %S", buffer->ndim, name);
        }
        Py_DECREF(name);
    }
    Py_DECREF(view);
    return -1;
}

const char radixly_encodebytes_doc[] =
    PyDoc_STR("encodebytes($module, /, s)\n"
              "--\n"
              "\n"
              "Encode a bytestring into a bytes object containing multiple lines\n"
              "of base-64 data.");
/* The lines of a contiguous buffer in one allocation, for the bytes and bytearray the stdlib slices into
 * identical copies. */
static PyObject *
encodebytes_contiguous(PyObject *arg, Py_ssize_t length)
{
    if (length == 0) {
        return PyBytes_FromStringAndSize("", 0); /* no chunk, so the stdlib never reaches b2a_base64 */
    }
    if (length > PY_SSIZE_T_MAX / 2) {
        return PyErr_NoMemory(); /* the lines are 77 characters per 57 bytes, comfortably under twice */
    }
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    const Py_ssize_t chunks = (view.len + MAXBINSIZE - 1) / MAXBINSIZE;
    const Py_ssize_t tail = view.len - (MAXBINSIZE * (chunks - 1));
    PyObject *result =
        PyBytes_FromStringAndSize(NULL, ((MAXLINESIZE + 1) * (chunks - 1)) + encoded_len(tail) + 1);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return NULL;
    }
    const unsigned char *data = view.buf;
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    for (Py_ssize_t chunk = 0; chunk < chunks; chunk++) {
        const Py_ssize_t offset = MAXBINSIZE * chunk;
        const Py_ssize_t count = Py_MIN(MAXBINSIZE, view.len - offset);
        radixly_b64_encode(data + offset, count, out, RADIXLY_B64_STD);
        out += encoded_len(count);
        *out++ = '\n';
    }
    PyBuffer_Release(&view);
    return result;
}

/* One encoded line from s[start:stop], the slice and its buffer the stdlib's own. */
static PyObject *
encode_slice(PyObject *arg, Py_ssize_t start, Py_ssize_t stop)
{
    /* PySlice_New increfs its bounds and reads a NULL as None, so both are owned here and checked first. */
    PyObject *first = PyLong_FromSsize_t(start);
    PyObject *last = PyLong_FromSsize_t(stop);
    PyObject *bounds = first == NULL || last == NULL ? NULL : PySlice_New(first, last, NULL);
    Py_XDECREF(first);
    Py_XDECREF(last);
    if (bounds == NULL) {
        return NULL;
    }
    PyObject *chunk = PyObject_GetItem(arg, bounds);
    Py_DECREF(bounds);
    if (chunk == NULL) {
        return NULL;
    }
    Py_buffer view;
    if (PyObject_GetBuffer(chunk, &view, PyBUF_SIMPLE) == -1) {
        Py_DECREF(chunk);
        return NULL;
    }
    PyObject *line = b2a_line(view.buf, view.len);
    PyBuffer_Release(&view);
    Py_DECREF(chunk);
    return line;
}

/* The stdlib's own loop: `for i in range(0, len(s), MAXBINSIZE):
 * pieces.append(b2a_base64(s[i:i+MAXBINSIZE]))`, so an object whose length or slicing disagrees with its
 * buffer is treated as the stdlib treats it. */
static PyObject *
encodebytes_by_slices(PyObject *arg)
{
    const Py_ssize_t length = PyObject_Length(arg);
    if (length < 0) {
        return NULL;
    }
    PyObject *pieces = PyList_New(0);
    if (pieces == NULL) {
        return NULL;
    }
    for (Py_ssize_t start = 0; start < length; start += MAXBINSIZE) {
        PyObject *line = encode_slice(arg, start, start + MAXBINSIZE);
        if (line == NULL || PyList_Append(pieces, line) < 0) {
            Py_XDECREF(line);
            Py_DECREF(pieces);
            return NULL;
        }
        Py_DECREF(line);
    }
    PyObject *empty = PyBytes_FromStringAndSize("", 0);
    if (empty == NULL) {
        Py_DECREF(pieces);
        return NULL;
    }
    PyObject *result = PyObject_CallMethod(empty, "join", "O", pieces);
    Py_DECREF(empty);
    Py_DECREF(pieces);
    return result;
}

PyObject *
radixly_encodebytes(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    radixly_param params[] = {{"s", &arg}};
    if (radixly_bind_args("encodebytes", args, nargs, kwnames, params, 1, 1, 1) < 0) {
        return NULL;
    }
    Py_ssize_t length = 0;
    if (input_type_check(arg, &length) < 0) {
        return NULL;
    }
    if (PyBytes_CheckExact(arg) || PyByteArray_CheckExact(arg)) {
        return encodebytes_contiguous(arg,
                                      length); /* len(s) is the buffer's own length, every slice a copy */
    }
    return encodebytes_by_slices(arg);
}

const char radixly_decodebytes_doc[] = PyDoc_STR("decodebytes($module, /, s)\n"
                                                 "--\n"
                                                 "\n"
                                                 "Decode a bytestring of base-64 data into a bytes object.");
PyObject *
radixly_decodebytes(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    radixly_param params[] = {{"s", &arg}};
    if (radixly_bind_args("decodebytes", args, nargs, kwnames, params, 1, 1, 1) < 0) {
        return NULL;
    }
    Py_ssize_t length = 0;
    if (input_type_check(arg, &length) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_ascii_buffer_input(arg, &source) < 0) {
        return NULL;
    }
    PyObject *result = stdlib_a2b(radixly_b64_table(RADIXLY_B64_STD), source.data, source.len, 0);
    radixly_compat_input_release(&source);
    return result;
}

/* The stdlib's `line = b2a_base64(s); output.write(line)`, with s whatever read returned. */
static int
write_encoded_line(PyObject *output, PyObject *chunk)
{
    Py_buffer view;
    if (PyObject_GetBuffer(chunk, &view, PyBUF_SIMPLE) == -1) {
        return -1;
    }
    PyObject *line = b2a_line(view.buf, view.len);
    PyBuffer_Release(&view);
    if (line == NULL) {
        return -1;
    }
    PyObject *written = PyObject_CallMethod(output, "write", "O", line);
    Py_DECREF(line);
    Py_XDECREF(written);
    return written == NULL ? -1 : 0;
}

/* One read of at most count bytes, or NULL with the exception set. */
static PyObject *
read_chunk(PyObject *input, Py_ssize_t count)
{
    return PyObject_CallMethod(input, "read", "n", count);
}

/* A short read is topped up, so every line but the last carries its full 57 bytes; -1 clears the chunk. */
static int
top_up(PyObject *input, PyObject **chunk)
{
    for (;;) {
        const Py_ssize_t have = PyObject_Length(*chunk);
        if (have < 0) {
            return -1;
        }
        if (have >= MAXBINSIZE) {
            return 0;
        }
        /* The stdlib's condition and its read size are two separate len(s) calls, so this asks twice too. */
        const Py_ssize_t wanted = PyObject_Length(*chunk);
        if (wanted < 0) {
            return -1;
        }
        PyObject *extra = read_chunk(input, MAXBINSIZE - wanted);
        if (extra == NULL) {
            return -1;
        }
        const int again = PyObject_IsTrue(extra);
        if (again <= 0) {
            Py_DECREF(extra);
            return again;
        }
        PyObject *joined = PyNumber_InPlaceAdd(*chunk, extra);
        Py_DECREF(extra);
        Py_DECREF(*chunk);
        *chunk = joined;
        if (joined == NULL) {
            return -1;
        }
    }
}

const char radixly_encode_doc[] = PyDoc_STR("encode($module, /, input, output)\n"
                                            "--\n"
                                            "\n"
                                            "Encode a file; input and output are binary files.");
PyObject *
radixly_encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *input = NULL;
    PyObject *output = NULL;
    radixly_param params[] = {{"input", &input}, {"output", &output}};
    if (radixly_bind_args("encode", args, nargs, kwnames, params, 2, 2, 2) < 0) {
        return NULL;
    }
    for (;;) {
        PyObject *chunk = read_chunk(input, MAXBINSIZE);
        if (chunk == NULL) {
            return NULL;
        }
        const int more = PyObject_IsTrue(chunk);
        if (more <= 0) {
            Py_DECREF(chunk);
            return more < 0 ? NULL : Py_NewRef(Py_None);
        }
        if (top_up(input, &chunk) < 0) {
            Py_XDECREF(chunk);
            return NULL;
        }
        const int failed = write_encoded_line(output, chunk) < 0;
        Py_DECREF(chunk);
        if (failed) {
            return NULL;
        }
    }
}

const char radixly_decode_doc[] = PyDoc_STR("decode($module, /, input, output)\n"
                                            "--\n"
                                            "\n"
                                            "Decode a file; input and output are binary files.");
PyObject *
radixly_decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *input = NULL;
    PyObject *output = NULL;
    radixly_param params[] = {{"input", &input}, {"output", &output}};
    if (radixly_bind_args("decode", args, nargs, kwnames, params, 2, 2, 2) < 0) {
        return NULL;
    }
    for (;;) {
        PyObject *line = PyObject_CallMethod(input, "readline", NULL);
        if (line == NULL) {
            return NULL;
        }
        const int more = PyObject_IsTrue(line);
        if (more <= 0) {
            Py_DECREF(line);
            return more < 0 ? NULL : Py_NewRef(Py_None);
        }
        radixly_compat_input source;
        if (radixly_compat_ascii_buffer_input(line, &source) < 0) {
            Py_DECREF(line);
            return NULL;
        }
        PyObject *decoded = stdlib_a2b(radixly_b64_table(RADIXLY_B64_STD), source.data, source.len, 0);
        radixly_compat_input_release(&source);
        Py_DECREF(line);
        if (decoded == NULL) {
            return NULL;
        }
        PyObject *written = PyObject_CallMethod(output, "write", "O", decoded);
        Py_DECREF(decoded);
        Py_XDECREF(written);
        if (written == NULL) {
            return NULL;
        }
    }
}

const char radixly_b64encode_doc[] =
    PyDoc_STR("b64encode($module, /, s, altchars=None)\n"
              "--\n"
              "\n"
              "Encode the bytes-like object s using Base64 and return a bytes object.\n"
              "\n"
              "Optional altchars should be a byte string of length 2 which specifies an\n"
              "alternative alphabet for the '+' and '/' characters.  This allows an\n"
              "application to e.g. generate url or filesystem safe Base64 strings.");
PyObject *
radixly_b64encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b64encode_with("b64encode", args, nargs, kwnames, 0, 1);
}

const char radixly_b64decode_doc[] =
    PyDoc_STR("b64decode($module, /, s, altchars=None, validate=False)\n"
              "--\n"
              "\n"
              "Decode the Base64 encoded bytes-like object or ASCII string s.\n"
              "\n"
              "Optional altchars must be a bytes-like object or ASCII string of length 2\n"
              "which specifies the alternative alphabet used instead of the '+' and '/'\n"
              "characters.\n"
              "\n"
              "The result is returned as a bytes object.  A binascii.Error is raised if\n"
              "s is incorrectly padded.\n"
              "\n"
              "If validate is False (the default), characters that are neither in the\n"
              "normal base-64 alphabet nor the alternative alphabet are discarded prior\n"
              "to the padding check.  If validate is True, these non-alphabet characters\n"
              "in the input result in a binascii.Error.\n"
              "For more information about the strict base64 check, see:\n"
              "\n"
              "https://docs.python.org/3.11/library/binascii.html#binascii.a2b_base64");
PyObject *
radixly_b64decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b64decode_with("b64decode", args, nargs, kwnames, 0, 1);
}

const char radixly_standard_b64encode_doc[] =
    PyDoc_STR("standard_b64encode($module, /, s)\n"
              "--\n"
              "\n"
              "Encode bytes-like object s using the standard Base64 alphabet.\n"
              "\n"
              "The result is returned as a bytes object.");
PyObject *
radixly_standard_b64encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs,
                           PyObject *kwnames)
{
    return radixly_b64encode_with("standard_b64encode", args, nargs, kwnames, 0, 0);
}

const char radixly_standard_b64decode_doc[] =
    PyDoc_STR("standard_b64decode($module, /, s)\n"
              "--\n"
              "\n"
              "Decode bytes encoded with the standard Base64 alphabet.\n"
              "\n"
              "Argument s is a bytes-like object or ASCII string to decode.  The result\n"
              "is returned as a bytes object.  A binascii.Error is raised if the input\n"
              "is incorrectly padded.  Characters that are not in the standard alphabet\n"
              "are discarded prior to the padding check.");
PyObject *
radixly_standard_b64decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs,
                           PyObject *kwnames)
{
    return radixly_b64decode_with("standard_b64decode", args, nargs, kwnames, 0, 0);
}

/* Python 3.15 made the base64 family shells over binascii.b2a_base64 and a2b_base64, which grew padded,
 * wrapcol, ignorechars, canonical and an alphabet of their own. */

/* The encoding under any 64-byte alphabet: the engine's tables where the alphabet is one of its own or shares
 * the standard prefix, a plain six-bit lookup otherwise (an alphabet a bytes subclass's __radd__ made up). */
static unsigned char *
encode_alphabet(const unsigned char *data, Py_ssize_t len, unsigned char *out, const unsigned char *alphabet)
{
    const int which = memcmp(alphabet, radixly_b64_alphabet(RADIXLY_B64_URL), ALPHABET_SIZE) == 0
                          ? RADIXLY_B64_URL
                          : RADIXLY_B64_STD;
    const unsigned char *own = (const unsigned char *)radixly_b64_alphabet(which);
    if (memcmp(alphabet, own, STD_ALPHABET_PREFIX) != 0) {
        unsigned char *cursor = out;
        for (Py_ssize_t offset = 0; offset + GROUP_BYTES <= len;
             offset += GROUP_BYTES, cursor += GROUP_CHARS) {
            const unsigned group = ((unsigned)data[offset] << (2U * BITS_PER_BYTE)) |
                                   ((unsigned)data[offset + 1] << BITS_PER_BYTE) | data[offset + 2];
            cursor[0] = alphabet[(group >> (3U * BITS_PER_CHAR)) & CHAR_MASK];
            cursor[1] = alphabet[(group >> (2U * BITS_PER_CHAR)) & CHAR_MASK];
            cursor[2] = alphabet[(group >> BITS_PER_CHAR) & CHAR_MASK];
            cursor[3] = alphabet[group & CHAR_MASK];
        }
        const Py_ssize_t whole = len - (len % GROUP_BYTES);
        if (whole < len) {
            unsigned char tail[GROUP_CHARS];
            const int chars = radixly_b64_tail(data + whole, len - whole, tail, RADIXLY_B64_STD);
            for (int i = 0; i < chars; i++) {
                cursor[i] = alphabet[radixly_b64_table(RADIXLY_B64_STD)[tail[i]]];
            }
            cursor += chars;
        }
        return cursor;
    }
    const Py_ssize_t whole = radixly_b64_fill(data, len, out, which);
    unsigned char *cursor = out + ((whole / GROUP_BYTES) * GROUP_CHARS);
    cursor += radixly_b64_tail(data + whole, len - whole, cursor, which);
    if (memcmp(alphabet + STD_ALPHABET_PREFIX, own + STD_ALPHABET_PREFIX, ALTCHARS_LEN) != 0) {
        for (unsigned char *at = out; at < cursor; at++) {
            if (*at == own[STD_ALPHABET_PREFIX]) {
                *at = alphabet[STD_ALPHABET_PREFIX];
            }
            else if (*at == own[STD_ALPHABET_PREFIX + 1]) {
                *at = alphabet[STD_ALPHABET_PREFIX + 1];
            }
        }
    }
    return cursor;
}

/* binascii.b2a_base64 as 3.15 has it: padded, wrapcol, newline and alphabet included. */
static PyObject *
b2a_base64(const unsigned char *data, Py_ssize_t len, int padded, size_t wrapcol, int newline,
           const unsigned char *alphabet)
{
    size_t out_len = (((size_t)len + GROUP_BYTES - 1U) / GROUP_BYTES) * GROUP_CHARS;
    unsigned pads = (unsigned)((GROUP_BYTES - (len % GROUP_BYTES)) % GROUP_BYTES) * GROUP_CHARS / GROUP_BYTES;
    if (padded == 0) {
        out_len -= pads;
        pads = 0;
    }
    if (wrapcol != 0 && out_len != 0) {
        /* Each line should encode a whole number of bytes. */
        wrapcol = wrapcol < GROUP_CHARS ? GROUP_CHARS : wrapcol / GROUP_CHARS * GROUP_CHARS;
        out_len += (out_len - 1U) / wrapcol;
    }
    if (newline != 0) {
        out_len++;
    }
    if (out_len > (size_t)PY_SSIZE_T_MAX) {
        return radixly_binascii_error("Too much data for base64");
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    unsigned char *out = encode_alphabet(data, len, start, alphabet);
    for (; pads != 0; pads--) {
        *out++ = PAD;
    }
    if (wrapcol != 0) {
        out = start + radixly_compat_wraplines(start, out - start, wrapcol);
    }
    if (newline != 0) {
        *out++ = '\n';
    }
    return radixly_compat_finish(result, out - start);
}

/* The stdlib's `if len(altchars) != 2: raise ValueError(f'invalid altchars: {altchars!r}')`. */
static int
check_altchars_py315(PyObject *altchars)
{
    const Py_ssize_t length = PyObject_Size(altchars);
    if (length < 0) {
        return -1;
    }
    if (length != ALTCHARS_LEN) {
        PyErr_Format(PyExc_ValueError, "invalid altchars: %R", altchars);
        return -1;
    }
    return 0;
}

/* binascii.BASE64_ALPHABET[:-2] + altchars, with bytes.__add__'s own type errors. */
static PyObject *
alphabet_with_altchars(PyObject *altchars)
{
    PyObject *prefix = PyBytes_FromStringAndSize(radixly_b64_alphabet(RADIXLY_B64_STD), STD_ALPHABET_PREFIX);
    if (prefix == NULL) {
        return NULL;
    }
    PyObject *alphabet = PyNumber_Add(prefix, altchars);
    Py_DECREF(prefix);
    return alphabet;
}

/* The stdlib's s.translate(bytes.maketrans(pair, b'+/')): the pair mapped back, later maketrans entries
 * winning, or maketrans's ValueError when the pair's buffer is not two bytes. */
static PyObject *
translated_from_pair(const radixly_compat_input *source, PyObject *pair, const unsigned char *into)
{
    Py_buffer view;
    if (PyObject_GetBuffer(pair, &view, PyBUF_SIMPLE) < 0) {
        return NULL;
    }
    if (view.len != ALTCHARS_LEN) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError, "maketrans arguments must have same length");
        return NULL;
    }
    unsigned char table[RADIXLY_B64_TABLE_SIZE];
    for (unsigned code = 0; code < RADIXLY_B64_TABLE_SIZE; code++) {
        table[code] = (unsigned char)code;
    }
    table[((const unsigned char *)view.buf)[0]] = into[0];
    table[((const unsigned char *)view.buf)[1]] = into[1];
    PyBuffer_Release(&view);
    PyObject *copy = PyBytes_FromStringAndSize(NULL, source->len);
    if (copy == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(copy);
    for (Py_ssize_t i = 0; i < source->len; i++) {
        out[i] = table[source->data[i]];
    }
    return copy;
}

/* The '+' or '/' the stdlib still decodes next to altchars that do not cover it, and warns about; -1 for
 * none, -2 with an exception set. */
static int
stray_standard_char(const radixly_compat_input *source, PyObject *altchars)
{
    for (int i = 0; i < ALTCHARS_LEN; i++) {
        const unsigned char code = (unsigned char)"+/"[i];
        PyObject *value = PyLong_FromLong(code);
        if (value == NULL) {
            return -2;
        }
        const int covered = PySequence_Contains(altchars, value);
        Py_DECREF(value);
        if (covered < 0) {
            return -2;
        }
        if (covered == 0 && memchr(source->data, code, (size_t)source->len) != NULL) {
            return code;
        }
    }
    return -1;
}

/* The stdlib's warnings.warn after a decode that met a stray standard character; NULL when the warning is an
 * error, the result otherwise. */
static PyObject *
warn_stray_char(PyObject *result, int code, int strict, PyObject *altchars)
{
    PyObject *shown = PyObject_Repr(altchars);
    if (shown == NULL) {
        Py_DECREF(result);
        return NULL;
    }
    const int failed =
        strict != 0
            ? PyErr_WarnFormat(PyExc_DeprecationWarning, 1,
                               "invalid character '%c' in Base64 data with altchars=%U and validate=True "
                               "will be an error in future Python versions",
                               code, shown)
            : PyErr_WarnFormat(PyExc_FutureWarning, 1,
                               "invalid character '%c' in Base64 data with altchars=%U and validate=False "
                               "will be discarded in future Python versions",
                               code, shown);
    Py_DECREF(shown);
    if (failed < 0) {
        Py_DECREF(result);
        return NULL;
    }
    return result;
}

PyObject *
radixly_b64encode_with_py315(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                             radixly_b64_shape shape)
{
    PyObject *arg = NULL;
    PyObject *altchars = NULL;
    PyObject *padded = NULL;
    PyObject *wrapcol = NULL;
    radixly_param full[] = {
        {"s", &arg},
        {"altchars", &altchars},
        {"padded", &padded},
        {"wrapcol", &wrapcol},
    };
    radixly_param standard[] = {{"s", &arg}};
    radixly_param urlsafe[] = {{"s", &arg}, {"padded", &padded}};
    int bound;
    switch (shape) {
    case RADIXLY_B64_FULL:
        bound = radixly_bind_args(function, args, nargs, kwnames, full, RADIXLY_ARRAY_SIZE(full), 1, 2);
        break;
    case RADIXLY_B64_STANDARD:
        bound = radixly_bind_args(function, args, nargs, kwnames, standard, 1, 1, 1);
        break;
    default:
        bound = radixly_bind_args(function, args, nargs, kwnames, urlsafe, 2, 1, 1);
        break;
    }
    if (bound < 0) {
        return NULL;
    }
    /* altchars is judged, and joined to the alphabet, before b2a_base64 sees s. */
    PyObject *alphabet_obj = NULL;
    if (altchars != NULL && altchars != Py_None) {
        if (check_altchars_py315(altchars) < 0) {
            return NULL;
        }
        alphabet_obj = alphabet_with_altchars(altchars);
        if (alphabet_obj == NULL) {
            return NULL;
        }
    }
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) < 0) {
        Py_XDECREF(alphabet_obj);
        return NULL;
    }
    /* binascii's keywords in its own order: padded, wrapcol, newline, alphabet. */
    PyObject *result = NULL;
    size_t width = 0;
    radixly_compat_bytes alphabet;
    const int pad = padded == NULL ? 1 : PyObject_IsTrue(padded);
    const int which = shape == RADIXLY_B64_URLSAFE ? RADIXLY_B64_URL : RADIXLY_B64_STD;
    if (pad >= 0 && (wrapcol == NULL || radixly_compat_size_t(wrapcol, &width) == 0) &&
        radixly_compat_bytes_init(&alphabet, alphabet_obj, (const unsigned char *)radixly_b64_alphabet(which),
                                  ALPHABET_SIZE) == 0) {
        if (alphabet.len != ALPHABET_SIZE) {
            PyErr_SetString(PyExc_ValueError, "alphabet must have length 64");
        }
        else {
            result = b2a_base64(view.buf, view.len, pad, width, 0, alphabet.data);
        }
        radixly_compat_bytes_release(&alphabet);
    }
    Py_XDECREF(alphabet_obj);
    PyBuffer_Release(&view);
    return result;
}

/* What b64decode holds between its argument handling and the a2b_base64 call. */
typedef struct {
    PyObject *altchars; /* _bytes_from_decode_data(altchars), or NULL */
    PyObject *copy;     /* s with the altchars mapped back, or NULL for s itself */
    PyObject *alphabet; /* BASE64_ALPHABET[:-2] + altchars when ignorechars is given, or NULL */
    int stray;          /* the standard character to warn about, or -1 */
    int has_pair;       /* the altchars stand for 62 and 63 in a table of their own */
    unsigned char pair[ALTCHARS_LEN];
} b64decode_prelude;

/* The two bytes of the stdlib's maketrans(altchars, b'+/'), or its ValueError. */
static int
altchars_pair(PyObject *altchars, unsigned char pair[ALTCHARS_LEN])
{
    Py_buffer view;
    if (PyObject_GetBuffer(altchars, &view, PyBUF_SIMPLE) < 0) {
        return -1;
    }
    if (view.len != ALTCHARS_LEN) {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError, "maketrans arguments must have same length");
        return -1;
    }
    memcpy(pair, view.buf, ALTCHARS_LEN);
    PyBuffer_Release(&view);
    return 0;
}

static void
prelude_clear(b64decode_prelude *prelude)
{
    Py_CLEAR(prelude->altchars);
    Py_CLEAR(prelude->copy);
    Py_CLEAR(prelude->alphabet);
}

/* The stdlib's altchars handling, in its order: coercion, the length check, then either the translation back
 * to
 * '+/' or the alphabet for binascii. -1 with the exception set. */
static int
prelude_altchars(b64decode_prelude *prelude, const radixly_compat_input *source, PyObject *altchars,
                 int ignore_given, int copy_needed)
{
    radixly_compat_input pair;
    if (radixly_compat_decode_input(altchars, &pair) < 0) {
        return -1;
    }
    prelude->altchars = radixly_compat_input_object(&pair);
    radixly_compat_input_release(&pair);
    if (prelude->altchars == NULL || check_altchars_py315(prelude->altchars) < 0) {
        return -1;
    }
    if (ignore_given != 0) {
        prelude->alphabet = alphabet_with_altchars(prelude->altchars);
        return prelude->alphabet == NULL ? -1 : 0;
    }
    prelude->stray = stray_standard_char(source, prelude->altchars);
    if (prelude->stray == -2) {
        return -1;
    }
    if (copy_needed) {
        prelude->copy = translated_from_pair(source, prelude->altchars, (const unsigned char *)"+/");
        return prelude->copy == NULL ? -1 : 0;
    }
    prelude->has_pair = 1;
    return altchars_pair(prelude->altchars, prelude->pair);
}

/* a2b_base64 with the keywords read in binascii's order: strict_mode, padded, alphabet, ignorechars,
 * canonical; the alphabet's length is judged last, as the implementation judges it after the converters ran.
 */
static PyObject *
a2b_base64_py315(const b64decode_prelude *prelude, const radixly_compat_input *source, int strict,
                 PyObject *padded, PyObject *ignorechars, PyObject *canonical)
{
    const int pad = padded == NULL ? 1 : PyObject_IsTrue(padded);
    if (pad < 0) {
        return NULL;
    }
    radixly_compat_bytes ignore;
    if (radixly_compat_bytes_init(&ignore, ignorechars, NULL, 0) < 0) {
        return NULL;
    }
    PyObject *result = NULL;
    const int strict_pad_bits = radixly_compat_truth(canonical);
    if (strict_pad_bits >= 0) {
        unsigned char table[RADIXLY_B64_TABLE_SIZE];
        const unsigned char *rev = radixly_b64_table(RADIXLY_B64_STD);
        if (prelude->has_pair) {
            /* translate(maketrans(pair, b'+/')) folded into the table, the later entry winning like
             * maketrans. */
            memcpy(table, rev, RADIXLY_B64_TABLE_SIZE);
            table[prelude->pair[0]] = STD_ALPHABET_PREFIX;
            table[prelude->pair[1]] = STD_ALPHABET_PREFIX + 1;
            rev = table;
        }
        else if (prelude->alphabet != NULL) {
            if (!PyBytes_Check(prelude->alphabet)) {
                PyErr_Format(PyExc_TypeError, "a2b_base64() argument 'alphabet' must be bytes, not %.50s",
                             prelude->alphabet == Py_None ? "None" : Py_TYPE(prelude->alphabet)->tp_name);
                radixly_compat_bytes_release(&ignore);
                return NULL;
            }
            if (PyBytes_GET_SIZE(prelude->alphabet) != ALPHABET_SIZE) {
                PyErr_SetString(PyExc_ValueError, "alphabet must have length 64");
                radixly_compat_bytes_release(&ignore);
                return NULL;
            }
            radixly_b64_reverse_table((const unsigned char *)PyBytes_AS_STRING(prelude->alphabet), table);
            rev = table;
        }
        const unsigned char *data =
            prelude->copy != NULL ? (const unsigned char *)PyBytes_AS_STRING(prelude->copy) : source->data;
        const Py_ssize_t len = prelude->copy != NULL ? PyBytes_GET_SIZE(prelude->copy) : source->len;
        result = a2b_base64(data, len, strict, pad, rev, ignore.data, ignore.len, strict_pad_bits);
    }
    radixly_compat_bytes_release(&ignore);
    return result;
}

/* The stdlib's b64decode once s is coerced; releases source. */
static PyObject *
b64decode_py315(radixly_compat_input *source, PyObject *altchars, PyObject *validate, PyObject *padded,
                PyObject *ignorechars, PyObject *canonical)
{
    const int validate_given = radixly_compat_specified(validate);
    const int ignore_given = radixly_compat_specified(ignorechars);
    b64decode_prelude prelude = {NULL, NULL, NULL, -1, 0, {0, 0}};
    PyObject *result = NULL;
    const int copy_needed = !inert_flag(validate) || !inert_flag(padded) || !inert_flag(canonical);
    if (altchars != NULL && altchars != Py_None &&
        prelude_altchars(&prelude, source, altchars, ignore_given, copy_needed) < 0) {
        goto done;
    }
    /* The stdlib decodes the copy its translate() made, so a hook in the flags may resize s from here on. */
    if (prelude.copy != NULL) {
        radixly_compat_input_release(source);
    }
    /* validate defaults to whether ignorechars was given; a given one is read where binascii reads
     * strict_mode. */
    const int strict = validate_given != 0 ? PyObject_IsTrue(validate) : ignore_given;
    if (strict < 0) {
        goto done;
    }
    result =
        a2b_base64_py315(&prelude, source, strict, padded, ignore_given != 0 ? ignorechars : NULL, canonical);
    if (result != NULL && prelude.stray >= 0) {
        result = warn_stray_char(result, prelude.stray, strict, prelude.altchars);
    }
done:
    prelude_clear(&prelude);
    radixly_compat_input_release(source); /* a second release is a no-op */
    return result;
}

/* The stdlib's urlsafe_b64decode once s is coerced: '-_' mapped to '+/', a stray '+' or '/' warned about;
 * releases source. */
static PyObject *
urlsafe_b64decode_py315(radixly_compat_input *source, PyObject *padded)
{
    int stray = -1;
    for (int i = 0; i < ALTCHARS_LEN && stray < 0; i++) {
        const unsigned char code = (unsigned char)"+/"[i];
        if (memchr(source->data, code, (size_t)source->len) != NULL) {
            stray = code;
        }
    }
    PyObject *snapshot = NULL;
    if (!inert_flag(padded)) {
        snapshot = PyBytes_FromStringAndSize((const char *)source->data, source->len);
        radixly_compat_input_release(source);
        if (snapshot == NULL) {
            return NULL;
        }
        source->data = (const unsigned char *)PyBytes_AS_STRING(snapshot);
        source->len = PyBytes_GET_SIZE(snapshot);
    }
    PyObject *result = NULL;
    const int pad = radixly_compat_truth(padded);
    if (pad >= 0) {
        result = a2b_base64(source->data, source->len, 0, pad, URL_LENIENT_REV, NULL, 0, 0);
    }
    radixly_compat_input_release(source);
    Py_XDECREF(snapshot);
    if (result != NULL && stray >= 0 &&
        PyErr_WarnFormat(PyExc_FutureWarning, 1,
                         "invalid character '%c' in URL-safe Base64 data will be discarded in future Python "
                         "versions",
                         stray) < 0) {
        Py_CLEAR(result);
    }
    return result;
}

PyObject *
radixly_b64decode_with_py315(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                             radixly_b64_shape shape)
{
    PyObject *arg = NULL;
    PyObject *altchars = NULL;
    PyObject *validate = NULL;
    PyObject *padded = NULL;
    PyObject *ignorechars = NULL;
    PyObject *canonical = NULL;
    radixly_param full[] = {
        {"s", &arg},         {"altchars", &altchars},       {"validate", &validate},
        {"padded", &padded}, {"ignorechars", &ignorechars}, {"canonical", &canonical},
    };
    radixly_param standard[] = {{"s", &arg}};
    radixly_param urlsafe[] = {{"s", &arg}, {"padded", &padded}};
    int bound;
    switch (shape) {
    case RADIXLY_B64_FULL:
        bound = radixly_bind_args(function, args, nargs, kwnames, full, RADIXLY_ARRAY_SIZE(full), 1, 3);
        break;
    case RADIXLY_B64_STANDARD:
        bound = radixly_bind_args(function, args, nargs, kwnames, standard, 1, 1, 1);
        break;
    default:
        bound = radixly_bind_args(function, args, nargs, kwnames, urlsafe, 2, 1, 1);
        break;
    }
    if (bound < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    if (shape == RADIXLY_B64_URLSAFE) {
        return urlsafe_b64decode_py315(&source, padded);
    }
    return b64decode_py315(&source, altchars, validate, padded, ignorechars, canonical);
}

const char radixly_b64encode_py315_doc[] =
    PyDoc_STR("b64encode($module, /, s, altchars=None, *, padded=True, wrapcol=0)\n"
              "--\n"
              "\n"
              "Encode the bytes-like object s using Base64 and return a bytes object.\n"
              "\n"
              "Optional altchars should be a byte string of length 2 which specifies an\n"
              "alternative alphabet for the '+' and '/' characters.  This allows an\n"
              "application to e.g. generate url or filesystem safe Base64 strings.\n"
              "\n"
              "If padded is false, omit padding in the output.\n"
              "\n"
              "If wrapcol is non-zero, insert a newline (b'\\n') character after at most\n"
              "every wrapcol characters.");
PyObject *
radixly_b64encode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b64encode_with_py315("b64encode", args, nargs, kwnames, RADIXLY_B64_FULL);
}

const char radixly_b64decode_py315_doc[] =
    PyDoc_STR("b64decode($module, /, s, altchars=None, validate=['NOT SPECIFIED'], *, padded=True, "
              "ignorechars=['NOT SPECIFIED'], canonical=False)\n"
              "--\n"
              "\n"
              "Decode the Base64 encoded bytes-like object or ASCII string s.\n"
              "\n"
              "Optional altchars must be a bytes-like object or ASCII string of length 2\n"
              "which specifies the alternative alphabet used instead of the '+' and '/'\n"
              "characters.\n"
              "\n"
              "If padded is false, padding in input is not required.\n"
              "\n"
              "The result is returned as a bytes object.  A binascii.Error is raised if\n"
              "s is incorrectly padded.\n"
              "\n"
              "If ignorechars is specified, it should be a byte string containing\n"
              "characters to ignore from the input.  The default value of validate is\n"
              "True if ignorechars is specified, False otherwise.\n"
              "\n"
              "If validate is false, characters that are neither in the normal base-64\n"
              "alphabet nor the alternative alphabet are discarded prior to the\n"
              "padding check.  If validate is true, these non-alphabet characters in\n"
              "the input result in a binascii.Error if they are not in ignorechars.\n"
              "For more information about the strict base64 check, see:\n"
              "\n"
              "https://docs.python.org/3.11/library/binascii.html#binascii.a2b_base64");
PyObject *
radixly_b64decode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b64decode_with_py315("b64decode", args, nargs, kwnames, RADIXLY_B64_FULL);
}

PyObject *
radixly_standard_b64encode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames)
{
    return radixly_b64encode_with_py315("standard_b64encode", args, nargs, kwnames, RADIXLY_B64_STANDARD);
}

PyObject *
radixly_standard_b64decode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs,
                                 PyObject *kwnames)
{
    return radixly_b64decode_with_py315("standard_b64decode", args, nargs, kwnames, RADIXLY_B64_STANDARD);
}

/* The stdlib's encodebytes on 3.15: one b2a_base64 call wrapped at 76, b'' for the lone newline of empty
 * input. */
PyObject *
radixly_encodebytes_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs,
                          PyObject *kwnames)
{
    PyObject *arg = NULL;
    radixly_param params[] = {{"s", &arg}};
    if (radixly_bind_args("encodebytes", args, nargs, kwnames, params, 1, 1, 1) < 0) {
        return NULL;
    }
    Py_ssize_t length = 0;
    if (input_type_check(arg, &length) < 0) {
        return NULL;
    }
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) < 0) {
        return NULL;
    }
    PyObject *result = b2a_base64(view.buf, view.len, 1, MAXLINESIZE, 1,
                                  (const unsigned char *)radixly_b64_alphabet(RADIXLY_B64_STD));
    PyBuffer_Release(&view);
    if (result != NULL && PyBytes_GET_SIZE(result) == 1) {
        Py_DECREF(result);
        return PyBytes_FromStringAndSize("", 0);
    }
    return result;
}
