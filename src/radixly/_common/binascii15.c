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
#include "binascii15.h"

#include "compat.h"
#include "internal.h"

enum {
    INVALID = 0xFF,
    PAD = '=',
    B64_SIZE = 64,
    B64_GROUP_BYTES = 3,
    B64_GROUP_CHARS = 4,
    B32_SIZE = 32,
    B32_GROUP_BYTES = 5,
    B32_GROUP_CHARS = 8,
    B85_BASE = 85,
    B85_GROUP_BYTES = 4,
    B85_GROUP_CHARS = 5,
    B85_TOP_DIGIT = 84,
    A85_PREFIX = '<',
    A85_AFFIX = '~',
    A85_SUFFIX = '>',
    A85_FRAME = 4, /* "<~" and "~>" */
    HEX_BASE = 16,
    HEX_DIGITS_PER_BYTE = 2,
    HEX_LETTER = 10, /* the digit 'a' and 'A' stand for */
};

static const unsigned B64_BITS = 6U;
static const unsigned B32_BITS = 5U;
static const unsigned FOUR_BITS = 0x0FU;
static const unsigned THREE_BITS = 0x07U;
static const unsigned B64_MASK = 0x3FU;
static const unsigned B32_MASK = 0x1FU;
static const unsigned NIBBLE = 4U;
static const unsigned TOP_BYTE_SHIFT = 24U; /* of a 32-bit word */
static const uint32_t A85_Z = 0x00000000U;
static const uint32_t A85_Y = 0x20202020U;
/* 85 to the power of 0 to 4, the span of words a tail's dropped digits cover. */
static const uint32_t POW85[B85_GROUP_CHARS] = {1, 85, 7225, 614125, 52200625};
static const char HEX_UPPER[] = "0123456789ABCDEF";

/* binascii caches the answer per byte and asks memchr once; so does this. */
typedef struct {
    const unsigned char *chars; /* NULL once nothing is ignored */
    Py_ssize_t len;
    unsigned char cache[RADIXLY_PY315_TABLE_SIZE / BITS_PER_BYTE];
} ignore_set;

static void
ignore_set_init(ignore_set *set, const unsigned char *chars, Py_ssize_t len)
{
    set->chars = len == 0 ? NULL : chars;
    set->len = len;
    memset(set->cache, 0, sizeof(set->cache));
}

static int
ignored(ignore_set *set, unsigned char code)
{
    if (set->chars == NULL) {
        return 0;
    }
    const unsigned bit = 1U << (code & THREE_BITS);
    const unsigned slot = code >> 3U;
    if ((set->cache[slot] & bit) != 0) {
        return 1;
    }
    if (memchr(set->chars, code, (size_t)set->len) != NULL) {
        set->cache[slot] |= (unsigned char)bit;
        return 1;
    }
    return 0;
}

void
radixly_py315_reverse_table(const unsigned char *alphabet, unsigned size, int pad,
                            unsigned char table[RADIXLY_PY315_TABLE_SIZE])
{
    memset(table, INVALID, RADIXLY_PY315_TABLE_SIZE);
    for (unsigned i = 0; i < size; i++) {
        table[alphabet[i]] = (unsigned char)i;
    }
    if (pad >= 0) {
        table[pad] = (unsigned char)size;
    }
}

int
radixly_py315_size_t(PyObject *arg, size_t *value)
{
    PyObject *index = PyNumber_Index(arg);
    if (index == NULL) {
        return -1;
    }
    PyObject *zero = PyLong_FromLong(0);
    if (zero == NULL) {
        Py_DECREF(index);
        return -1;
    }
    const int negative = PyObject_RichCompareBool(index, zero, Py_LT);
    Py_DECREF(zero);
    if (negative != 0) {
        Py_DECREF(index);
        if (negative > 0) {
            PyErr_SetString(PyExc_ValueError, "Cannot convert negative int");
        }
        return -1;
    }
    const size_t converted = PyLong_AsSize_t(index);
    Py_DECREF(index);
    if (converted == (size_t)-1 && PyErr_Occurred()) {
        if (PyErr_ExceptionMatches(PyExc_OverflowError)) {
            PyErr_SetString(PyExc_OverflowError, "Python int too large for C size_t");
        }
        return -1;
    }
    *value = converted;
    return 0;
}

/* The result trimmed to what was written; NULL with the exception set when the shrink fails. */
static PyObject *
finish(PyObject *result, Py_ssize_t written)
{
    if (written != PyBytes_GET_SIZE(result) && _PyBytes_Resize(&result, written) < 0) {
        return NULL; /* result already cleared */
    }
    return result;
}

