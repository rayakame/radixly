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
#include "base32.h"

#include "_common/errors.h"
#include "_common/internal.h"
#include "_common/text.h"

enum {
    GROUP_BYTES = 5,
    GROUP_CHARS = 8,
    PAD = '=',
    NUM_ALPHABETS = 2,
    ALPHABET_SIZE = 32,
    PAIR_TABLE_SIZE = 1024, /* every 10-bit value: two characters */
    ASCII_MAX = 0x7F,
};

static const unsigned BITS_PER_CHAR = 5U;
static const unsigned PAIR_BITS = 10U;
static const unsigned CHAR_MASK = 0x1FU;
static const unsigned PAIR_MASK = 0x3FFU;
static const unsigned NOT_DATA =
    0xE0U; /* set in the pad value and in an invalid cell, clear in every value */

static const char ALPHABET_STD[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
static const char ALPHABET_HEX[] = "0123456789ABCDEFGHIJKLMNOPQRSTUV";
static const char *const ALPHABETS[NUM_ALPHABETS] = {ALPHABET_STD, ALPHABET_HEX};

static uint16_t PAIRS[NUM_ALPHABETS]
                     [PAIR_TABLE_SIZE]; /* both characters of a 10-bit value, one 16-bit store */
static unsigned char REV[NUM_ALPHABETS][RADIXLY_B32_TABLE_SIZE];
static unsigned char REV_FOLD[NUM_ALPHABETS][RADIXLY_B32_TABLE_SIZE];

/* Data characters a padded final group may hold, mapped to the payload bytes they carry; -1 is not a shape.
 */
static const int PAYLOAD_BYTES[GROUP_CHARS + 1] = {-1, -1, 1, -1, 2, 3, -1, 4, 5};

int
radixly_base32_exec(PyObject *Py_UNUSED(module))
{
    memset(REV, RADIXLY_B32_INVALID, sizeof(REV));
    memset(REV_FOLD, RADIXLY_B32_INVALID, sizeof(REV_FOLD));
    for (int which = 0; which < NUM_ALPHABETS; which++) {
        const char *alphabet = ALPHABETS[which];
        for (unsigned value = 0; value < PAIR_TABLE_SIZE; value++) {
            const unsigned char pair[2] = {
                (unsigned char)alphabet[value >> BITS_PER_CHAR],
                (unsigned char)alphabet[value & CHAR_MASK],
            };
            memcpy(&PAIRS[which][value], pair, sizeof(pair));
        }
        for (unsigned value = 0; value < ALPHABET_SIZE; value++) {
            const unsigned char code = (unsigned char)alphabet[value];
            REV[which][code] = (unsigned char)value;
            REV_FOLD[which][code] = (unsigned char)value;
            REV_FOLD[which][Py_TOLOWER(code)] = (unsigned char)value;
        }
        REV[which][PAD] = RADIXLY_B32_PAD_VALUE;
        REV_FOLD[which][PAD] = RADIXLY_B32_PAD_VALUE;
    }
    return 0;
}

const char *
radixly_b32_alphabet(int which)
{
    return ALPHABETS[which];
}

const unsigned char *
radixly_b32_table(int which)
{
    return REV[which];
}

const unsigned char *
radixly_b32_fold_table(int which)
{
    return REV_FOLD[which];
}

Py_ssize_t
radixly_b32_fill(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which)
{
    const uint16_t *pairs = PAIRS[which];
    const unsigned char *cursor = data;
    const unsigned char *end = data + (len - (len % GROUP_BYTES));
    for (; cursor < end; cursor += GROUP_BYTES, out += GROUP_CHARS) {
        const uint64_t group = ((uint64_t)cursor[0] << 32U) | ((uint64_t)cursor[1] << 24U) |
                               ((uint64_t)cursor[2] << 16U) | ((uint64_t)cursor[3] << 8U) | cursor[4];
        for (size_t pair = 0; pair < GROUP_CHARS / 2; pair++) {
            memcpy(out + (2 * pair), &pairs[(group >> ((3U - pair) * PAIR_BITS)) & PAIR_MASK],
                   sizeof(uint16_t));
        }
    }
    return cursor - data;
}

int
radixly_b32_tail(const unsigned char *data, Py_ssize_t leftover, unsigned char *out, int which)
{
    const char *alphabet = ALPHABETS[which];
    const int chars = (int)(((BITS_PER_BYTE * (unsigned)leftover) + BITS_PER_CHAR - 1U) / BITS_PER_CHAR);
    uint64_t group = 0;
    for (Py_ssize_t i = 0; i < leftover; i++) {
        group = (group << BITS_PER_BYTE) | data[i];
    }
    group <<= (BITS_PER_CHAR * (unsigned)chars) - (BITS_PER_BYTE * (unsigned)leftover);
    for (int i = chars - 1; i >= 0; i--) {
        out[i] = (unsigned char)alphabet[group & CHAR_MASK];
        group >>= BITS_PER_CHAR;
    }
    return chars;
}

void
radixly_b32_encode(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which)
{
    const Py_ssize_t whole = radixly_b32_fill(data, len, out, which);
    if (whole < len) {
        out += (whole / GROUP_BYTES) * GROUP_CHARS;
        for (int written = radixly_b32_tail(data + whole, len - whole, out, which); written < GROUP_CHARS;
             written++) {
            out[written] = PAD;
        }
    }
}

Py_ssize_t
radixly_b32_octas(const unsigned char *text, Py_ssize_t len, unsigned char *out, const unsigned char *rev)
{
    const unsigned char *cursor = text;
    const unsigned char *end = text + (len - (len % GROUP_CHARS));
    for (; cursor < end; cursor += GROUP_CHARS, out += GROUP_BYTES) {
        uint64_t acc = 0;
        unsigned seen = 0;
        for (int i = 0; i < GROUP_CHARS; i++) {
            const unsigned quint = rev[cursor[i]];
            seen |= quint;
            acc = (acc << BITS_PER_CHAR) | quint;
        }
        if ((seen & NOT_DATA) != 0) {
            break;
        }
        for (int i = 0; i < GROUP_BYTES; i++) {
            out[i] = (unsigned char)((acc >> (BITS_PER_BYTE * (unsigned)(GROUP_BYTES - 1 - i))) & BYTE_MASK);
        }
    }
    return cursor - text;
}

Py_ssize_t
radixly_b32_decode_bound(const unsigned char *text, Py_ssize_t len, const unsigned char *rev)
{
    const Py_ssize_t groups = (len + GROUP_CHARS - 1) / GROUP_CHARS;
    if ((len % GROUP_CHARS) != 0 || groups == 0 || rev[PAD] != RADIXLY_B32_PAD_VALUE) {
        return GROUP_BYTES * groups;
    }
    /* A trailing pad is never data: the last group carries floor(5 * data / 8) bytes at most. */
    int pads = 0;
    while (pads < GROUP_CHARS && text[len - 1 - pads] == PAD) {
        pads++;
    }
    return (GROUP_BYTES * (groups - 1)) +
           (int)((BITS_PER_CHAR * (unsigned)(GROUP_CHARS - pads)) / BITS_PER_BYTE);
}

static Py_ssize_t
encoded_len(Py_ssize_t num_bytes)
{
    return GROUP_CHARS * ((num_bytes + GROUP_BYTES - 1) / GROUP_BYTES);
}

PyObject *
radixly_base32_encode_with(PyObject *arg, int which)
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
    radixly_b32_encode(view.buf, view.len, PyUnicode_1BYTE_DATA(result), which);
    PyBuffer_Release(&view);
    return result;
}

