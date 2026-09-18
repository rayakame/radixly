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
#include "base64.h"

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/errors.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 3,
    GROUP_CHARS = 4,
    REV_PAD = 64, /* the compat tables: a byte the stdlib's translate turns into '=' */
    REV_INVALID = 0xFF,
    PAD = '=',
    NUM_ALPHABETS = 2,
    TABLE_SIZE = 256,
    ASCII_MAX = 0x7F,
};

static const unsigned BITS_PER_CHAR = 6U;
static const unsigned GROUP_BITS = 24U;
static const unsigned CHAR_MASK = 0x3FU;
static const unsigned FIRST_BYTE_SHIFT = 16U; /* the top byte of a 24-bit group */
static const unsigned SIX_BIT_LIMIT = 64U;

/* The stdlib's switch on quad_pos, bit for bit: the bits a character leaves for the next output byte. */
static const unsigned LEFT_FOUR_BITS = 0x0FU;
static const unsigned LEFT_TWO_BITS = 0x03U;
static const unsigned SHIFT_TWO = 2U;
static const unsigned SHIFT_FOUR = 4U;

/* The stdlib's BASE64_MAXBIN: b2a_base64 refuses more with binascii.Error, never MemoryError. */
static const Py_ssize_t STDLIB_MAX_INPUT = (PY_SSIZE_T_MAX - 3) / 2;

typedef struct {
    const char *alphabet;
    uint8_t rev[TABLE_SIZE]; /* the alphabet's own 64 characters, the strict codec */
} alphabet_tables;

