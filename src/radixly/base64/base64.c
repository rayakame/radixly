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

#include "_common/errors.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 3,
    GROUP_CHARS = 4,
    PAD = '=',
    NUM_ALPHABETS = 2,
    ALPHABET_SIZE = 64,
    PAIR_TABLE_SIZE = 4096, /* every 12-bit value: two characters */
    ASCII_MAX = 0x7F,
};

static const unsigned BITS_PER_CHAR = 6U;
static const unsigned PAIR_BITS = 12U;
static const unsigned CHAR_MASK = 0x3FU;
static const unsigned PAIR_MASK = 0xFFFU;
static const unsigned NOT_DATA =
    0xC0U; /* set in the pad value and in an invalid cell, clear in every value */

static const char ALPHABET_STD[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static const char ALPHABET_URL[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
static const char *const ALPHABETS[NUM_ALPHABETS] = {ALPHABET_STD, ALPHABET_URL};

static uint16_t PAIRS[NUM_ALPHABETS]
                     [PAIR_TABLE_SIZE]; /* both characters of a 12-bit value, one 16-bit store */
static unsigned char REV[NUM_ALPHABETS][RADIXLY_B64_TABLE_SIZE];

/* Data characters a padded final group may hold, mapped to the payload bytes they carry; -1 is not a shape.
 */
static const int PAYLOAD_BYTES[GROUP_CHARS + 1] = {-1, -1, 1, 2, 3};

void
radixly_b64_reverse_table(const unsigned char *alphabet, unsigned char table[RADIXLY_B64_TABLE_SIZE])
{
    memset(table, RADIXLY_B64_INVALID, RADIXLY_B64_TABLE_SIZE);
    for (unsigned value = 0; value < ALPHABET_SIZE; value++) {
        table[alphabet[value]] = (unsigned char)value;
    }
    table[PAD] = RADIXLY_B64_PAD_VALUE;
}

int
radixly_base64_exec(PyObject *Py_UNUSED(module))
{
    for (int which = 0; which < NUM_ALPHABETS; which++) {
        const char *alphabet = ALPHABETS[which];
        for (unsigned value = 0; value < PAIR_TABLE_SIZE; value++) {
            const unsigned char pair[2] = {
                (unsigned char)alphabet[value >> BITS_PER_CHAR],
                (unsigned char)alphabet[value & CHAR_MASK],
            };
            memcpy(&PAIRS[which][value], pair, sizeof(pair));
        }
        radixly_b64_reverse_table((const unsigned char *)alphabet, REV[which]);
    }
    return 0;
}

const char *
radixly_b64_alphabet(int which)
{
    return ALPHABETS[which];
}

const unsigned char *
radixly_b64_table(int which)
{
    return REV[which];
}

Py_ssize_t
radixly_b64_fill(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which)
{
    const uint16_t *pairs = PAIRS[which];
    const unsigned char *cursor = data;
    const unsigned char *end = data + (len - (len % GROUP_BYTES));
    for (; cursor < end; cursor += GROUP_BYTES, out += GROUP_CHARS) {
        const unsigned group = ((unsigned)cursor[0] << (2U * BITS_PER_BYTE)) |
                               ((unsigned)cursor[1] << BITS_PER_BYTE) | cursor[2];
        memcpy(out, &pairs[group >> PAIR_BITS], sizeof(uint16_t));
        memcpy(out + 2, &pairs[group & PAIR_MASK], sizeof(uint16_t));
    }
    return cursor - data;
}

int
radixly_b64_tail(const unsigned char *data, Py_ssize_t leftover, unsigned char *out, int which)
{
    const char *alphabet = ALPHABETS[which];
    if (leftover == 1) {
        const unsigned value = data[0];
        out[0] = (unsigned char)alphabet[value >> 2U];
        out[1] = (unsigned char)alphabet[(value << 4U) & CHAR_MASK];
        return 2;
    }
    if (leftover == 2) {
        const unsigned value = ((unsigned)data[0] << BITS_PER_BYTE) | data[1];
        out[0] = (unsigned char)alphabet[value >> ((2U * BITS_PER_BYTE) - BITS_PER_CHAR)];
        out[1] = (unsigned char)alphabet[(value >> 4U) & CHAR_MASK];
        out[2] = (unsigned char)alphabet[(value << 2U) & CHAR_MASK];
        return 3;
    }
    return 0;
}

void
radixly_b64_encode(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which)
{
    const Py_ssize_t whole = radixly_b64_fill(data, len, out, which);
    if (whole < len) {
        out += (whole / GROUP_BYTES) * GROUP_CHARS;
        for (int written = radixly_b64_tail(data + whole, len - whole, out, which); written < GROUP_CHARS;
             written++) {
            out[written] = PAD;
        }
    }
}

Py_ssize_t
radixly_b64_quads(const unsigned char *text, Py_ssize_t len, unsigned char *out, const unsigned char *rev)
{
    const unsigned char *cursor = text;
    const unsigned char *end = text + (len - (len % GROUP_CHARS));
    for (; cursor < end; cursor += GROUP_CHARS, out += GROUP_BYTES) {
        const unsigned sextet0 = rev[cursor[0]];
        const unsigned sextet1 = rev[cursor[1]];
        const unsigned sextet2 = rev[cursor[2]];
        const unsigned sextet3 = rev[cursor[3]];
        if (((sextet0 | sextet1 | sextet2 | sextet3) & NOT_DATA) != 0) {
            break;
        }
        out[0] = (unsigned char)((sextet0 << 2U) | (sextet1 >> 4U));
        out[1] = (unsigned char)((sextet1 << 4U) | (sextet2 >> 2U));
        out[2] = (unsigned char)((sextet2 << BITS_PER_CHAR) | sextet3);
    }
    return cursor - text;
}

Py_ssize_t
radixly_b64_decode_bound(const unsigned char *text, Py_ssize_t len, const unsigned char *rev)
{
    Py_ssize_t bound = GROUP_BYTES * ((len + GROUP_CHARS - 1) / GROUP_CHARS);
    if ((len % GROUP_CHARS) == 0 && rev[PAD] == RADIXLY_B64_PAD_VALUE) {
        /* A trailing pad is never data; the shrink that saves is the common one, so no resize follows. */
        for (Py_ssize_t i = len - 1; i >= len - 2 && i >= 0 && text[i] == PAD; i--) {
            bound--;
        }
    }
    return bound;
}

static Py_ssize_t
encoded_len(Py_ssize_t num_bytes)
{
    return GROUP_CHARS * ((num_bytes + GROUP_BYTES - 1) / GROUP_BYTES);
}

PyObject *
radixly_base64_encode_with(PyObject *arg, int which)
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
    radixly_b64_encode(view.buf, view.len, PyUnicode_1BYTE_DATA(result), which);
    PyBuffer_Release(&view);
    return result;
}

/* The text as bytes. A 2- or 4-byte str is decoded up to and including its first character outside ASCII,
 * which an invalid placeholder stands in for; wide_index says where, so the error names the real character.
 */
typedef struct {
    const unsigned char *text;
    Py_ssize_t len;
    const unsigned char *rev;
    const char *codec;
    Py_ssize_t wide_index;
    Py_UCS4 wide_code_point;
} text_source;

static int
raise_invalid(const text_source *source, Py_ssize_t index)
{
    const Py_UCS4 code_point = index == source->wide_index ? source->wide_code_point : source->text[index];
    radixly_raise_decode_error(index, "invalid %s character U+%x at index %zd", source->codec,
                               (unsigned)code_point, index);
    return -1;
}

/* Read the group at base into acc, data_chars being 4 or the index of the first '='; raises on a bad
 * character. */
static int
read_group(const text_source *source, Py_ssize_t base, uint32_t *acc, int *data_chars)
{
    *acc = 0;
    *data_chars = GROUP_CHARS;
    for (int i = 0; i < GROUP_CHARS; i++) {
        const unsigned char code = source->text[base + i];
        const unsigned value = source->rev[code];
        if (value == RADIXLY_B64_PAD_VALUE) {
            if (*data_chars == GROUP_CHARS) {
                *data_chars = i;
            }
            continue;
        }
        if (value == RADIXLY_B64_INVALID) {
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

/* A padded group is only ever the last one, in the two shapes the encoder produces, with zero pad bits. */
static int
finish_padded(uint32_t acc, int data_chars, Py_ssize_t pad_index, int is_last, unsigned char *out)
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
    acc <<= BITS_PER_CHAR * (unsigned)(GROUP_CHARS - data_chars);
    for (int i = 0; i < payload; i++) {
        out[i] = (unsigned char)((acc >> (BITS_PER_BYTE * (unsigned)(2 - i))) & BYTE_MASK);
    }
    return 0;
}

/* The characters after the last full group are still checked, so an invalid one reports its own index. */
static void
raise_for_remainder(const text_source *source, Py_ssize_t start)
{
    for (Py_ssize_t i = start; i < source->len; i++) {
        const unsigned value = source->rev[source->text[i]];
        if (value == RADIXLY_B64_PAD_VALUE) {
            radixly_raise_decode_error(i, "padding at index %zd in an incomplete group", i);
            return;
        }
        if (value == RADIXLY_B64_INVALID) {
            raise_invalid(source, i);
            return;
        }
    }
    radixly_raise_decode_error(source->len, "length %zd is not a multiple of 4", source->len);
}

/* Strict RFC 4648; characters raise left to right at their own index. */
static PyObject *
decode_text(const text_source *source)
{
    const Py_ssize_t num_chars = source->len;
    const Py_ssize_t whole = GROUP_CHARS * (num_chars / GROUP_CHARS);
    PyObject *result =
        PyBytes_FromStringAndSize(NULL, radixly_b64_decode_bound(source->text, num_chars, source->rev));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    const Py_ssize_t consumed = radixly_b64_quads(source->text, whole, out, source->rev);
    if (consumed < whole) {
        /* The group that stopped the run holds a pad or an invalid character: the last group, or an error. */
        uint32_t acc;
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

/* A 2- or 4-byte str holds a character outside ASCII, so the decode ends in an error at or before it. The
 * text through the end of that character's group is decoded as bytes, an invalid placeholder standing in from
 * the character on, so every earlier error keeps its place and the group shapes stay what they were. */
static PyObject *
decode_wide(PyObject *arg, text_source *source)
{
    const int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);
    const Py_ssize_t num_chars = PyUnicode_GET_LENGTH(arg);
    Py_ssize_t wide = 0;
    while (wide < num_chars && PyUnicode_READ(kind, data, wide) <= ASCII_MAX) {
        wide++;
    }
    if (wide == num_chars) {
        PyErr_SetString(PyExc_SystemError, "a non-ASCII str kind held only ASCII characters");
        return NULL;
    }
    const Py_ssize_t len = Py_MIN(num_chars, GROUP_CHARS * ((wide / GROUP_CHARS) + 1));
    unsigned char *text = PyMem_Malloc((size_t)len);
    if (text == NULL) {
        return PyErr_NoMemory();
    }
    for (Py_ssize_t i = 0; i < wide; i++) {
        text[i] = (unsigned char)PyUnicode_READ(kind, data, i);
    }
    memset(text + wide, ASCII_MAX + 1, (size_t)(len - wide)); /* never in an alphabet */
    source->text = text;
    source->len = len;
    source->wide_index = wide;
    source->wide_code_point = PyUnicode_READ(kind, data, wide);
    PyObject *result = decode_text(source);
    PyMem_Free(text);
    assert(result == NULL);
    return result;
}

PyObject *
radixly_base64_decode_with(PyObject *arg, int which)
{
    if (!PyUnicode_Check(arg)) {
        PyErr_Format(PyExc_TypeError, "expected str, not %.200s", Py_TYPE(arg)->tp_name);
        return NULL;
    }
#if PY_VERSION_HEX < 0x030C0000
    /* 3.11 can still meet legacy, non-ready strings; GET_LENGTH/KIND/DATA on one is UB. Compiles out
     * on 3.12+. */
    if (PyUnicode_READY(arg) == -1) {
        return NULL;
    }
#endif
    const Py_ssize_t num_chars = PyUnicode_GET_LENGTH(arg);
    if (num_chars == 0) {
        return PyBytes_FromStringAndSize("", 0);
    }
    text_source source = {
        NULL, num_chars, REV[which], which == RADIXLY_B64_URL ? "base64url" : "base64", -1, 0,
    };
    if (PyUnicode_KIND(arg) != PyUnicode_1BYTE_KIND) {
        return decode_wide(arg, &source);
    }
    source.text = PyUnicode_1BYTE_DATA(arg);
    return decode_text(&source);
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
    return radixly_base64_encode_with(arg, RADIXLY_B64_STD);
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
    return radixly_base64_decode_with(arg, RADIXLY_B64_STD);
}