typedef struct {
    const radixly_text *text;
    const unsigned char *rev;
    const char *codec;
} text_source;

static int
raise_invalid(const text_source *source, Py_ssize_t index)
{
    const Py_UCS4 code_point = radixly_text_code_point(source->text, index);
    radixly_raise_decode_error(index, "invalid %s character U+%x at index %zd", source->codec,
                               (unsigned)code_point, index);
    return -1;
}

/* Read the group at base into acc, data_chars being 8 or the index of the first '='; raises on a bad
 * character. */
static int
read_group(const text_source *source, Py_ssize_t base, uint64_t *acc, int *data_chars)
{
    *acc = 0;
    *data_chars = GROUP_CHARS;
    for (int i = 0; i < GROUP_CHARS; i++) {
        const unsigned char code = source->text->text[base + i];
        const unsigned value = source->rev[code];
        if (value == RADIXLY_B32_PAD_VALUE) {
            if (*data_chars == GROUP_CHARS) {
                *data_chars = i;
            }
            continue;
        }
        if (value == RADIXLY_B32_INVALID) {
            return raise_invalid(source, base + i);
        }
        if (*data_chars != GROUP_CHARS) {
            radixly_raise_decode_error(base + i, "data character U+%x at index %zd after padding",
                                       (unsigned)code, base + i);
            return -1;
        }
        *acc = (*acc << BITS_PER_CHAR) | value;
    }
    return 0;
}

