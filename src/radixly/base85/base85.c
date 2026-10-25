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

#include "_common/errors.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 4,
    GROUP_CHARS = 5,
    BASE = 85,
    NUM_ALPHABETS = 3,
    PAIR_TABLE_SIZE = BASE * BASE, /* every two-digit value: two characters */
    ASCII_MAX = 0x7F,
};

static const unsigned NOT_DIGIT = 0x80U; /* set in an invalid cell, clear in every digit */

/* 85 to the power of the digits a tail drops: the span of words that share the tail's digits. */
enum { SPAN_1 = BASE, SPAN_2 = BASE * BASE, SPAN_3 = BASE * BASE * BASE, SPAN_4 = BASE * BASE * BASE * BASE };
static const uint64_t DROPPED_SPAN[GROUP_CHARS] = {1, SPAN_1, SPAN_2, SPAN_3, SPAN_4};
static const uint32_t POW85[GROUP_CHARS] = {1, SPAN_1, SPAN_2, SPAN_3, SPAN_4};
static const uint64_t WORD_MAX = 0xFFFFFFFFU;

static const char ALPHABET_STD[] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                   "abcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~";
static const char ALPHABET_Z85[] = "0123456789abcdefghijklmnopqrstuvwxyz"
                                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?&<>()[]{}@%$#";
static const char ALPHABET_A85[] =
    "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstu";
static const char *const ALPHABETS[NUM_ALPHABETS] = {ALPHABET_STD, ALPHABET_Z85, ALPHABET_A85};

static uint16_t PAIRS[NUM_ALPHABETS]
                     [PAIR_TABLE_SIZE]; /* both digits of a two-digit value, one 16-bit store */
static unsigned char REV[NUM_ALPHABETS][RADIXLY_B85_TABLE_SIZE];

int
radixly_base85_exec(PyObject *Py_UNUSED(module))
{
    memset(REV, RADIXLY_B85_INVALID, sizeof(REV));
    for (int which = 0; which < NUM_ALPHABETS; which++) {
        const char *alphabet = ALPHABETS[which];
        for (unsigned value = 0; value < PAIR_TABLE_SIZE; value++) {
            const unsigned char pair[2] = {
                (unsigned char)alphabet[value / BASE],
                (unsigned char)alphabet[value % BASE],
            };
            memcpy(&PAIRS[which][value], pair, sizeof(pair));
        }
        for (unsigned value = 0; value < BASE; value++) {
            REV[which][(unsigned char)alphabet[value]] = (unsigned char)value;
        }
    }
    return 0;
}

const char *
radixly_b85_alphabet(int which)
{
    return ALPHABETS[which];
}

const unsigned char *
radixly_b85_table(int which)
{
    return REV[which];
}

uint32_t
radixly_b85_word(const unsigned char *data, Py_ssize_t count)
{
    uint32_t word = 0;
    for (Py_ssize_t i = 0; i < GROUP_BYTES; i++) {
        word = (word << BITS_PER_BYTE) | (i < count ? data[i] : 0U);
    }
    return word;
}

void
radixly_b85_put_word(unsigned char *out, uint32_t word, int count)
{
    for (int i = 0; i < count; i++) {
        out[i] = (unsigned char)((word >> (BITS_PER_BYTE * (unsigned)(GROUP_BYTES - 1 - i))) & BYTE_MASK);
    }
}

void
radixly_b85_digits(uint32_t word, unsigned char *out, int which)
{
    const uint16_t *pairs = PAIRS[which];
    const uint32_t upper = word / PAIR_TABLE_SIZE;
    const uint32_t low = word - (upper * PAIR_TABLE_SIZE);
    const uint32_t top = upper / PAIR_TABLE_SIZE;
    const uint32_t middle = upper - (top * PAIR_TABLE_SIZE);
    out[0] = (unsigned char)ALPHABETS[which][top];
    memcpy(out + 1, &pairs[middle], sizeof(uint16_t));
    memcpy(out + 3, &pairs[low], sizeof(uint16_t));
}

