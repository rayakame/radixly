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
#include "ascii85.h"

#include "base85/base85.h"

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 4,
    GROUP_CHARS = 5,
    BASE = 85,
    FIRST = '!', /* the alphabet is the 85 characters from '!' */
    LAST = 'u',
    TABLE_SIZE = 256,
    FRAME = 2,      /* the "<~" and "~>" markers */
    FRAME_BOTH = 4, /* both of them */
};

static const uint64_t WORD_MAX = 0xFFFFFFFFU;
static const uint32_t FOUR_SPACES = 0x20202020U;
static const char ALPHABET_A85[] =
    "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstu";
static const char DEFAULT_IGNORED[] = " \t\n\r\v";

/* The stdlib's max(2 if adobe else 1, wrapcol) then range(0, n, wrapcol): the comparison's own TypeError for
 * a value that is not ordered against int, __index__'s for one that is not an integer, the ssize maximum for
 * one too large to matter. */
static Py_ssize_t
wrap_width(PyObject *wrapcol, int adobe)
{
    PyObject *floor = PyLong_FromLong(adobe ? FRAME : 1);
    if (floor == NULL) {
        return -1;
    }
    const int larger = PyObject_RichCompareBool(wrapcol, floor, Py_GT);
    if (larger < 0) {
        Py_DECREF(floor);
        return -1;
    }
    PyObject *chosen = larger ? wrapcol : floor;
    const Py_ssize_t width = PyNumber_AsSsize_t(chosen, NULL);
    Py_DECREF(floor);
    return width;
}

/* The line breaks the stdlib's wrapping inserts into text_len characters, the "~>" line of its own included.
 */
static Py_ssize_t
count_breaks(Py_ssize_t text_len, int adobe, Py_ssize_t width)
{
    if (width <= 0 || text_len == 0) {
        return 0;
    }
    const Py_ssize_t lines = ((text_len - 1) / width) + 1;
    const Py_ssize_t last = text_len - (width * (lines - 1));
    const Py_ssize_t closing_line = adobe && last + FRAME > width ? 1 : 0;
    return lines - 1 + closing_line;
}

/* Copy the prefix and the body into out as one text with a newline after every width characters; returns the
 * count written. */
static Py_ssize_t
write_wrapped(unsigned char *out, const unsigned char *prefix, Py_ssize_t prefix_len,
              const unsigned char *body, Py_ssize_t body_len, Py_ssize_t width)
{
    Py_ssize_t written = 0;
    for (Py_ssize_t i = 0; i < prefix_len + body_len; i++) {
        if (width > 0 && i != 0 && i % width == 0) {
            out[written++] = '\n';
        }
        out[written++] = i < prefix_len ? prefix[i] : body[i - prefix_len];
    }
    return written;
}

/* The stdlib's framing and wrapping of the raw text: "<~" first, lines of width, "~>" on its own line when
 * the last one has no room for it. */
static PyObject *
frame_and_wrap(PyObject *raw, int adobe, Py_ssize_t width)
{
    const Py_ssize_t raw_len = PyBytes_GET_SIZE(raw);
    assert(raw_len >= 0 && width >= 0);
    if (raw_len > (PY_SSIZE_T_MAX / 2) - FRAME_BOTH) {
        return PyErr_NoMemory();
    }
    const Py_ssize_t prefix_len = adobe ? FRAME : 0;
    const Py_ssize_t text_len = raw_len + prefix_len;
    const Py_ssize_t lines_end = text_len + count_breaks(text_len, adobe, width);
    PyObject *result = PyBytes_FromStringAndSize(NULL, lines_end + prefix_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    Py_ssize_t written = write_wrapped(out, (const unsigned char *)"<~", prefix_len,
                                       (const unsigned char *)PyBytes_AS_STRING(raw), raw_len, width);
    assert(written >= 0 && written <= lines_end);
    for (; written < lines_end; written++) {
        out[written] = '\n'; /* the "~>" line of its own */
    }
    if (adobe) {
        out[written] = '~';
        out[written + 1] = '>';
    }
    return result;
}

const char radixly_a85encode_doc[] =
    PyDoc_STR("a85encode($module, /, b, *, foldspaces=False, wrapcol=0, pad=False, adobe=False)\n"
              "--\n"
              "\n"
              "Encode bytes-like object b using Ascii85 and return a bytes object.\n"
              "\n"
              "foldspaces is an optional flag that uses the special short sequence 'y'\n"
              "instead of 4 consecutive spaces (ASCII 0x20) as supported by 'btoa'. This\n"
              "feature is not supported by the standard encoding used in PDF.\n"
              "\n"
              "If wrapcol is non-zero, insert a newline (b'\\n') character after at most\n"
              "every wrapcol characters.\n"
              "\n"
              "pad controls whether zero-padding applied to the end of the input\n"
              "is fully retained in the output encoding, as done by btoa,\n"
              "producing an exact multiple of 5 bytes of output.\n"
              "\n"
              "adobe controls whether the encoded byte sequence is framed with <~\n"
              "and ~>, as in a PostScript base-85 string literal.  Note that\n"
              "while ASCII85Decode streams in PDF documents must be terminated\n"
              "with ~>, they must not use a leading <~.");
PyObject *
radixly_a85encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    PyObject *foldspaces = NULL;
    PyObject *wrapcol = NULL;
    PyObject *pad = NULL;
    PyObject *adobe = NULL;
    radixly_param params[] = {
        {"b", &arg}, {"foldspaces", &foldspaces}, {"wrapcol", &wrapcol}, {"pad", &pad}, {"adobe", &adobe}};
    if (radixly_bind_args("a85encode", args, nargs, kwnames, params, RADIXLY_ARRAY_SIZE(params), 1, 1) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_buffer_input(arg, &source) < 0) {
        return NULL;
    }
    PyObject *raw = radixly_85_encode(source.data, source.len, ALPHABET_A85, pad, 1, foldspaces);
    radixly_compat_input_release(&source);
    if (raw == NULL) {
        return NULL;
    }
    const int framed = radixly_compat_truth(adobe);
    const int wrapped = framed < 0 ? -1 : radixly_compat_truth(wrapcol);
    if (wrapped < 0) {
        Py_DECREF(raw);
        return NULL;
    }
    if (!framed && !wrapped) {
        return raw;
    }
    Py_ssize_t width = 0;
    if (wrapped) {
        width = wrap_width(wrapcol, framed);
        if (width < 0) {
            Py_DECREF(raw);
            return NULL;
        }
    }
    PyObject *result = frame_and_wrap(raw, framed, width);
    Py_DECREF(raw);
    return result;
}