/* A padded group is only ever the last one, in the four shapes the encoder produces, with zero pad bits. */
static int
finish_padded(uint64_t acc, int data_chars, Py_ssize_t pad_index, int is_last, unsigned char *out)
{
    if (!is_last) {
        radixly_raise_decode_error(pad_index, "padding at index %zd before the end of the text", pad_index);
        return -1;
    }
    const int payload = PAYLOAD_BYTES[data_chars];
    if (payload < 0) {
        radixly_raise_decode_error(pad_index,
                                   "%d data characters before the padding at index %zd, not 2, 4, 5 or 7",
                                   data_chars, pad_index);
        return -1;
    }
    const unsigned pad_bits = (BITS_PER_CHAR * (unsigned)data_chars) - (BITS_PER_BYTE * (unsigned)payload);
    if ((acc & ((1U << pad_bits) - 1U)) != 0) {
        radixly_raise_decode_error(pad_index - 1, "%u padding bits not zero in the character at index %zd",
                                   pad_bits, pad_index - 1);
        return -1;
    }
    acc <<= BITS_PER_CHAR * (unsigned)(GROUP_CHARS - data_chars);
    for (int i = 0; i < payload; i++) {
        out[i] = (unsigned char)((acc >> (BITS_PER_BYTE * (unsigned)(GROUP_BYTES - 1 - i))) & BYTE_MASK);
    }
    return 0;
}

/* The characters after the last full group are still checked, so an invalid one reports its own index. */
static void
raise_for_remainder(const text_source *source, Py_ssize_t start)
{
    for (Py_ssize_t i = start; i < source->text->len; i++) {
        const unsigned value = source->rev[source->text->text[i]];
        if (value == RADIXLY_B32_PAD_VALUE) {
            radixly_raise_decode_error(i, "padding at index %zd in an incomplete group", i);
            return;
        }
        if (value == RADIXLY_B32_INVALID) {
            raise_invalid(source, i);
            return;
        }
    }
    radixly_raise_decode_error(source->text->len, "length %zd is not a multiple of 8", source->text->len);
}

/* Strict RFC 4648; characters raise left to right at their own index. */
static PyObject *
decode_text(const text_source *source)
{
    const Py_ssize_t num_chars = source->text->len;
    const Py_ssize_t whole = GROUP_CHARS * (num_chars / GROUP_CHARS);
    PyObject *result =
        PyBytes_FromStringAndSize(NULL, radixly_b32_decode_bound(source->text->text, num_chars, source->rev));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    const Py_ssize_t consumed = radixly_b32_octas(source->text->text, whole, out, source->rev);
    if (consumed < whole) {
        /* The group that stopped the run holds a pad or an invalid character: the last group, or an error. */
        uint64_t acc;
        int data_chars;
        if (read_group(source, consumed, &acc, &data_chars) < 0 ||
            finish_padded(acc, data_chars, consumed + data_chars, consumed + GROUP_CHARS == num_chars,
                          out + (GROUP_BYTES * (consumed / GROUP_CHARS))) < 0) {
            Py_DECREF(result);
            return NULL;
        }
    }
    else if (whole != num_chars) {
        Py_DECREF(result);
        raise_for_remainder(source, whole);
        return NULL;
    }
    return result;
}

PyObject *
radixly_base32_decode_with(PyObject *arg, int which)
{
    radixly_text text;
    if (radixly_text_init(&text, arg, GROUP_CHARS) < 0) {
        return NULL;
    }
    PyObject *result;
    if (text.len == 0) {
        result = PyBytes_FromStringAndSize("", 0);
    }
    else {
        const text_source source = {&text, REV[which], which == RADIXLY_B32_HEX ? "base32hex" : "base32"};
        result = decode_text(&source);
    }
    radixly_text_release(&text);
    return result;
}

const char radixly_base32_encode_doc[] =
    PyDoc_STR("base32_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base32 text.\n"
              "\n"
              "RFC 4648 section 6: eight characters per five bytes, a shorter tail\n"
              "padded with ``=`` to a full group. ``n`` bytes become\n"
              "``8 * ceil(n / 5)`` characters.\n"
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
              ">>> from radixly import base32\n"
              ">>> base32.encode(b'hi')\n"
              "'NBUQ===='\n"
              ">>> base32.decode(base32.encode(b'hi'))\n"
              "b'hi'");
PyObject *
radixly_base32_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base32_encode_with(arg, RADIXLY_B32_STD);
}

const char radixly_base32_decode_doc[] =
    PyDoc_STR("base32_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base32 text back to bytes.\n"
              "\n"
              "Strict RFC 4648: uppercase alphabet only, groups of eight, padding only\n"
              "at the end in the four shapes the encoder produces, pad bits zero.\n"
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
              "...     radixly.base32.decode('nbuq====')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "0");
PyObject *
radixly_base32_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base32_decode_with(arg, RADIXLY_B32_STD);
}