/* Whole groups rounded up, as binascii bounds its output. */
static size_t
groups_bound(Py_ssize_t len, size_t in_group, size_t out_group)
{
    return (((size_t)len + in_group - 1U) / in_group) * out_group;
}

/* binascii's wraplines: a newline after every width characters, moving the data right; returns the new size.
 */
static Py_ssize_t
wraplines(unsigned char *data, Py_ssize_t size, size_t width)
{
    if ((size_t)size <= width) {
        return size;
    }
    unsigned char *src = data + size;
    const Py_ssize_t newlines = (size - 1) / (Py_ssize_t)width;
    Py_ssize_t line_len = size - (newlines * (Py_ssize_t)width);
    size += newlines;
    unsigned char *dst = data + size;
    while ((src -= line_len) != data) {
        dst -= line_len;
        memmove(dst, src, (size_t)line_len);
        *--dst = '\n';
        line_len = (Py_ssize_t)width;
    }
    assert(dst == data + width);
    return size;
}

/* The bit accumulator behind binascii's quad_pos and octa_pos switches: leftchar holds the bits no byte has
 * taken yet, and pos counts the characters of the group. */
typedef struct {
    unsigned char *start;
    unsigned char *out;
    unsigned pos;
    unsigned leftchar;
    unsigned leftbits;
    unsigned pads; /* binascii's int wraps under -fwrapv; unsigned arithmetic wraps the same without the UB */
} bits_state;

static void
bits_take(bits_state *state, unsigned value, unsigned bits, unsigned group_chars)
{
    state->pos = (state->pos + 1U) % group_chars;
    state->leftchar = (state->leftchar << bits) | value;
    state->leftbits += bits;
    if (state->leftbits >= BITS_PER_BYTE) {
        state->leftbits -= BITS_PER_BYTE;
        *state->out++ = (unsigned char)((state->leftchar >> state->leftbits) & BYTE_MASK);
        state->leftchar &= (1U << state->leftbits) - 1U;
    }
}

/* The encoder's tail: the leftover bytes, then zero bits up to the next whole character. */
static unsigned char *
put_tail(unsigned char *out, const unsigned char *data, Py_ssize_t leftover, unsigned bits, unsigned mask,
         const unsigned char *alphabet)
{
    const unsigned chars = ((BITS_PER_BYTE * (unsigned)leftover) + bits - 1U) / bits;
    uint64_t combined = 0;
    for (Py_ssize_t i = 0; i < leftover; i++) {
        combined = (combined << BITS_PER_BYTE) | data[i];
    }
    combined <<= (bits * chars) - (BITS_PER_BYTE * (unsigned)leftover);
    for (unsigned i = chars; i > 0; i--) {
        *out++ = alphabet[(combined >> (bits * (i - 1U))) & mask];
    }
    return out;
}

/* One whole group of bytes as characters. */
static unsigned char *
put_group(unsigned char *out, const unsigned char *data, int group_bytes, int group_chars, unsigned bits,
          unsigned mask, const unsigned char *alphabet)
{
    uint64_t combined = 0;
    for (int i = 0; i < group_bytes; i++) {
        combined = (combined << BITS_PER_BYTE) | data[i];
    }
    for (int i = group_chars - 1; i >= 0; i--) {
        *out++ = alphabet[(combined >> (bits * (unsigned)i)) & mask];
    }
    return out;
}

/* base64 */

/* A '=': 1 to go on with the next character, 0 to stop reading (the one-extra error follows), -1 with the
 * error set. */
static int
a2b64_pad(bits_state *state, int strict, ignore_set *skip)
{
    state->pads++;
    if (state->pos >= 2 && state->pos + state->pads <= B64_GROUP_CHARS) {
        return 1;
    }
    if (strict == 0 || ignored(skip, PAD) != 0) {
        return 1;
    }
    if (state->pos == 1) {
        return 0;
    }
    radixly_binascii_error(state->pos == 0 && state->out == state->start ? "Leading padding not allowed"
                                                                         : "Excess padding not allowed");
    return -1;
}