/* Whether the stdlib's `x in ignorechars` holds: a table for bytes and bytearray, the operator itself for
 * anything else, with its own errors. */
typedef struct {
    PyObject *object;
    unsigned char table[TABLE_SIZE];
    int use_table;
} ignore_set;

static int
ignore_set_init(ignore_set *set, PyObject *ignorechars)
{
    for (unsigned code = 0; code < TABLE_SIZE; code++) {
        set->table[code] = 0;
    }
    set->object = ignorechars;
    set->use_table = 1;
    const unsigned char *data;
    Py_ssize_t len;
    if (ignorechars == NULL) {
        data = (const unsigned char *)DEFAULT_IGNORED;
        len = (Py_ssize_t)(sizeof(DEFAULT_IGNORED) - 1);
    }
    else if (PyBytes_Check(ignorechars)) {
        data = (const unsigned char *)PyBytes_AS_STRING(ignorechars);
        len = PyBytes_GET_SIZE(ignorechars);
    }
    else if (PyByteArray_Check(ignorechars)) {
        data = (const unsigned char *)PyByteArray_AS_STRING(ignorechars);
        len = PyByteArray_GET_SIZE(ignorechars);
    }
    else {
        set->use_table = 0;
        return 0;
    }
    for (Py_ssize_t i = 0; i < len; i++) {
        set->table[data[i]] = 1;
    }
    return 0;
}

/* 1 when the byte is ignored, 0 when not, -1 with the operator's own exception. */
static int
ignore_set_has(const ignore_set *set, unsigned char code)
{
    if (set->use_table) {
        return set->table[code];
    }
    PyObject *value = PyLong_FromLong(code);
    if (value == NULL) {
        return -1;
    }
    const int found = PySequence_Contains(set->object, value);
    Py_DECREF(value);
    return found;
}

/* The state of the stdlib's decode loop: the digits gathered so far and where the next word goes. */
typedef struct {
    uint64_t acc;
    int digits;
    unsigned char *out;
    int folded_spaces; /* -1 until the stdlib would first read foldspaces */
    PyObject *foldspaces;
    ignore_set ignored;
} a85_state;

static void
put_word(a85_state *state, uint32_t word)
{
    for (int i = 0; i < GROUP_BYTES; i++) {
        *state->out++ =
            (unsigned char)((word >> (BITS_PER_BYTE * (unsigned)(GROUP_BYTES - 1 - i))) & BYTE_MASK);
    }
}

