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
#include "base32.h"

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/errors.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 5,
    GROUP_CHARS = 8,
    REV_INVALID = 0xFF,
    PAD = '=',
    NUM_ALPHABETS = 2,
    TABLE_SIZE = 256,
    ASCII_MAX = 0x7F,
};

static const unsigned BITS_PER_CHAR = 5U;
static const unsigned GROUP_BITS = 40U;
static const unsigned CHAR_MASK = 0x1FU;
static const unsigned FIRST_BYTE_SHIFT = 32U; /* the top byte of a 40-bit group */

typedef struct {
    const char *alphabet;
    uint8_t rev[TABLE_SIZE];      /* uppercase only, the strict codec and the compat default */
    uint8_t rev_fold[TABLE_SIZE]; /* lowercase letters as well, the compat casefold */
} alphabet_tables;

static const char ALPHABET_STD[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
static const char ALPHABET_HEX[] = "0123456789ABCDEFGHIJKLMNOPQRSTUV";
static alphabet_tables TABLES[NUM_ALPHABETS];

/* Data characters a padded final group may hold, mapped to the payload bytes they carry; -1 is not a shape.
 */
static const int PAYLOAD_BYTES[GROUP_CHARS + 1] = {-1, -1, 1, -1, 2, 3, -1, 4, 5};

/* The stdlib's leftover bytes for a pad count, its (43 - 5 * padchars) // 8; 0 marks a count it refuses. */
static const int STDLIB_LEFTOVER[GROUP_CHARS + 1] = {0, 4, 0, 3, 2, 0, 1, 0, 0};

int
radixly_base32_exec(PyObject *Py_UNUSED(module))
{
    const char *alphabets[NUM_ALPHABETS] = {ALPHABET_STD, ALPHABET_HEX};
    for (int which = 0; which < NUM_ALPHABETS; which++) {
        alphabet_tables *tables = &TABLES[which];
        tables->alphabet = alphabets[which];
        for (unsigned code = 0; code < TABLE_SIZE; code++) {
            tables->rev[code] = REV_INVALID;
            tables->rev_fold[code] = REV_INVALID;
        }
        for (unsigned value = 0; value < (1U << BITS_PER_CHAR); value++) {
            const unsigned char code = (unsigned char)alphabets[which][value];
            tables->rev[code] = (uint8_t)value;
            tables->rev_fold[code] = (uint8_t)value;
            if (code >= 'A' && code <= 'Z') {
                tables->rev_fold[code - 'A' + 'a'] = (uint8_t)value;
            }
        }
    }
    return 0;
}

static Py_ssize_t
encoded_len(Py_ssize_t num_bytes)
{
    return GROUP_CHARS * ((num_bytes + GROUP_BYTES - 1) / GROUP_BYTES);
}

/* Up to five bytes as one big-endian 40-bit value, the missing ones zero. */
static uint64_t
pack(const unsigned char *source, Py_ssize_t count)
{
    uint64_t acc = 0;
    for (Py_ssize_t i = 0; i < count; i++) {
        acc |= (uint64_t)source[i] << (FIRST_BYTE_SHIFT - (BITS_PER_BYTE * (unsigned)i));
    }
    return acc;
}

/* The top count bytes of a 40-bit value, big-endian. */
static void
unpack(uint64_t acc, unsigned char *out, int count)
{
    for (int i = 0; i < count; i++) {
        out[i] = (unsigned char)((acc >> (FIRST_BYTE_SHIFT - (BITS_PER_BYTE * (unsigned)i))) & BYTE_MASK);
    }
}

/* The top count characters of a 40-bit value. */
static void
put_chars(uint64_t acc, unsigned char *out, int count, const char *alphabet)
{
    for (int i = 0; i < count; i++) {
        const unsigned shift = GROUP_BITS - (BITS_PER_CHAR * ((unsigned)i + 1U));
        out[i] = (unsigned char)alphabet[(acc >> shift) & CHAR_MASK];
    }
}

/* Eight characters per five bytes, the tail zero-padded and finished with '='. */
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
radixly_base32_encode_with(PyObject *arg, int hex)
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
    fill(view.buf, view.len, PyUnicode_1BYTE_DATA(result), TABLES[hex].alphabet);
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

/* Read one group of eight into acc, data_chars being 8 or the index of the first '='; raises on a bad
 * character. */
static int
read_group(const text_source *source, Py_ssize_t base, uint64_t *acc, int *data_chars)
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

/* A padded group is only ever the last one, in the four shapes the encoder produces, with zero pad bits. */
static int
finish_padded(uint64_t acc, int data_chars, Py_ssize_t pad_index, int is_last, unsigned char *out,
              int *written)
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
    radixly_raise_decode_error(num_chars, "length %zd is not a multiple of 8", num_chars);
}

