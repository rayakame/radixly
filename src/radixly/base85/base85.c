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
#include "base85.h"

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/errors.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 4,
    GROUP_CHARS = 5,
    BASE = 85,
    REV_INVALID = 0xFF,
    TABLE_SIZE = 256,
    PAD_DIGIT = 84, /* the '~' b85decode appends, the largest digit */
    ASCII_MAX = 0x7F,
};

/* 85 to the power of the digits a tail drops: the span of words that share the tail's digits. */
enum { SPAN_1 = BASE, SPAN_2 = BASE * BASE, SPAN_3 = BASE * BASE * BASE, SPAN_4 = BASE * BASE * BASE * BASE };
static const uint64_t DROPPED_SPAN[GROUP_CHARS] = {1, SPAN_1, SPAN_2, SPAN_3, SPAN_4};

static const uint64_t WORD_MAX = 0xFFFFFFFFU;
static const uint32_t FOUR_SPACES = 0x20202020U;

static const char ALPHABET_B85[] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                   "abcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~";
static const char ALPHABET_Z85[] = "0123456789abcdefghijklmnopqrstuvwxyz"
                                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?&<>()[]{}@%$#";
static unsigned char REV_B85[TABLE_SIZE];
static unsigned char REV_Z85[TABLE_SIZE];

int
radixly_base85_exec(PyObject *Py_UNUSED(module))
{
    for (unsigned code = 0; code < TABLE_SIZE; code++) {
        REV_B85[code] = REV_INVALID;
        REV_Z85[code] = REV_INVALID;
    }
    for (unsigned value = 0; value < BASE; value++) {
        REV_B85[(unsigned char)ALPHABET_B85[value]] = (unsigned char)value;
        REV_Z85[(unsigned char)ALPHABET_Z85[value]] = (unsigned char)value;
    }
    return 0;
}

/* Up to four bytes as one big-endian word, the missing ones zero. */
static uint32_t
pack(const unsigned char *source, Py_ssize_t count)
{
    uint32_t word = 0;
    for (Py_ssize_t i = 0; i < GROUP_BYTES; i++) {
        word = (word << BITS_PER_BYTE) | (i < count ? source[i] : 0U);
    }
    return word;
}

/* The five digits of a word, most significant first. */
static void
put_digits(uint32_t word, unsigned char *out, const char *alphabet)
{
    for (int i = GROUP_CHARS - 1; i >= 0; i--) {
        out[i] = (unsigned char)alphabet[word % BASE];
        word /= BASE;
    }
}

/* The encoder's cursor and the two folds the stdlib's list comprehension applies per word. */
typedef struct {
    unsigned char *out;
    int last_chunk_len;
    int folded_spaces; /* -1 until the first word that is not zero, when the stdlib reads foldspaces */
    int fold_nuls;
    PyObject *fold_spaces;
    const char *alphabet;
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
    put_digits(word, state->out, state->alphabet);
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
        for (int i = 0; i < GROUP_CHARS; i++) {
            chunk[i] = (unsigned char)state->alphabet[0];
        }
        state->out = chunk + GROUP_CHARS;
    }
    state->out -= padding;
}

PyObject *
radixly_85_encode(const unsigned char *data, Py_ssize_t len, const char *alphabet, PyObject *pad,
                  int fold_nuls, PyObject *fold_spaces)
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
    encoder state = {out, 0, -1, fold_nuls, fold_spaces, alphabet};
    for (Py_ssize_t index = 0; index < words; index++) {
        const Py_ssize_t offset = GROUP_BYTES * index;
        if (put_word(&state, pack(data + offset, Py_MIN(GROUP_BYTES, len - offset))) < 0) {
            Py_DECREF(result);
            return NULL;
        }
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
    const Py_ssize_t written = state.out - out;
    if (written != GROUP_CHARS * words && _PyBytes_Resize(&result, written) < 0) {
        return NULL; /* result already cleared and the exception set */
    }
    return result;
}

static Py_ssize_t
encoded_len(Py_ssize_t num_bytes)
{
    const Py_ssize_t tail = num_bytes % GROUP_BYTES;
    return (GROUP_CHARS * (num_bytes / GROUP_BYTES)) + (tail != 0 ? tail + 1 : 0);
}

/* The strict encoder: full groups, then a tail of one character more than its bytes. */
PyObject *
radixly_base85_encode_with(PyObject *arg, int zeromq)
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
    const char *alphabet = zeromq ? ALPHABET_Z85 : ALPHABET_B85;
    const unsigned char *data = view.buf;
    unsigned char *out = PyUnicode_1BYTE_DATA(result);
    Py_ssize_t offset = 0;
    for (; offset + GROUP_BYTES <= view.len; offset += GROUP_BYTES) {
        put_digits(pack(data + offset, GROUP_BYTES), out, alphabet);
        out += GROUP_CHARS;
    }
    const Py_ssize_t tail = view.len - offset;
    if (tail != 0) {
        unsigned char digits[GROUP_CHARS];
        put_digits(pack(data + offset, tail), digits, alphabet);
        for (Py_ssize_t i = 0; i <= tail; i++) {
            out[i] = digits[i];
        }
    }
    PyBuffer_Release(&view);
    return result;
}