/* One byte of the stdlib's loop; -1 with the exception set. */
static int
take_byte(a85_state *state, unsigned char code)
{
    if (code >= FIRST && code <= LAST) {
        state->acc = (state->acc * BASE) + (code - FIRST);
        if (++state->digits == GROUP_CHARS) {
            if (state->acc > WORD_MAX) {
                PyObject *context = radixly_struct_error("'I' format requires 0 <= number <= 4294967295");
                PyObject *message = context == NULL ? NULL : PyUnicode_FromString("Ascii85 overflow");
                radixly_raise_from(PyExc_ValueError, message, context);
                return -1;
            }
            put_word(state, (uint32_t)state->acc);
            state->acc = 0;
            state->digits = 0;
        }
        return 0;
    }
    if (code == 'z') {
        if (state->digits != 0) {
            PyErr_SetString(PyExc_ValueError, "z inside Ascii85 5-tuple");
            return -1;
        }
        put_word(state, 0);
        return 0;
    }
    if (state->folded_spaces < 0) {
        state->folded_spaces = radixly_compat_truth(state->foldspaces);
        if (state->folded_spaces < 0) {
            return -1;
        }
    }
    if (state->folded_spaces && code == 'y') {
        if (state->digits != 0) {
            PyErr_SetString(PyExc_ValueError, "y inside Ascii85 5-tuple");
            return -1;
        }
        put_word(state, FOUR_SPACES);
        return 0;
    }
    const int ignored = ignore_set_has(&state->ignored, code);
    if (ignored != 0) {
        return ignored < 0 ? -1 : 0;
    }
    PyErr_Format(PyExc_ValueError, "Non-Ascii85 digit found: %c", (int)code);
    return -1;
}

const char radixly_a85decode_doc[] =
    PyDoc_STR("a85decode($module, /, b, *, foldspaces=False, adobe=False, ignorechars=b' \\t\\n\\r\\v')\n"
              "--\n"
              "\n"
              "Decode the Ascii85 encoded bytes-like object or ASCII string b.\n"
              "\n"
              "foldspaces is a flag that specifies whether the 'y' short sequence\n"
              "should be accepted as shorthand for 4 consecutive spaces (ASCII\n"
              "0x20).  This feature is not supported by the standard Ascii85\n"
              "encoding used in PDF and PostScript.\n"
              "\n"
              "adobe controls whether the <~ and ~> markers are present. While\n"
              "the leading <~ is not required, the input must end with ~>, or a\n"
              "ValueError is raised.\n"
              "\n"
              "ignorechars should be a byte string containing characters to ignore from the\n"
              "input. This should only contain whitespace characters, and by default\n"
              "contains all whitespace characters in ASCII.\n"
              "\n"
              "The result is returned as a bytes object.");
PyObject *
radixly_a85decode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    PyObject *foldspaces = NULL;
    PyObject *adobe = NULL;
    PyObject *ignorechars = NULL;
    radixly_param params[] = {
        {"b", &arg}, {"foldspaces", &foldspaces}, {"adobe", &adobe}, {"ignorechars", &ignorechars}};
    if (radixly_bind_args("a85decode", args, nargs, kwnames, params, RADIXLY_ARRAY_SIZE(params), 1, 1) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    const unsigned char *data = source.data;
    Py_ssize_t len = source.len;
    const int framed = radixly_compat_truth(adobe);
    if (framed < 0) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    if (framed) {
        if (len < FRAME || data[len - 2] != '~' || data[len - 1] != '>') {
            radixly_compat_input_release(&source);
            PyErr_SetString(PyExc_ValueError, "Ascii85 encoded byte sequences must end with b'~>'");
            return NULL;
        }
        len -= FRAME;
        if (len >= FRAME && data[0] == '<' && data[1] == '~') {
            data += FRAME;
            len -= FRAME;
        }
    }
    if (len > (PY_SSIZE_T_MAX / GROUP_BYTES) - GROUP_BYTES) {
        radixly_compat_input_release(&source);
        return PyErr_NoMemory();
    }
    /* Every byte may be a 'z' worth four; the four 'u' the stdlib appends complete the last group. */
    PyObject *result = PyBytes_FromStringAndSize(NULL, GROUP_BYTES * (len + GROUP_BYTES));
    if (result == NULL) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    a85_state state = {0, 0, (unsigned char *)PyBytes_AS_STRING(result), -1, foldspaces, {NULL, {0}, 0}};
    ignore_set_init(&state.ignored, ignorechars);
    for (Py_ssize_t i = 0; i < len + GROUP_BYTES; i++) {
        if (take_byte(&state, i < len ? data[i] : (unsigned char)LAST) < 0) {
            radixly_compat_input_release(&source);
            Py_DECREF(result);
            return NULL;
        }
    }
    radixly_compat_input_release(&source);
    Py_ssize_t out_len = state.out - (unsigned char *)PyBytes_AS_STRING(result);
    const Py_ssize_t padding = GROUP_BYTES - state.digits;
    if (padding != 0) {
        out_len = Py_MAX(0, out_len - padding);
    }
    if (out_len != PyBytes_GET_SIZE(result) && _PyBytes_Resize(&result, out_len) < 0) {
        return NULL; /* result already cleared and the exception set */
    }
    return result;
}