/* Strict RFC 4648; characters raise left to right at their own index. */
PyObject *
radixly_base32_decode_with(PyObject *arg, int hex)
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
    const text_source source = {PyUnicode_KIND(arg), PyUnicode_DATA(arg), TABLES[hex].rev,
                                hex ? "base32hex" : "base32"};
    const Py_ssize_t num_groups = num_chars / GROUP_CHARS;
    const Py_ssize_t remainder = num_chars % GROUP_CHARS;

    PyObject *result = PyBytes_FromStringAndSize(NULL, GROUP_BYTES * num_groups);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    Py_ssize_t out_len = GROUP_BYTES * num_groups;
    for (Py_ssize_t group = 0; group < num_groups; group++) {
        uint64_t acc;
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

PyObject *
radixly_b32encode_with(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                       int hex)
{
    PyObject *arg = NULL;
    radixly_param params[] = {{"s", &arg}};
    if (radixly_bind_args(function, args, nargs, kwnames, params, 1, 1, 1) < 0) {
        return NULL;
    }
    /* The stdlib goes through memoryview(s).tobytes(): any buffer, strided ones copied. */
    radixly_compat_input source;
    if (radixly_compat_buffer_input(arg, &source) < 0) {
        return NULL;
    }
    if (source.len > (PY_SSIZE_T_MAX / GROUP_CHARS) - GROUP_BYTES) {
        radixly_compat_input_release(&source);
        return PyErr_NoMemory();
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, encoded_len(source.len));
    if (result == NULL) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    fill(source.data, source.len, (unsigned char *)PyBytes_AS_STRING(result), TABLES[hex].alphabet);
    radixly_compat_input_release(&source);
    return result;
}

/* Under -O the stdlib's assert is gone and bytes.maketrans raises instead; the drop-in follows the flag. */
static int
optimize_flag(void)
{
    PyObject *flags = PySys_GetObject("flags"); /* borrowed */
    if (flags == NULL) {
        return 0;
    }
    PyObject *optimize = PyObject_GetAttrString(flags, "optimize");
    if (optimize == NULL) {
        PyErr_Clear();
        return 0;
    }
    const long level = PyLong_AsLong(optimize);
    Py_DECREF(optimize);
    if (level == -1 && PyErr_Occurred()) {
        PyErr_Clear();
        return 0;
    }
    return level > 0;
}

/* The stdlib's map01 contract: one byte, or AssertionError showing map01 as _bytes_from_decode_data left it.
 */
static int
map01_byte(PyObject *map01, unsigned char *byte)
{
    radixly_compat_input source;
    if (radixly_compat_decode_input(map01, &source) < 0) {
        return -1;
    }
    if (source.len == 1) {
        *byte = source.data[0];
        radixly_compat_input_release(&source);
        return 0;
    }
    if (optimize_flag()) {
        radixly_compat_input_release(&source);
        PyErr_SetString(PyExc_ValueError, "maketrans arguments must have same length");
        return -1;
    }
    PyObject *shown;
    if (PyBytes_Check(map01) || PyByteArray_Check(map01)) {
        shown = Py_NewRef(map01); /* bytes and bytearray pass through the stdlib's coercion untouched */
    }
    else {
        shown = PyBytes_FromStringAndSize((const char *)source.data, source.len);
    }
    radixly_compat_input_release(&source);
    if (shown == NULL) {
        return -1;
    }
    PyObject *repr = PyObject_Repr(shown);
    Py_DECREF(shown);
    if (repr == NULL) {
        return -1;
    }
    PyErr_SetObject(PyExc_AssertionError, repr);
    Py_DECREF(repr);
    return -1;
}

/* The stdlib's translate() as one table, 0 and 1 mapped; its upper() is the caller's rev_fold table. */
static int
stdlib_translation(PyObject *map01, unsigned char *translate)
{
    for (unsigned code = 0; code < TABLE_SIZE; code++) {
        translate[code] = (unsigned char)code;
    }
    if (map01 != NULL && map01 != Py_None) {
        unsigned char one;
        if (map01_byte(map01, &one) < 0) {
            return -1;
        }
        translate['0'] = 'O';
        translate['1'] = one;
    }
    return 0;
}

/* The stdlib's group loop: every quantum decoded and checked before the padding count is judged. */
static PyObject *
stdlib_decode_groups(const radixly_compat_input *source, Py_ssize_t stripped, const unsigned char *translate,
                     const uint8_t *rev, uint64_t *last_acc)
{
    const Py_ssize_t num_groups = (stripped + GROUP_CHARS - 1) / GROUP_CHARS;
    PyObject *result = PyBytes_FromStringAndSize(NULL, GROUP_BYTES * num_groups);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    uint64_t acc = 0;
    for (Py_ssize_t group = 0; group < num_groups; group++) {
        const Py_ssize_t base = GROUP_CHARS * group;
        const Py_ssize_t chars = Py_MIN(GROUP_CHARS, stripped - base);
        acc = 0;
        for (Py_ssize_t i = 0; i < chars; i++) {
            const uint8_t value = rev[translate[source->data[base + i]]];
            if (value == REV_INVALID) {
                Py_DECREF(result);
                return radixly_binascii_error("Non-base32 digit found");
            }
            acc = (acc << BITS_PER_CHAR) | value;
        }
        unpack(acc, out + (GROUP_BYTES * group), GROUP_BYTES);
    }
    *last_acc = acc;
    return result;
}

/* A faithful port of the stdlib's _b32decode. */
PyObject *
radixly_b32decode_with(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                       int hex)
{
    PyObject *arg = NULL;
    PyObject *casefold = NULL;
    PyObject *map01 = NULL;
    radixly_param params[] = {{"s", &arg}, {"casefold", &casefold}, {"map01", &map01}};
    const Py_ssize_t num_params = hex ? 2 : 3;
    if (radixly_bind_args(function, args, nargs, kwnames, params, num_params, 1, num_params) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    if ((source.len % GROUP_CHARS) != 0) {
        radixly_compat_input_release(&source);
        return radixly_binascii_error("Incorrect padding");
    }
    unsigned char translate[TABLE_SIZE];
    if (stdlib_translation(map01, translate) < 0) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    /* The stdlib reads s and map01 before it looks at casefold, so a flag that raises comes last here too. */
    const int fold = radixly_compat_truth(casefold);
    if (fold < 0) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    /* The stdlib strips '=' after translating, so a map01 of '=' strips the ones it made. */
    Py_ssize_t stripped = source.len;
    while (stripped > 0 && translate[source.data[stripped - 1]] == PAD) {
        stripped--;
    }
    const Py_ssize_t padchars = source.len - stripped;
    uint64_t last_acc = 0;
    PyObject *result = stdlib_decode_groups(&source, stripped, translate,
                                            fold ? TABLES[hex].rev_fold : TABLES[hex].rev, &last_acc);
    radixly_compat_input_release(&source);
    if (result == NULL) {
        return NULL;
    }
    const int leftover = padchars <= GROUP_CHARS ? STDLIB_LEFTOVER[padchars] : 0;
    if (padchars != 0 && leftover == 0) {
        Py_DECREF(result);
        return radixly_binascii_error("Incorrect padding");
    }
    if (padchars != 0 && stripped != 0) {
        const Py_ssize_t last_group = (stripped - 1) / GROUP_CHARS;
        unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
        unpack(last_acc << (BITS_PER_CHAR * (unsigned)padchars), out + (GROUP_BYTES * last_group), leftover);
        if (_PyBytes_Resize(&result, (GROUP_BYTES * last_group) + leftover) < 0) {
            return NULL; /* result already cleared and the exception set */
        }
    }
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
    return radixly_base32_encode_with(arg, 0);
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
    return radixly_base32_decode_with(arg, 0);
}

const char radixly_b32encode_doc[] =
    PyDoc_STR("b32encode($module, /, s)\n"
              "--\n"
              "\n"
              "Encode the bytes-like objects using base32 and return a bytes object.");
PyObject *
radixly_b32encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b32encode_with("b32encode", args, nargs, kwnames, 0);
}

const char radixly_b32decode_doc[] =
    PyDoc_STR("b32decode($module, /, s, casefold=False, map01=None)\n"
              "--\n"
              "\n"
              "Decode the base32 encoded bytes-like object or ASCII string s.\n"
              "\n"
              "Optional casefold is a flag specifying whether a lowercase alphabet is\n"
              "acceptable as input.  For security purposes, the default is False.\n"
              "\n"
              "RFC 3548 allows for optional mapping of the digit 0 (zero) to the\n"
              "letter O (oh), and for optional mapping of the digit 1 (one) to\n"
              "either the letter I (eye) or letter L (el).  The optional argument\n"
              "map01 when not None, specifies which letter the digit 1 should be\n"
              "mapped to (when map01 is not None, the digit 0 is always mapped to\n"
              "the letter O).  For security purposes the default is None, so that\n"
              "0 and 1 are not allowed in the input.\n"
              "\n"
              "The result is returned as a bytes object.  A binascii.Error is raised if\n"
              "the input is incorrectly padded or if there are non-alphabet\n"
              "characters present in the input.");
PyObject *
radixly_b32decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b32decode_with("b32decode", args, nargs, kwnames, 0);
}