/* One character of binascii's slow path: 1 to go on, 0 to leave the loop, -1 with the error set. */
static int
a2b64_step(bits_state *state, unsigned char this_ch, int strict, int padded, const unsigned char *table,
           ignore_set *skip)
{
    if (padded != 0 && this_ch == PAD) {
        return a2b64_pad(state, strict, skip);
    }
    const unsigned value = table[this_ch];
    if (value >= B64_SIZE) {
        if (strict != 0 && ignored(skip, this_ch) == 0) {
            radixly_binascii_error(this_ch == PAD ? "Padding not allowed" : "Only base64 data is allowed");
            return -1;
        }
        return 1;
    }
    if (state->pads != 0 && strict != 0 && ignored(skip, PAD) == 0) {
        radixly_binascii_error(state->pos + state->pads == B64_GROUP_CHARS
                                   ? "Excess data after padding"
                                   : "Discontinuous padding not allowed");
        return -1;
    }
    state->pads = 0;
    bits_take(state, value, B64_BITS, B64_GROUP_CHARS);
    return 1;
}

PyObject *
radixly_py315_a2b_base64(const unsigned char *data, Py_ssize_t len, int strict, int padded,
                         const unsigned char *table, const unsigned char *ignore, Py_ssize_t ignore_len,
                         int canonical)
{
    ignore_set skip;
    ignore_set_init(&skip, ignore, strict != 0 ? ignore_len : 0);
    PyObject *result =
        PyBytes_FromStringAndSize(NULL, (Py_ssize_t)groups_bound(len, B64_GROUP_CHARS, B64_GROUP_BYTES));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    bits_state state = {start, start, 0, 0, 0, 0};
    for (Py_ssize_t i = 0; i < len; i++) {
        const int outcome = a2b64_step(&state, data[i], strict, padded, table, &skip);
        if (outcome < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (outcome == 0) {
            break;
        }
    }
    if (state.pos == 1) {
        Py_DECREF(result);
        return radixly_binascii_error_format("Invalid base64-encoded string: number of data characters (%zd) "
                                             "cannot be 1 more than a multiple of 4",
                                             ((state.out - start) / B64_GROUP_BYTES * B64_GROUP_CHARS) + 1);
    }
    if (padded != 0 && state.pos != 0 && state.pos + state.pads < B64_GROUP_CHARS) {
        Py_DECREF(result);
        return radixly_binascii_error("Incorrect padding");
    }
    if (canonical != 0 && state.leftchar != 0) {
        Py_DECREF(result);
        return radixly_binascii_error("Non-zero padding bits");
    }
    return finish(result, state.out - start);
}

PyObject *
radixly_py315_b2a_base64(const unsigned char *data, Py_ssize_t len, int padded, size_t wrapcol, int newline,
                         const unsigned char *alphabet)
{
    size_t out_len = groups_bound(len, B64_GROUP_BYTES, B64_GROUP_CHARS);
    unsigned pads = (unsigned)((B64_GROUP_BYTES - (len % B64_GROUP_BYTES)) % B64_GROUP_BYTES) *
                    B64_GROUP_CHARS / B64_GROUP_BYTES;
    if (padded == 0) {
        out_len -= pads;
        pads = 0;
    }
    if (wrapcol != 0 && out_len != 0) {
        /* Each line should encode a whole number of bytes. */
        wrapcol = wrapcol < B64_GROUP_CHARS ? B64_GROUP_CHARS : wrapcol / B64_GROUP_CHARS * B64_GROUP_CHARS;
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
    unsigned char *out = start;
    Py_ssize_t offset = 0;
    for (; offset + B64_GROUP_BYTES <= len; offset += B64_GROUP_BYTES) {
        out = put_group(out, data + offset, B64_GROUP_BYTES, B64_GROUP_CHARS, B64_BITS, B64_MASK, alphabet);
    }
    if (len > offset) {
        out = put_tail(out, data + offset, len - offset, B64_BITS, B64_MASK, alphabet);
    }
    for (; pads != 0; pads--) {
        *out++ = PAD;
    }
    if (wrapcol != 0) {
        out = start + wraplines(start, out - start, wrapcol);
    }
    if (newline != 0) {
        *out++ = '\n';
    }
    return finish(result, out - start);
}

/* base32 */

/* Indexed by the characters read into the group: after 2, 4, 5 and 7 the bytes are whole and a pad may
 * follow; after 1, 3 and 6 a byte dangles, which binascii refuses outright. */
static const unsigned char B32_PAD_MAY_FOLLOW[B32_GROUP_CHARS] = {0, 0, 1, 0, 1, 1, 0, 1};
static const unsigned char B32_BYTE_DANGLES[B32_GROUP_CHARS] = {0, 1, 0, 1, 0, 0, 1, 0};

static int
a2b32_pad(bits_state *state, ignore_set *skip)
{
    state->pads++;
    if (B32_PAD_MAY_FOLLOW[state->pos] != 0 && state->pos + state->pads <= B32_GROUP_CHARS) {
        return 1;
    }
    if (ignored(skip, PAD) != 0) {
        return 1;
    }
    if (B32_BYTE_DANGLES[state->pos] != 0) {
        return 0;
    }
    radixly_binascii_error(state->pos == 0 && state->out == state->start ? "Leading padding not allowed"
                                                                         : "Excess padding not allowed");
    return -1;
}

static int
a2b32_step(bits_state *state, unsigned char this_ch, int padded, const unsigned char *table, ignore_set *skip)
{
    if (padded != 0 && this_ch == PAD) {
        return a2b32_pad(state, skip);
    }
    const unsigned value = table[this_ch];
    if (value >= B32_SIZE) {
        if (ignored(skip, this_ch) == 0) {
            radixly_binascii_error(this_ch == PAD ? "Padding not allowed" : "Only base32 data is allowed");
            return -1;
        }
        return 1;
    }
    if (state->pads != 0 && ignored(skip, PAD) == 0) {
        radixly_binascii_error(state->pos + state->pads == B32_GROUP_CHARS
                                   ? "Excess data after padding"
                                   : "Discontinuous padding not allowed");
        return -1;
    }
    bits_take(state, value, B32_BITS, B32_GROUP_CHARS);
    // binascii restarts its slow path, pads included, after every whole group.
    if (state->pos == 0) {
        state->pads = 0;
    }
    return 1;
}

PyObject *
radixly_py315_a2b_base32(const unsigned char *data, Py_ssize_t len, int padded, const unsigned char *table,
                         const unsigned char *ignore, Py_ssize_t ignore_len, int canonical)
{
    ignore_set skip;
    ignore_set_init(&skip, ignore, ignore_len);
    PyObject *result =
        PyBytes_FromStringAndSize(NULL, (Py_ssize_t)groups_bound(len, B32_GROUP_CHARS, B32_GROUP_BYTES));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    bits_state state = {start, start, 0, 0, 0, 0};
    for (Py_ssize_t i = 0; i < len; i++) {
        const int outcome = a2b32_step(&state, data[i], padded, table, &skip);
        if (outcome < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (outcome == 0) {
            break;
        }
    }
    if (B32_BYTE_DANGLES[state.pos] != 0) {
        Py_DECREF(result);
        return radixly_binascii_error_format("Invalid base32-encoded string: number of data characters (%zd) "
                                             "cannot be 1, 3, or 6 more than a multiple of 8",
                                             ((state.out - start) / B32_GROUP_BYTES * B32_GROUP_CHARS) +
                                                 (Py_ssize_t)state.pos);
    }
    if (padded != 0 && state.pos != 0 && state.pos + state.pads < B32_GROUP_CHARS) {
        Py_DECREF(result);
        return radixly_binascii_error("Incorrect padding");
    }
    if (canonical != 0 && state.leftchar != 0) {
        Py_DECREF(result);
        return radixly_binascii_error("Non-zero padding bits");
    }
    return finish(result, state.out - start);
}

PyObject *
radixly_py315_b2a_base32(const unsigned char *data, Py_ssize_t len, int padded, size_t wrapcol,
                         const unsigned char *alphabet)
{
    size_t out_len = groups_bound(len, B32_GROUP_BYTES, B32_GROUP_CHARS);
    unsigned pads = (unsigned)((B32_GROUP_BYTES - (len % B32_GROUP_BYTES)) % B32_GROUP_BYTES) *
                    B32_GROUP_CHARS / B32_GROUP_BYTES;
    if (padded == 0) {
        out_len -= pads;
        pads = 0;
    }
    if (wrapcol != 0 && out_len != 0) {
        wrapcol = wrapcol < B32_GROUP_CHARS ? B32_GROUP_CHARS : wrapcol / B32_GROUP_CHARS * B32_GROUP_CHARS;
        out_len += (out_len - 1U) / wrapcol;
    }
    if (out_len > (size_t)PY_SSIZE_T_MAX) {
        return radixly_binascii_error("Too much data for base32");
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    unsigned char *out = start;
    Py_ssize_t offset = 0;
    for (; offset + B32_GROUP_BYTES <= len; offset += B32_GROUP_BYTES) {
        out = put_group(out, data + offset, B32_GROUP_BYTES, B32_GROUP_CHARS, B32_BITS, B32_MASK, alphabet);
    }
    if (len > offset) {
        out = put_tail(out, data + offset, len - offset, B32_BITS, B32_MASK, alphabet);
    }
    for (; pads != 0; pads--) {
        *out++ = PAD;
    }
    if (wrapcol != 0 && out_len != 0) {
        out = start + wraplines(start, out - start, wrapcol);
    }
    return finish(result, out - start);
}

/* base85 and Ascii85 */

/* A tail of count characters (2 to 4) spells count - 1 bytes; the digits must be the encoder's own. */
static int
canonical_tail(uint32_t leftchar, int chunk_len)
{
    const int n_pad = B85_GROUP_BYTES - chunk_len;
    const unsigned shift = BITS_PER_BYTE * (unsigned)n_pad;
    const uint32_t canonical_top = (leftchar >> shift) << shift;
    return canonical_top / POW85[n_pad] == leftchar / POW85[n_pad];
}

static void
put_word(unsigned char **out, uint32_t leftchar, int chunk_len)
{
    for (int i = 0; i < chunk_len; i++) {
        *(*out)++ =
            (unsigned char)((leftchar >> (TOP_BYTE_SHIFT - (BITS_PER_BYTE * (unsigned)i))) & BYTE_MASK);
    }
}

typedef struct {
    unsigned char *out;
    uint32_t leftchar;
    int group_pos;
    int from_z; /* the current group came from 'z' */
} a2b85_state;

/* The digit's place in the word; 1 when the fifth digit would carry the word past 32 bits. */
static int
a2b85_overflows(a2b85_state *state, unsigned digit)
{
    if (state->group_pos == B85_GROUP_CHARS - 1 &&
        (state->leftchar > UINT32_MAX / B85_BASE || state->leftchar * B85_BASE > UINT32_MAX - digit)) {
        return 1;
    }
    state->leftchar = (state->leftchar * B85_BASE) + digit;
    state->group_pos++;
    return 0;
}

/* The bytes of a full group: four, or the one to three a tail spells; 0 is the lone character binascii
 * refuses. */
static int
chunk_length(Py_ssize_t len)
{
    return len < 1 ? B85_GROUP_BYTES - 1 + (int)len : B85_GROUP_BYTES;
}

PyObject *
radixly_py315_a2b_base85(const unsigned char *data, Py_ssize_t len, const unsigned char *table,
                         const unsigned char *ignore, Py_ssize_t ignore_len, int canonical)
{
    ignore_set skip;
    ignore_set_init(&skip, ignore, ignore_len);
    PyObject *result =
        PyBytes_FromStringAndSize(NULL, (Py_ssize_t)groups_bound(len, B85_GROUP_CHARS, B85_GROUP_BYTES));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    a2b85_state state = {start, 0, 0, 0};
    const Py_ssize_t total = len;
    for (; len > 0 || state.group_pos != 0; len--, data++) {
        unsigned char this_ch = 0;
        unsigned digit = B85_TOP_DIGIT; /* the padding digit once the input is spent */
        if (len > 0) {
            this_ch = *data;
            digit = table[this_ch];
        }
        if (digit < B85_BASE) {
            if (a2b85_overflows(&state, digit) != 0) {
                Py_DECREF(result);
                return radixly_binascii_error_format("Base85 overflow in hunk starting at byte %zd",
                                                     (total - len) / B85_GROUP_CHARS * B85_GROUP_CHARS);
            }
        }
        else if (ignored(&skip, this_ch) == 0) {
            Py_DECREF(result);
            return radixly_binascii_error_format("bad Base85 character at position %zd", total - len);
        }
        if (state.group_pos != B85_GROUP_CHARS) {
            continue;
        }
        const int chunk_len = chunk_length(len);
        if (chunk_len == 0) {
            Py_DECREF(result);
            return radixly_binascii_error("Incomplete Base85 group");
        }
        put_word(&state.out, state.leftchar, chunk_len);
        if (canonical != 0 && chunk_len < B85_GROUP_BYTES && canonical_tail(state.leftchar, chunk_len) == 0) {
            Py_DECREF(result);
            return radixly_binascii_error("Non-zero padding bits");
        }
        state.group_pos = 0;
        state.leftchar = 0;
    }
    return finish(result, state.out - start);
}

static void
put_digits(unsigned char *out, uint32_t leftchar, const unsigned char *alphabet, Py_ssize_t group_len)
{
    for (Py_ssize_t i = B85_GROUP_CHARS - 1; i >= 0; i--) {
        if (i < group_len) {
            out[i] = alphabet[leftchar % B85_BASE];
        }
        leftchar /= B85_BASE;
    }
}

static uint32_t
read_word(const unsigned char *data, Py_ssize_t count)
{
    uint32_t leftchar = 0;
    for (Py_ssize_t i = 0; i < B85_GROUP_BYTES; i++) {
        leftchar <<= BITS_PER_BYTE; /* zero past the end */
        if (i < count) {
            leftchar |= data[i];
        }
    }
    return leftchar;
}

/* binascii's bound for an 85 encoding: whole groups, the frame, the dropped padding and the newlines. */
static size_t
bound_85(Py_ssize_t len, size_t wrapcol, int pad, size_t frame)
{
    size_t out_len = groups_bound(len, B85_GROUP_BYTES, B85_GROUP_CHARS) + frame;
    if (pad == 0 && (len % B85_GROUP_BYTES) != 0) {
        out_len -= (size_t)(B85_GROUP_BYTES - (len % B85_GROUP_BYTES));
    }
    if (wrapcol != 0 && out_len != 0 && out_len <= (size_t)PY_SSIZE_T_MAX) {
        out_len += (out_len - 1U) / wrapcol;
    }
    return out_len;
}

PyObject *
radixly_py315_b2a_base85(const unsigned char *data, Py_ssize_t len, int pad, size_t wrapcol,
                         const unsigned char *alphabet)
{
    if (wrapcol != 0) {
        /* Each line should encode a whole number of bytes. */
        wrapcol = wrapcol < B85_GROUP_CHARS ? B85_GROUP_CHARS : wrapcol / B85_GROUP_CHARS * B85_GROUP_CHARS;
    }
    const size_t out_len = bound_85(len, wrapcol, pad, 0);
    if (out_len > (size_t)PY_SSIZE_T_MAX) {
        return radixly_binascii_error("Too much data for Base85");
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    unsigned char *out = start;
    for (; len >= B85_GROUP_BYTES; len -= B85_GROUP_BYTES, data += B85_GROUP_BYTES) {
        put_digits(out, read_word(data, B85_GROUP_BYTES), alphabet, B85_GROUP_CHARS);
        out += B85_GROUP_CHARS;
    }
    if (len > 0) {
        const Py_ssize_t group_len = pad != 0 ? B85_GROUP_CHARS : len + 1;
        put_digits(out, read_word(data, len), alphabet, group_len);
        out += group_len;
    }
    if (wrapcol != 0 && out_len != 0) {
        out = start + wraplines(start, out - start, wrapcol);
    }
    return finish(result, out - start);
}

static const unsigned char A85_ALPHABET[] =
    "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstu";

/* The Ascii85 digit of a byte, or 0xFF: the alphabet runs from '!' to 'u' in order. */
static unsigned
a85_digit(unsigned char this_ch)
{
    return this_ch >= '!' && this_ch <= 'u' ? (unsigned)(this_ch - '!') : INVALID;
}

/* Strip the Adobe frame; -1 with the error set when the "~>" is missing. */
static int
a85_unframe(const unsigned char **data, Py_ssize_t *len)
{
    if (*len < 2 || (*data)[*len - 2] != A85_AFFIX || (*data)[*len - 1] != A85_SUFFIX) {
        radixly_binascii_error("Ascii85 encoded byte sequences must end with b'~>'");
        return -1;
    }
    *len -= 2;
    if (*len >= 2 && (*data)[0] == A85_PREFIX && (*data)[1] == A85_AFFIX) {
        *data += 2;
        *len -= 2;
    }
    return 0;
}

/* One character of a2b_ascii85: the digit, a shorthand, something ignored, or -1 with the error set. */
static int
a2b_a85_step(a2b85_state *state, unsigned char this_ch, unsigned digit, int foldspaces, ignore_set *skip)
{
    if (digit < B85_BASE) {
        if (a2b85_overflows(state, digit) != 0) {
            radixly_binascii_error("Ascii85 overflow");
            return -1;
        }
        return 0;
    }
    if ((this_ch == 'y' && foldspaces != 0) || this_ch == 'z') {
        if (state->group_pos != 0) {
            radixly_binascii_error_format("'%c' inside Ascii85 5-tuple", (int)this_ch);
            return -1;
        }
        state->leftchar = this_ch == 'y' ? A85_Y : A85_Z;
        state->from_z = this_ch == 'z';
        state->group_pos = B85_GROUP_CHARS;
        return 0;
    }
    if (ignored(skip, this_ch) == 0) {
        radixly_binascii_error_format("Non-Ascii85 digit found: %c", (int)this_ch);
        return -1;
    }
    return 0;
}

/* The canonical readings binascii enforces on a full group: 'z' for zero words, the encoder's own tail
 * digits. */
static int
a2b_a85_canonical(const a2b85_state *state, int chunk_len)
{
    if (chunk_len == B85_GROUP_BYTES && state->leftchar == 0 && state->from_z == 0) {
        radixly_binascii_error("Non-canonical encoding, use 'z' for all-zero groups");
        return -1;
    }
    if (chunk_len < B85_GROUP_BYTES && canonical_tail(state->leftchar, chunk_len) == 0) {
        radixly_binascii_error("Non-zero padding bits");
        return -1;
    }
    return 0;
}

/* binascii's bound for a2b_ascii85: every 'y' and 'z' is a word of its own. */
static int
a85_decode_bound(const unsigned char *data, Py_ssize_t len, size_t *bin_len)
{
    size_t count_yz = 0;
    for (Py_ssize_t i = 0; i < len; i++) {
        if (data[i] == 'y' || data[i] == 'z') {
            count_yz++;
        }
    }
    *bin_len = (((size_t)len - count_yz + (size_t)B85_GROUP_BYTES) / (size_t)B85_GROUP_CHARS) *
               (size_t)B85_GROUP_BYTES;
    if (count_yz > ((size_t)PY_SSIZE_T_MAX - *bin_len) / (size_t)B85_GROUP_BYTES) {
        radixly_binascii_error("Too much Ascii85 data");
        return -1;
    }
    *bin_len += count_yz * (size_t)B85_GROUP_BYTES;
    return 0;
}

PyObject *
radixly_py315_a2b_ascii85(const unsigned char *data, Py_ssize_t len, int foldspaces, int adobe,
                          const unsigned char *ignore, Py_ssize_t ignore_len, int canonical)
{
    if (adobe != 0 && a85_unframe(&data, &len) < 0) {
        return NULL;
    }
    ignore_set skip;
    ignore_set_init(&skip, ignore, ignore_len);
    size_t bin_len = 0;
    if (a85_decode_bound(data, len, &bin_len) < 0) {
        return NULL;
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)bin_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    a2b85_state state = {start, 0, 0, 0};
    for (; len > 0 || state.group_pos != 0; len--, data++) {
        unsigned char this_ch = 0;
        unsigned digit = B85_TOP_DIGIT;
        if (len > 0) {
            this_ch = *data;
            digit = a85_digit(this_ch);
        }
        if (a2b_a85_step(&state, this_ch, digit, foldspaces, &skip) < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (state.group_pos != B85_GROUP_CHARS) {
            continue;
        }
        const int chunk_len = chunk_length(len);
        if (chunk_len == 0) {
            Py_DECREF(result);
            return radixly_binascii_error("Incomplete Ascii85 group");
        }
        put_word(&state.out, state.leftchar, chunk_len);
        if (canonical != 0 && a2b_a85_canonical(&state, chunk_len) < 0) {
            Py_DECREF(result);
            return NULL;
        }
        state.from_z = 0;
        state.group_pos = 0;
        state.leftchar = 0;
    }
    return finish(result, state.out - start);
}

/* The words of the input as Ascii85 digits or the z and y shorthands; returns the cursor after them. */
static unsigned char *
a85_words(unsigned char *out, const unsigned char *data, Py_ssize_t len, int foldspaces, int pad)
{
    for (; len >= B85_GROUP_BYTES; len -= B85_GROUP_BYTES, data += B85_GROUP_BYTES) {
        const uint32_t leftchar = read_word(data, B85_GROUP_BYTES);
        if (leftchar == A85_Z) {
            *out++ = 'z';
        }
        else if (foldspaces != 0 && leftchar == A85_Y) {
            *out++ = 'y';
        }
        else {
            put_digits(out, leftchar, A85_ALPHABET, B85_GROUP_CHARS);
            out += B85_GROUP_CHARS;
        }
    }
    if (len > 0) {
        const uint32_t leftchar = read_word(data, len);
        if (pad != 0 && leftchar == A85_Z) {
            *out++ = 'z';
        }
        else {
            const Py_ssize_t group_len = pad != 0 ? B85_GROUP_CHARS : len + 1;
            put_digits(out, leftchar, A85_ALPHABET, group_len);
            out += group_len;
        }
    }
    return out;
}

PyObject *
radixly_py315_b2a_ascii85(const unsigned char *data, Py_ssize_t len, int foldspaces, size_t wrapcol, int pad,
                          int adobe)
{
    if (adobe != 0 && wrapcol == 1) {
        wrapcol = 2;
    }
    const size_t out_len = bound_85(len, wrapcol, pad, adobe != 0 ? A85_FRAME : 0);
    if (out_len > (size_t)PY_SSIZE_T_MAX) {
        return radixly_binascii_error("Too much data for Ascii85");
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    unsigned char *out = start;
    if (adobe != 0) {
        *out++ = A85_PREFIX;
        *out++ = A85_AFFIX;
    }
    out = a85_words(out, data, len, foldspaces, pad);
    if (adobe != 0) {
        *out++ = A85_AFFIX;
        *out++ = A85_SUFFIX;
    }
    if (wrapcol != 0 && out_len != 0) {
        out = start + wraplines(start, out - start, wrapcol);
        /* The "~>" goes on a line of its own when the wrap split it from its text. */
        if (adobe != 0 && out[-2] == '\n') {
            assert(out[-1] == A85_SUFFIX);
            assert(out[-3] == A85_AFFIX);
            out[-3] = '\n';
            out[-2] = A85_AFFIX;
        }
    }
    return finish(result, out - start);
}

/* hexadecimal */

static unsigned
hex_digit(unsigned char this_ch)
{
    if (this_ch >= '0' && this_ch <= '9') {
        return (unsigned)(this_ch - '0');
    }
    if (this_ch >= 'a' && this_ch <= 'f') {
        return (unsigned)(this_ch - 'a') + HEX_LETTER;
    }
    if (this_ch >= 'A' && this_ch <= 'F') {
        return (unsigned)(this_ch - 'A') + HEX_LETTER;
    }
    return INVALID;
}

PyObject *
radixly_py315_a2b_hex(const unsigned char *data, Py_ssize_t len, const unsigned char *ignore,
                      Py_ssize_t ignore_len)
{
    ignore_set skip;
    ignore_set_init(&skip, ignore, ignore_len);
    PyObject *result = PyBytes_FromStringAndSize(NULL, len / HEX_DIGITS_PER_BYTE);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    unsigned char *out = start;
    int pair_pos = 0;
    unsigned leftchar = 0;
    for (Py_ssize_t i = 0; i < len; i++) {
        const unsigned digit = hex_digit(data[i]);
        if (digit >= HEX_BASE) {
            if (ignored(&skip, data[i]) == 0) {
                Py_DECREF(result);
                return radixly_binascii_error("Non-hexadecimal digit found");
            }
            continue;
        }
        if (pair_pos == 0) {
            pair_pos = 1;
            leftchar = digit;
        }
        else {
            pair_pos = 0;
            *out++ = (unsigned char)((leftchar << NIBBLE) | digit);
        }
    }
    if (pair_pos != 0) {
        Py_DECREF(result);
        return radixly_binascii_error("Odd number of hexadecimal digits");
    }
    return finish(result, out - start);
}

static unsigned char *
put_hex(unsigned char *out, unsigned char value)
{
    *out++ = (unsigned char)HEX_UPPER[value >> NIBBLE];
    *out++ = (unsigned char)HEX_UPPER[value & FOUR_BITS];
    return out;
}

PyObject *
radixly_py315_hexlify_upper(const unsigned char *data, Py_ssize_t len, Py_ssize_t bytes_per_sep)
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
    PyObject *result = PyBytes_FromStringAndSize(NULL, (len * HEX_DIGITS_PER_BYTE) + separators);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    if (group == 0) {
        for (Py_ssize_t index = 0; index < len; index++) {
            out = put_hex(out, data[index]);
        }
        return result;
    }
    /* A negative count groups from the left, a positive one from the right; the short group sits at the far
     * end.
     */
    const Py_ssize_t first = bytes_per_sep < 0 ? (Py_ssize_t)group : len - (separators * (Py_ssize_t)group);
    for (Py_ssize_t index = 0; index < first; index++) {
        out = put_hex(out, data[index]);
    }
    for (Py_ssize_t index = first; index < len; index += (Py_ssize_t)group) {
        *out++ = '\n';
        const Py_ssize_t chunk = Py_MIN((Py_ssize_t)group, len - index);
        for (Py_ssize_t k = 0; k < chunk; k++) {
            out = put_hex(out, data[index + k]);
        }
    }
    return result;
}