Py_ssize_t
radixly_b85_fill(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which)
{
    const unsigned char *cursor = data;
    const unsigned char *end = data + (len - (len % GROUP_BYTES));
    for (; cursor < end; cursor += GROUP_BYTES, out += GROUP_CHARS) {
        const uint32_t word = ((uint32_t)cursor[0] << 24U) | ((uint32_t)cursor[1] << 16U) |
                              ((uint32_t)cursor[2] << 8U) | cursor[3];
        radixly_b85_digits(word, out, which);
    }
    return cursor - data;
}

Py_ssize_t
radixly_b85_groups(const unsigned char *text, Py_ssize_t len, unsigned char *out, const unsigned char *rev,
                   int zero_stops)
{
    const unsigned char *cursor = text;
    const unsigned char *end = text + (len - (len % GROUP_CHARS));
    for (; cursor < end; cursor += GROUP_CHARS, out += GROUP_BYTES) {
        uint64_t word = 0;
        unsigned seen = 0;
        for (int i = 0; i < GROUP_CHARS; i++) {
            const unsigned digit = rev[cursor[i]];
            seen |= digit;
            word = (word * BASE) + digit;
        }
        if ((seen & NOT_DIGIT) != 0 || word > WORD_MAX || (zero_stops != 0 && word == 0)) {
            break;
        }
        radixly_b85_put_word(out, (uint32_t)word, GROUP_BYTES);
    }
    return cursor - text;
}

int
radixly_b85_canonical_tail(uint32_t word, int chunk_len)
{
    const int n_pad = GROUP_BYTES - chunk_len;
    const unsigned shift = BITS_PER_BYTE * (unsigned)n_pad;
    const uint32_t canonical_top = (word >> shift) << shift;
    return canonical_top / POW85[n_pad] == word / POW85[n_pad];
}

static Py_ssize_t
encoded_len(Py_ssize_t num_bytes)
{
    const Py_ssize_t tail = num_bytes % GROUP_BYTES;
    return (GROUP_CHARS * (num_bytes / GROUP_BYTES)) + (tail != 0 ? tail + 1 : 0);
}

/* The strict encoder: full groups, then a tail of one character more than its bytes. */
PyObject *
radixly_base85_encode_with(PyObject *arg, int which)
{
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len == 0) {
        PyBuffer_Release(&view);
        return PyUnicode_New(0, 0);
    }
    if (view.len > (PY_SSIZE_T_MAX / GROUP_CHARS) * GROUP_BYTES) {
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    PyObject *result = PyUnicode_New(encoded_len(view.len), ASCII_MAX);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return NULL;
    }
    const unsigned char *data = view.buf;
    unsigned char *out = PyUnicode_1BYTE_DATA(result);
    const Py_ssize_t whole = radixly_b85_fill(data, view.len, out, which);
    const Py_ssize_t tail = view.len - whole;
    if (tail != 0) {
        unsigned char digits[GROUP_CHARS];
        radixly_b85_digits(radixly_b85_word(data + whole, tail), digits, which);
        memcpy(out + ((whole / GROUP_BYTES) * GROUP_CHARS), digits, (size_t)tail + 1U);
    }
    PyBuffer_Release(&view);
    return result;
}

/* The text as bytes. A 2- or 4-byte str is decoded through the group of its first character outside ASCII,
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

/* Read one group of up to five characters into word, the dropped digits as zero; raises on a bad character.
 */
static int
read_group(const text_source *source, Py_ssize_t start, Py_ssize_t count, uint64_t *word)
{
    *word = 0;
    for (Py_ssize_t i = 0; i < GROUP_CHARS; i++) {
        unsigned value = 0;
        if (i < count) {
            const Py_ssize_t index = start + i;
            value = source->rev[source->text[index]];
            if (value == RADIXLY_B85_INVALID) {
                const Py_UCS4 code_point =
                    index == source->wide_index ? source->wide_code_point : source->text[index];
                radixly_raise_decode_error(index, "invalid %s character U+%x at index %zd", source->codec,
                                           (unsigned)code_point, index);
                return -1;
            }
        }
        *word = (*word * BASE) + value;
    }
    return 0;
}

/* A tail's payload is the one word with zero low bytes among those sharing its digits: the encoder made it,
 * and no other tail spells it. */