typedef struct {
    int kind;
    const void *data;
    const unsigned char *rev;
    const char *codec;
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
            const Py_UCS4 code_point = PyUnicode_READ(source->kind, source->data, start + i);
            if (code_point > ASCII_MAX || source->rev[code_point] == REV_INVALID) {
                radixly_raise_decode_error(start + i, "invalid %s character U+%x at index %zd", source->codec,
                                           (unsigned)code_point, start + i);
                return -1;
            }
            value = source->rev[code_point];
        }
        *word = (*word * BASE) + value;
    }
    return 0;
}

/* Write the top count bytes of a word, big-endian. */
static void
unpack(uint64_t word, unsigned char *out, Py_ssize_t count)
{
    for (Py_ssize_t i = 0; i < count; i++) {
        out[i] = (unsigned char)((word >> (BITS_PER_BYTE * (unsigned)(GROUP_BYTES - 1 - i))) & BYTE_MASK);
    }
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
    unpack(rounded, out, payload);
    return 0;
}

/* Strict: characters raise left to right at their own index, a group at its last character. */
PyObject *
radixly_base85_decode_with(PyObject *arg, int zeromq)
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
    const text_source source = {PyUnicode_KIND(arg), PyUnicode_DATA(arg), zeromq ? REV_Z85 : REV_B85,
                                zeromq ? "z85" : "base85"};
    const Py_ssize_t num_groups = num_chars / GROUP_CHARS;
    const Py_ssize_t remainder = num_chars % GROUP_CHARS;
    const Py_ssize_t out_len = (GROUP_BYTES * num_groups) + (remainder != 0 ? remainder - 1 : 0);
    PyObject *result = PyBytes_FromStringAndSize(NULL, out_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    for (Py_ssize_t group = 0; group <= num_groups; group++) {
        const Py_ssize_t start = GROUP_CHARS * group;
        const Py_ssize_t count = group < num_groups ? GROUP_CHARS : remainder;
        if (count == 0) {
            break;
        }
        uint64_t word;
        if (read_group(&source, start, count, &word) < 0) {
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
        if (count == GROUP_CHARS) {
            unpack(word, out + (GROUP_BYTES * group), GROUP_BYTES);
        }
        else if (finish_tail(word, count, last, out + (GROUP_BYTES * group)) < 0) {
            Py_DECREF(result);
            return NULL;
        }
    }
    return result;
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
    return radixly_base85_encode_with(arg, 0);
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
    return radixly_base85_decode_with(arg, 0);
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
radixly_85_decode(const unsigned char *data, Py_ssize_t len, const unsigned char *rev, const char *codec)
{
    if (len > PY_SSIZE_T_MAX - GROUP_CHARS) {
        return PyErr_NoMemory();
    }
    const Py_ssize_t padding = (GROUP_CHARS - (len % GROUP_CHARS)) % GROUP_CHARS;
    const Py_ssize_t chunks = (len + padding) / GROUP_CHARS;
    PyObject *result = PyBytes_FromStringAndSize(NULL, GROUP_BYTES * chunks);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    for (Py_ssize_t chunk = 0; chunk < chunks; chunk++) {
        const Py_ssize_t start = GROUP_CHARS * chunk;
        uint64_t acc = 0;
        for (Py_ssize_t j = 0; j < GROUP_CHARS; j++) {
            const Py_ssize_t position = start + j;
            const unsigned value = position < len ? rev[data[position]] : PAD_DIGIT;
            if (value == REV_INVALID) {
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
        for (int i = 0; i < GROUP_BYTES; i++) {
            out[(GROUP_BYTES * chunk) + i] =
                (unsigned char)((acc >> (BITS_PER_BYTE * (unsigned)(GROUP_BYTES - 1 - i))) & BYTE_MASK);
        }
    }
    const Py_ssize_t out_len = Py_MAX(0, (GROUP_BYTES * chunks) - padding);
    if (out_len != GROUP_BYTES * chunks && _PyBytes_Resize(&result, out_len) < 0) {
        return NULL; /* result already cleared and the exception set */
    }
    return result;
}

/* The stdlib's b85encode and z85encode: memoryview(b).tobytes() for the input, no folding. */
static PyObject *
encode_85(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
          const char *alphabet, const char *param, int with_pad)
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
    PyObject *result = radixly_85_encode(source.data, source.len, alphabet, pad, 0, NULL);
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
    return encode_85("b85encode", args, nargs, kwnames, ALPHABET_B85, "b", 1);
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
    PyObject *result = radixly_85_decode(source.data, source.len, REV_B85, "base85");
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
    return encode_85("z85encode", args, nargs, kwnames, ALPHABET_Z85, "s", 0);
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
    PyObject *result = radixly_85_decode(source.data, source.len, REV_Z85, "base85");
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