static const char ALPHABET_STD[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static const char ALPHABET_URL[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
static alphabet_tables TABLES[NUM_ALPHABETS];

/* The stdlib's table_a2b_base64 with '=' marked; [1] is it behind urlsafe_b64decode's translate, so '-' and
 * '_' decode next to '+' and '/'. */
static uint8_t COMPAT_REV[NUM_ALPHABETS][TABLE_SIZE];

/* Data characters a padded final group may hold, mapped to the payload bytes they carry; -1 is not a shape.
 */
static const int PAYLOAD_BYTES[GROUP_CHARS + 1] = {-1, -1, 1, 2, 3};

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
radixly_base64_exec(PyObject *Py_UNUSED(module))
{
    const char *alphabets[NUM_ALPHABETS] = {ALPHABET_STD, ALPHABET_URL};
    for (int which = 0; which < NUM_ALPHABETS; which++) {
        alphabet_tables *tables = &TABLES[which];
        tables->alphabet = alphabets[which];
        for (unsigned code = 0; code < TABLE_SIZE; code++) {
            tables->rev[code] = REV_INVALID;
            COMPAT_REV[which][code] = REV_INVALID;
        }
        for (unsigned value = 0; value < SIX_BIT_LIMIT; value++) {
            tables->rev[(unsigned char)alphabets[which][value]] = (uint8_t)value;
            COMPAT_REV[which][(unsigned char)ALPHABET_STD[value]] = (uint8_t)value;
        }
        COMPAT_REV[which][PAD] = REV_PAD;
    }
    for (unsigned value = 0; value < SIX_BIT_LIMIT; value++) {
        COMPAT_REV[1][(unsigned char)ALPHABET_URL[value]] = (uint8_t)value;
    }
    A2B_VARIANT = a2b_variant_for(Py_Version);
    return 0;
}

static Py_ssize_t
encoded_len(Py_ssize_t num_bytes)
{
    return GROUP_CHARS * ((num_bytes + GROUP_BYTES - 1) / GROUP_BYTES);
}

/* Up to three bytes as one big-endian 24-bit value, the missing ones zero. */
static uint32_t
pack(const unsigned char *source, Py_ssize_t count)
{
    uint32_t acc = 0;
    for (Py_ssize_t i = 0; i < count; i++) {
        acc |= (uint32_t)source[i] << (FIRST_BYTE_SHIFT - (BITS_PER_BYTE * (unsigned)i));
    }
    return acc;
}

/* The top count bytes of a 24-bit value, big-endian. */
static void
unpack(uint32_t acc, unsigned char *out, int count)
{
    for (int i = 0; i < count; i++) {
        out[i] = (unsigned char)((acc >> (FIRST_BYTE_SHIFT - (BITS_PER_BYTE * (unsigned)i))) & BYTE_MASK);
    }
}

/* The top count characters of a 24-bit value. */
static void
put_chars(uint32_t acc, unsigned char *out, int count, const char *alphabet)
{
    for (int i = 0; i < count; i++) {
        const unsigned shift = GROUP_BITS - (BITS_PER_CHAR * ((unsigned)i + 1U));
        out[i] = (unsigned char)alphabet[(acc >> shift) & CHAR_MASK];
    }
}

/* Four characters per three bytes, the tail zero-padded and finished with '='. */
static void
fill(const unsigned char *source, Py_ssize_t num_bytes, unsigned char *out, const char *alphabet)
{
    Py_ssize_t offset = 0;
    for (; offset + GROUP_BYTES <= num_bytes; offset += GROUP_BYTES) {
        put_chars(pack(source + offset, GROUP_BYTES), out, GROUP_CHARS, alphabet);
        out += GROUP_CHARS;
    }
    const Py_ssize_t leftover = num_bytes - offset;
    if (leftover > 0) {
        const int chars = (int)(((BITS_PER_BYTE * (unsigned)leftover) + BITS_PER_CHAR - 1U) / BITS_PER_CHAR);
        put_chars(pack(source + offset, leftover), out, chars, alphabet);
        for (int i = chars; i < GROUP_CHARS; i++) {
            out[i] = PAD;
        }
    }
}

PyObject *
radixly_base64_encode_with(PyObject *arg, int url)
{
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len == 0) {
        PyBuffer_Release(&view);
        return PyUnicode_New(0, 0);
    }
    if (view.len > (PY_SSIZE_T_MAX / GROUP_CHARS) - GROUP_BYTES) {
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    PyObject *result = PyUnicode_New(encoded_len(view.len), ASCII_MAX);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return NULL;
    }
    fill(view.buf, view.len, PyUnicode_1BYTE_DATA(result), TABLES[url].alphabet);
    PyBuffer_Release(&view);
    return result;
}

typedef struct {
    int kind;
    const void *data;
    const uint8_t *rev;
    const char *codec;
} text_source;

static int
raise_invalid(const text_source *source, Py_ssize_t index, Py_UCS4 code_point)
{
    radixly_raise_decode_error(index, "invalid %s character U+%x at index %zd", source->codec,
                               (unsigned)code_point, index);
    return -1;
}

/* Read one group of four into acc, data_chars being 4 or the index of the first '='; raises on a bad
 * character. */
static int
read_group(const text_source *source, Py_ssize_t base, uint32_t *acc, int *data_chars)
{
    *acc = 0;
    *data_chars = GROUP_CHARS;
    for (int i = 0; i < GROUP_CHARS; i++) {
        const Py_UCS4 code_point = PyUnicode_READ(source->kind, source->data, base + i);
        if (code_point == PAD) {
            if (*data_chars == GROUP_CHARS) {
                *data_chars = i;
            }
            continue;
        }
        if (code_point > ASCII_MAX || source->rev[code_point] == REV_INVALID) {
            return raise_invalid(source, base + i, code_point);
        }
        if (*data_chars != GROUP_CHARS) {
            radixly_raise_decode_error(base + i, "data character U+%x at index %zd after padding",
                                       (unsigned)code_point, base + i);
            return -1;
        }
        *acc = (*acc << BITS_PER_CHAR) | source->rev[code_point];
    }
    return 0;
}

/* A padded group is only ever the last one, in the two shapes the encoder produces, with zero pad bits. */
static int
finish_padded(uint32_t acc, int data_chars, Py_ssize_t pad_index, int is_last, unsigned char *out,
              int *written)
{
    if (!is_last) {
        radixly_raise_decode_error(pad_index, "padding at index %zd before the end of the text", pad_index);
        return -1;
    }
    const int payload = PAYLOAD_BYTES[data_chars];
    if (payload < 0) {
        radixly_raise_decode_error(pad_index,
                                   "%d data characters before the padding at index %zd, not 2 or 3",
                                   data_chars, pad_index);
        return -1;
    }
    const unsigned pad_bits = (BITS_PER_CHAR * (unsigned)data_chars) - (BITS_PER_BYTE * (unsigned)payload);
    if ((acc & ((1U << pad_bits) - 1U)) != 0) {
        radixly_raise_decode_error(pad_index - 1, "%u padding bits not zero in the character at index %zd",
                                   pad_bits, pad_index - 1);
        return -1;
    }
    unpack(acc << (BITS_PER_CHAR * (unsigned)(GROUP_CHARS - data_chars)), out, payload);
    *written = payload;
    return 0;
}

/* The characters after the last full group are still checked, so an invalid one reports its own index. */
static void
raise_for_remainder(const text_source *source, Py_ssize_t start, Py_ssize_t num_chars)
{
    for (Py_ssize_t i = start; i < num_chars; i++) {
        const Py_UCS4 code_point = PyUnicode_READ(source->kind, source->data, i);
        if (code_point == PAD) {
            radixly_raise_decode_error(i, "padding at index %zd in an incomplete group", i);
            return;
        }
        if (code_point > ASCII_MAX || source->rev[code_point] == REV_INVALID) {
            raise_invalid(source, i, code_point);
            return;
        }
    }
    radixly_raise_decode_error(num_chars, "length %zd is not a multiple of 4", num_chars);
}

/* Strict RFC 4648; characters raise left to right at their own index. */
PyObject *
radixly_base64_decode_with(PyObject *arg, int url)
{
    if (!PyUnicode_Check(arg)) {
        PyErr_Format(PyExc_TypeError, "expected str, not %.200s", Py_TYPE(arg)->tp_name);
        return NULL;
    }
#if PY_VERSION_HEX < 0x030C0000
    /* 3.11 can still meet legacy, non-ready strings from other C extensions;
     * GET_LENGTH/KIND/DATA on one is UB. Deprecated call, compiles out on
     * 3.12+; a 3.11 -Werror build may need a suppression. */
    if (PyUnicode_READY(arg) == -1) {
        return NULL;
    }
#endif
    const Py_ssize_t num_chars = PyUnicode_GET_LENGTH(arg);
    if (num_chars == 0) {
        return PyBytes_FromStringAndSize("", 0);
    }
    const text_source source = {PyUnicode_KIND(arg), PyUnicode_DATA(arg), TABLES[url].rev,
                                url ? "base64url" : "base64"};
    const Py_ssize_t num_groups = num_chars / GROUP_CHARS;
    const Py_ssize_t remainder = num_chars % GROUP_CHARS;

    PyObject *result = PyBytes_FromStringAndSize(NULL, GROUP_BYTES * num_groups);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    Py_ssize_t out_len = GROUP_BYTES * num_groups;
    for (Py_ssize_t group = 0; group < num_groups; group++) {
        uint32_t acc;
        int data_chars;
        if (read_group(&source, GROUP_CHARS * group, &acc, &data_chars) < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (data_chars == GROUP_CHARS) {
            unpack(acc, out + (GROUP_BYTES * group), GROUP_BYTES);
            continue;
        }
        int written;
        const int is_last = group == num_groups - 1 && remainder == 0;
        if (finish_padded(acc, data_chars, (GROUP_CHARS * group) + data_chars, is_last,
                          out + (GROUP_BYTES * group), &written) < 0) {
            Py_DECREF(result);
            return NULL;
        }
        out_len = (GROUP_BYTES * group) + written;
    }
    if (remainder != 0) {
        Py_DECREF(result);
        raise_for_remainder(&source, GROUP_CHARS * num_groups, num_chars);
        return NULL;
    }
    if (out_len != GROUP_BYTES * num_groups && _PyBytes_Resize(&result, out_len) < 0) {
        return NULL; /* result already cleared and the exception set */
    }
    return result;
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
    fill(view.buf, view.len, out, TABLES[url].alphabet);
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

/* The stdlib's checks after its loop; the count in the message is its arithmetic on bytes written. */
static int
finish(const a2b_state *state, int incomplete, const unsigned char *start, Py_ssize_t *written)
{
    if (state->quad_pos == 1) {
        radixly_binascii_error_format("Invalid base64-encoded string: number of data characters (%zd) "
                                      "cannot be 1 more than a multiple of 4",
                                      ((state->out - start) / GROUP_BYTES * GROUP_CHARS) + 1);
        return -1;
    }
    if (incomplete) {
        radixly_binascii_error("Incorrect padding");
        return -1;
    }
    *written = state->out - start;
    return 0;
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

/* a2b_base64 as 3.11 to 3.12.3 (stop at padding) and 3.12.4 to 3.13.12 (plus the excess-padding check) had
 * it.
 */
static int
a2b_stopping(const uint8_t *rev, const unsigned char *data, Py_ssize_t length, int strict, int excess_check,
             unsigned char *start, Py_ssize_t *written)
{
    a2b_state state = {0, 0, start};
    int pads = 0;
    int padding_started = 0;
    if (strict && length > 0 && rev[data[0]] == REV_PAD) {
        radixly_binascii_error("Leading padding not allowed");
        return -1;
    }
    for (Py_ssize_t i = 0; i < length; i++) {
        const uint8_t value = rev[data[i]];
        if (value == REV_PAD) {
            padding_started = 1;
            const int outcome = pad_stopping(&state, &pads, i, length, strict, excess_check);
            if (outcome < 0) {
                return -1;
            }
            if (outcome > 0) {
                *written = state.out - start; /* the stdlib's goto done, past the checks below */
                return 0;
            }
            continue;
        }
        if (value >= SIX_BIT_LIMIT) {
            if (strict) {
                radixly_binascii_error("Only base64 data is allowed");
                return -1;
            }
            continue;
        }
        if (strict && padding_started) {
            radixly_binascii_error("Discontinuous padding not allowed");
            return -1;
        }
        pads = 0;
        take_char(&state, value);
    }
    return finish(&state, state.quad_pos != 0, start, written);
}

/* The stdlib's pad counter is an int that wraps under CPython's -fwrapv once the lenient reading-past loop
 * has counted 2**31 pad bytes; unsigned arithmetic gives the same wrap without the UB. */
static int
wrapping_add(int first, int second)
{
    return (int)((unsigned)first + (unsigned)second);
}

/* A '=' in the reading-past variant: -1 with the error, 1 to leave the loop for its tail, 0 to carry on. */
static int
pad_reading_past(const a2b_state *state, int *pads, Py_ssize_t index, int strict)
{
    *pads = wrapping_add(*pads, 1);
    if (state->quad_pos >= 2 && wrapping_add(state->quad_pos, *pads) <= GROUP_CHARS) {
        return 0;
    }
    if (!strict) {
        return 0;
    }
    if (state->quad_pos == 1) {
        return 1; /* the one-extra error in the tail */
    }
    radixly_binascii_error(state->quad_pos == 0 && index == 0 ? "Leading padding not allowed"
                                                              : "Excess padding not allowed");
    return -1;
}

/* a2b_base64 as 3.13.13 and 3.14.4 on have it: padding is skipped and the parse continues past it. */
static int
a2b_reading_past(const uint8_t *rev, const unsigned char *data, Py_ssize_t length, int strict,
                 unsigned char *start, Py_ssize_t *written)
{
    a2b_state state = {0, 0, start};
    int pads = 0;
    for (Py_ssize_t i = 0; i < length; i++) {
        const uint8_t value = rev[data[i]];
        if (value == REV_PAD) {
            const int outcome = pad_reading_past(&state, &pads, i, strict);
            if (outcome < 0) {
                return -1;
            }
            if (outcome > 0) {
                break;
            }
            continue;
        }
        if (value >= SIX_BIT_LIMIT) {
            if (strict) {
                radixly_binascii_error("Only base64 data is allowed");
                return -1;
            }
            continue;
        }
        if (pads != 0 && strict) {
            radixly_binascii_error(wrapping_add(state.quad_pos, pads) == GROUP_CHARS
                                       ? "Excess data after padding"
                                       : "Discontinuous padding not allowed");
            return -1;
        }
        pads = 0;
        take_char(&state, value);
    }
    return finish(&state, state.quad_pos != 0 && wrapping_add(state.quad_pos, pads) < GROUP_CHARS, start,
                  written);
}

/* A faithful port of binascii.a2b_base64 on translated bytes: the bytes result, or NULL with binascii.Error.
 */
static PyObject *
stdlib_a2b(const uint8_t *rev, const unsigned char *data, Py_ssize_t length, int strict)
{
    const Py_ssize_t bound = GROUP_BYTES * ((length / GROUP_CHARS) + (length % GROUP_CHARS != 0 ? 1 : 0));
    PyObject *result = PyBytes_FromStringAndSize(NULL, bound);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    Py_ssize_t written = 0;
    int outcome;
    switch (A2B_VARIANT) {
    case A2B_STOPS_AT_PADDING:
        outcome = a2b_stopping(rev, data, length, strict, 0, start, &written);
        break;
    case A2B_REFUSES_EXCESS_PADDING:
        outcome = a2b_stopping(rev, data, length, strict, 1, start, &written);
        break;
    default:
        outcome = a2b_reading_past(rev, data, length, strict, start, &written);
        break;
    }
    if (outcome < 0) {
        Py_DECREF(result);
        return NULL;
    }
    if (written != bound && _PyBytes_Resize(&result, written) < 0) {
        return NULL; /* result already cleared and the exception set */
    }
    return result;
}

/* The stdlib's altchars: _bytes_from_decode_data, the length assert, then translate(maketrans(altchars,
 * b'+/')) folded into the reverse table, later entries winning like maketrans. */
static int
decode_altchars(PyObject *altchars, uint8_t *rev)
{
    radixly_compat_input pair;
    if (radixly_compat_decode_input(altchars, &pair) < 0) {
        return -1;
    }
    if (radixly_compat_check_length(&pair, 2) < 0) {
        radixly_compat_input_release(&pair);
        return -1;
    }
    for (unsigned code = 0; code < TABLE_SIZE; code++) {
        rev[code] = COMPAT_REV[0][code];
    }
    rev[pair.data[0]] = TABLES[0].rev[(unsigned char)'+'];
    rev[pair.data[1]] = TABLES[0].rev[(unsigned char)'/'];
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
    const uint8_t *rev = COMPAT_REV[url];
    uint8_t translated[TABLE_SIZE];
    PyObject *snapshot = NULL;
    if (altchars != NULL && altchars != Py_None) {
        if (decode_altchars(altchars, translated) < 0) {
            radixly_compat_input_release(&source);
            return NULL;
        }
        rev = translated;
        /* The stdlib decodes the copy its translate() made, so a validate hook editing s reaches neither. */
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
    fill(data, len, out, TABLES[0].alphabet);
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
        fill(data + offset, count, out, TABLES[0].alphabet);
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
    PyObject *result = stdlib_a2b(COMPAT_REV[0], source.data, source.len, 0);
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
        PyObject *decoded = stdlib_a2b(COMPAT_REV[0], source.data, source.len, 0);
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

const char radixly_base64_encode_doc[] =
    PyDoc_STR("base64_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base64 text.\n"
              "\n"
              "RFC 4648 section 4: four characters per three bytes, a shorter tail\n"
              "padded with ``=`` to a full group. ``n`` bytes become\n"
              "``4 * ceil(n / 3)`` characters.\n"
              "\n"
              "Parameters\n"
              "----------\n"
              "data\n"
              "    The bytes to encode: anything supporting the buffer protocol.\n"
              "\n"
              "Returns\n"
              "-------\n"
              "str\n"
              "    The encoded text; empty input encodes to the empty string.\n"
              "\n"
              "Raises\n"
              "------\n"
              "TypeError\n"
              "    If ``data`` is a ``str`` or otherwise not bytes-like.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> from radixly import base64\n"
              ">>> base64.encode(b'hi')\n"
              "'aGk='\n"
              ">>> base64.decode(base64.encode(b'hi'))\n"
              "b'hi'");
PyObject *
radixly_base64_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base64_encode_with(arg, 0);
}

const char radixly_base64_decode_doc[] =
    PyDoc_STR("base64_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base64 text back to bytes.\n"
              "\n"
              "Strict RFC 4648: the alphabet ``A-Za-z0-9+/`` only, groups of four,\n"
              "padding only at the end in the two shapes the encoder produces, pad\n"
              "bits zero.\n"
              "\n"
              "Parameters\n"
              "----------\n"
              "data\n"
              "    The text to decode.\n"
              "\n"
              "Returns\n"
              "-------\n"
              "bytes\n"
              "    The decoded payload; the empty string decodes to ``b''``.\n"
              "\n"
              "Raises\n"
              "------\n"
              "TypeError\n"
              "    If ``data`` is not a ``str``.\n"
              "DecodeError\n"
              "    On malformed or non-canonical input; ``position`` is the index of\n"
              "    the offending character, or the length when the text stops short of\n"
              "    a full group.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> import radixly\n"
              ">>> try:\n"
              "...     radixly.base64.decode('aGk')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "3");
PyObject *
radixly_base64_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base64_decode_with(arg, 0);
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