static int
finish_tail(uint64_t word, Py_ssize_t count, Py_ssize_t last, unsigned char *out)
{
    const Py_ssize_t payload = count - 1;
    const uint64_t unit = (uint64_t)1 << (BITS_PER_BYTE * (unsigned)(GROUP_BYTES - payload));
    const uint64_t rounded = ((word + unit - 1) / unit) * unit;
    const uint64_t span_end = word + DROPPED_SPAN[GROUP_CHARS - count] - 1;
    if (rounded > span_end || rounded > WORD_MAX) {
        radixly_raise_decode_error(last, "the tail ending at index %zd is not the encoder's spelling", last);
        return -1;
    }
    radixly_b85_put_word(out, (uint32_t)rounded, (int)payload);
    return 0;
}

/* Strict: characters raise left to right at their own index, a group at its last character. */
static PyObject *
decode_text(const text_source *source)
{
    const Py_ssize_t num_chars = source->len;
    const Py_ssize_t remainder = num_chars % GROUP_CHARS;
    const Py_ssize_t out_len =
        (GROUP_BYTES * (num_chars / GROUP_CHARS)) + (remainder != 0 ? remainder - 1 : 0);
    PyObject *result = PyBytes_FromStringAndSize(NULL, out_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    /* Whole groups of digits at speed; the group that stops the run, and the tail, one character at a time.
     */
    Py_ssize_t start = radixly_b85_groups(source->text, num_chars, out, source->rev, 0);
    for (; start < num_chars; start += GROUP_CHARS) {
        const Py_ssize_t count = Py_MIN(GROUP_CHARS, num_chars - start);
        uint64_t word;
        if (read_group(source, start, count, &word) < 0) {
            Py_DECREF(result);
            return NULL;
        }
        const Py_ssize_t last = start + count - 1;
        if (count == 1) {
            Py_DECREF(result);
            return radixly_raise_decode_error(last, "a tail of one character at index %zd carries no byte",
                                              last);
        }
        if (word > WORD_MAX) {
            Py_DECREF(result);
            return radixly_raise_decode_error(last, "the group ending at index %zd exceeds 32 bits", last);
        }
        unsigned char *target = out + (GROUP_BYTES * (start / GROUP_CHARS));
        if (count == GROUP_CHARS) {
            radixly_b85_put_word(target, (uint32_t)word, GROUP_BYTES);
        }
        else if (finish_tail(word, count, last, target) < 0) {
            Py_DECREF(result);
            return NULL;
        }
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
radixly_base85_decode_with(PyObject *arg, int which)
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
        NULL, num_chars, REV[which], which == RADIXLY_B85_Z85 ? "z85" : "base85", -1, 0,
    };
    if (PyUnicode_KIND(arg) != PyUnicode_1BYTE_KIND) {
        return decode_wide(arg, &source);
    }
    source.text = PyUnicode_1BYTE_DATA(arg);
    return decode_text(&source);
}

const char radixly_base85_encode_doc[] =
    PyDoc_STR("base85_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base85 text.\n"
              "\n"
              "The alphabet of RFC 1924 and the standard library's ``b85encode``: five\n"
              "characters per four bytes; a shorter tail becomes one character more\n"
              "than its bytes, so ``n`` bytes become ``5 * (n // 4)`` characters plus\n"
              "``n % 4 + 1`` when ``n`` is not a multiple of four.\n"
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
              ">>> from radixly import base85\n"
              ">>> base85.encode(b'hello')\n"
              "'Xk~0{Zv'\n"
              ">>> base85.decode(base85.encode(b'hello'))\n"
              "b'hello'");
PyObject *
radixly_base85_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base85_encode_with(arg, RADIXLY_B85_STD);
}

const char radixly_base85_decode_doc[] =
    PyDoc_STR("base85_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base85 text back to bytes.\n"
              "\n"
              "Strict: the alphabet only, groups of five, a tail of two to four\n"
              "characters only in the spelling the encoder produces, no group above\n"
              "32 bits.\n"
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
              "    the offending character.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> import radixly\n"
              ">>> try:\n"
              "...     radixly.base85.decode('Xk~0{Zv ')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "7");
PyObject *
radixly_base85_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_base85_decode_with(arg, RADIXLY_B85_STD);
}
