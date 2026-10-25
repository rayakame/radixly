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
    TOP_DIGIT = 84,
    TABLE_SIZE = 256,
    FRAME = 2,      /* the "<~" and "~>" markers */
    FRAME_BOTH = 4, /* both of them */
    PREFIX = '<',
    AFFIX = '~',
    SUFFIX = '>',
};

static const uint64_t WORD_MAX = 0xFFFFFFFFU;
static const uint32_t FOUR_SPACES = 0x20202020U;
static const char DEFAULT_IGNORED[] = " \t\n\r\v";

/* The stdlib's max(2 if adobe else 1, wrapcol) then range(0, n, wrapcol): the comparison's own TypeError for
 * a value that is not ordered against int, __index__'s for one that is not an integer, the ssize maximum for
 * one too large to matter. */
/* The line width the stdlib's max() settles on, as a count. It then threads the object itself through
 * range(), the slice and, under adobe, the closing-line test, so an object whose arithmetic or ordering is
 * partial can still differ; a plain integer, which is what the parameter is for, cannot. */
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
    if (width == -1 && PyErr_Occurred()) {
        return -1; /* the conversion failed; a -1 without an exception is a real width, see below */
    }
    if (width == 0) {
        PyErr_SetString(PyExc_ValueError, "range() arg 3 must not be zero");
        return -1;
    }
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
        {"b", &arg}, {"foldspaces", &foldspaces}, {"wrapcol", &wrapcol}, {"pad", &pad}, {"adobe", &adobe},
    };
    if (radixly_bind_args("a85encode", args, nargs, kwnames, params, RADIXLY_ARRAY_SIZE(params), 1, 1) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_buffer_input(arg, &source) < 0) {
        return NULL;
    }
    PyObject *raw = radixly_85_encode(source.data, source.len, RADIXLY_B85_A85, pad, 1, foldspaces);
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
        if (width == -1 && PyErr_Occurred()) {
            Py_DECREF(raw);
            return NULL;
        }
        if (width < 0) {
            /* The stdlib's range() yields nothing, so it joins no chunks at all and then indexes them. */
            Py_DECREF(raw);
            if (framed) {
                PyErr_SetString(PyExc_IndexError, "list index out of range");
                return NULL;
            }
            return PyBytes_FromStringAndSize("", 0);
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
    /* Exact types only: a subclass may have its own __contains__, which the stdlib's `x in ignorechars`
     * calls. */
    else if (PyBytes_CheckExact(ignorechars)) {
        data = (const unsigned char *)PyBytes_AS_STRING(ignorechars);
        len = PyBytes_GET_SIZE(ignorechars);
    }
    else if (PyByteArray_CheckExact(ignorechars)) {
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
            radixly_b85_put_word(state->out, (uint32_t)state->acc, GROUP_BYTES);
            state->out += GROUP_BYTES;
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
        radixly_b85_put_word(state->out, 0, GROUP_BYTES);
        state->out += GROUP_BYTES;
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
        radixly_b85_put_word(state->out, FOUR_SPACES, GROUP_BYTES);
        state->out += GROUP_BYTES;
        return 0;
    }
    const int ignored = ignore_set_has(&state->ignored, code);
    if (ignored != 0) {
        return ignored < 0 ? -1 : 0;
    }
    PyErr_Format(PyExc_ValueError, "Non-Ascii85 digit found: %c", (int)code);
    return -1;
}

/* binascii's bound for an Ascii85 decode, which the pure-Python decoder shares: every 'y' and 'z' is a word
 * of its own, the digits whole groups rounded up. -1 with the error set when it does not fit. */
static Py_ssize_t
decode_bound(const unsigned char *data, Py_ssize_t len, PyObject *(*too_much)(const char *))
{
    size_t count_yz = 0;
    for (Py_ssize_t i = 0; i < len; i++) {
        if (data[i] == 'y' || data[i] == 'z') {
            count_yz++;
        }
    }
    const size_t words = ((size_t)len - count_yz + (size_t)GROUP_BYTES) / (size_t)GROUP_CHARS;
    if (count_yz > (((size_t)PY_SSIZE_T_MAX / GROUP_BYTES) - words)) {
        too_much("Too much Ascii85 data");
        return -1;
    }
    return (Py_ssize_t)((words + count_yz) * GROUP_BYTES);
}

static PyObject *
no_memory(const char *Py_UNUSED(message))
{
    return PyErr_NoMemory();
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
        {"b", &arg},
        {"foldspaces", &foldspaces},
        {"adobe", &adobe},
        {"ignorechars", &ignorechars},
    };
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
        if (len < FRAME || data[len - 2] != AFFIX || data[len - 1] != SUFFIX) {
            radixly_compat_input_release(&source);
            PyErr_SetString(PyExc_ValueError, "Ascii85 encoded byte sequences must end with b'~>'");
            return NULL;
        }
        len -= FRAME;
        if (len >= FRAME && data[0] == PREFIX && data[1] == AFFIX) {
            data += FRAME;
            len -= FRAME;
        }
    }
    const Py_ssize_t bound = decode_bound(data, len, no_memory);
    if (bound < 0) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, bound);
    if (result == NULL) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    a85_state state = {0, 0, start, -1, foldspaces, {NULL, {0}, 0}};
    ignore_set_init(&state.ignored, ignorechars);
    const unsigned char *table = radixly_b85_table(RADIXLY_B85_A85);
    /* Whole groups of digits at speed; the four 'u' the stdlib appends complete the last group. */
    Py_ssize_t index = 0;
    while (index < len + GROUP_BYTES) {
        if (state.digits == 0 && index < len) {
            const Py_ssize_t consumed = radixly_b85_groups(data + index, len - index, state.out, table, 0);
            index += consumed;
            state.out += (consumed / GROUP_CHARS) * GROUP_BYTES;
        }
        if (take_byte(&state, index < len ? data[index] : (unsigned char)LAST) < 0) {
            radixly_compat_input_release(&source);
            Py_DECREF(result);
            return NULL;
        }
        index++;
    }
    radixly_compat_input_release(&source);
    Py_ssize_t out_len = state.out - start;
    const Py_ssize_t padding = GROUP_BYTES - state.digits;
    if (padding != 0) {
        out_len = Py_MAX(0, out_len - padding);
    }
    return radixly_compat_finish(result, out_len);
}

/* Python 3.15 made a85encode and a85decode shells over binascii.b2a_ascii85 and a2b_ascii85. */

static const uint32_t A85_Z = 0x00000000U;
static const uint32_t A85_Y = 0x20202020U;

/* Strip the Adobe frame; -1 with the error set when the "~>" is missing. */
static int
unframe(const unsigned char **data, Py_ssize_t *len)
{
    if (*len < FRAME || (*data)[*len - 2] != AFFIX || (*data)[*len - 1] != SUFFIX) {
        radixly_binascii_error("Ascii85 encoded byte sequences must end with b'~>'");
        return -1;
    }
    *len -= FRAME;
    if (*len >= FRAME && (*data)[0] == PREFIX && (*data)[1] == AFFIX) {
        *data += FRAME;
        *len -= FRAME;
    }
    return 0;
}

typedef struct {
    unsigned char *out;
    uint32_t leftchar;
    int group_pos;
    int from_z; /* the current group came from 'z' */
} a2b_state;

/* One character of a2b_ascii85: the digit, a shorthand, something ignored, or -1 with the error set. */
static int
a2b_step(a2b_state *state, unsigned char this_ch, unsigned digit, int foldspaces, radixly_ignore_set *skip)
{
    if (digit < BASE) {
        if (radixly_b85_take_digit(&state->leftchar, &state->group_pos, digit) != 0) {
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
        state->group_pos = GROUP_CHARS;
        return 0;
    }
    if (radixly_ignored(skip, this_ch) == 0) {
        radixly_binascii_error_format("Non-Ascii85 digit found: %c", (int)this_ch);
        return -1;
    }
    return 0;
}

/* The canonical readings binascii enforces on a full group: 'z' for zero words, the encoder's own tail
 * digits.
 */
static int
a2b_canonical(const a2b_state *state, int chunk_len)
{
    if (chunk_len == GROUP_BYTES && state->leftchar == 0 && state->from_z == 0) {
        radixly_binascii_error("Non-canonical encoding, use 'z' for all-zero groups");
        return -1;
    }
    if (chunk_len < GROUP_BYTES && radixly_b85_canonical_tail(state->leftchar, chunk_len) == 0) {
        radixly_binascii_error("Non-zero padding bits");
        return -1;
    }
    return 0;
}

/* binascii.a2b_ascii85: whole groups of digits at speed, the shorthands and everything else one character at
 * a time, the input padded with the top digit to a whole last group. */
static PyObject *
a2b_ascii85(const unsigned char *data, Py_ssize_t len, int foldspaces, int adobe, const unsigned char *ignore,
            Py_ssize_t ignore_len, int canonical)
{
    if (adobe != 0 && unframe(&data, &len) < 0) {
        return NULL;
    }
    radixly_ignore_set skip;
    radixly_ignore_set_init(&skip, ignore, ignore_len);
    const Py_ssize_t bound = decode_bound(data, len, radixly_binascii_error);
    if (bound < 0) {
        return NULL;
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, bound);
    if (result == NULL) {
        return NULL;
    }
    const unsigned char *table = radixly_b85_table(RADIXLY_B85_A85);
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    a2b_state state = {start, 0, 0, 0};
    for (; len > 0 || state.group_pos != 0; len--, data++) {
        if (state.group_pos == 0 && len > 0) {
            const Py_ssize_t consumed = radixly_b85_groups(data, len, state.out, table, canonical);
            data += consumed;
            len -= consumed;
            state.out += (consumed / GROUP_CHARS) * GROUP_BYTES;
            if (len == 0) {
                break;
            }
        }
        unsigned char this_ch = 0;
        unsigned digit = TOP_DIGIT;
        if (len > 0) {
            this_ch = *data;
            digit = table[this_ch];
        }
        if (a2b_step(&state, this_ch, digit, foldspaces, &skip) < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (state.group_pos != GROUP_CHARS) {
            continue;
        }
        const int chunk_len = radixly_b85_chunk_length(len);
        if (chunk_len == 0) {
            Py_DECREF(result);
            return radixly_binascii_error("Incomplete Ascii85 group");
        }
        radixly_b85_put_word(state.out, state.leftchar, chunk_len);
        state.out += chunk_len;
        if (canonical != 0 && a2b_canonical(&state, chunk_len) < 0) {
            Py_DECREF(result);
            return NULL;
        }
        state.from_z = 0;
        state.group_pos = 0;
        state.leftchar = 0;
    }
    return radixly_compat_finish(result, state.out - start);
}

/* The words of the input as Ascii85 digits or the z and y shorthands; returns the cursor after them. */
static unsigned char *
words(unsigned char *out, const unsigned char *data, Py_ssize_t len, int foldspaces, int pad)
{
    for (; len >= GROUP_BYTES; len -= GROUP_BYTES, data += GROUP_BYTES) {
        const uint32_t word =
            ((uint32_t)data[0] << 24U) | ((uint32_t)data[1] << 16U) | ((uint32_t)data[2] << 8U) | data[3];
        if (word == A85_Z) {
            *out++ = 'z';
        }
        else if (foldspaces != 0 && word == A85_Y) {
            *out++ = 'y';
        }
        else {
            radixly_b85_digits(word, out, RADIXLY_B85_A85);
            out += GROUP_CHARS;
        }
    }
    if (len > 0) {
        const uint32_t word = radixly_b85_word(data, len);
        if (pad != 0 && word == A85_Z) {
            *out++ = 'z';
        }
        else {
            unsigned char digits[GROUP_CHARS];
            radixly_b85_digits(word, digits, RADIXLY_B85_A85);
            const Py_ssize_t group_len = pad != 0 ? GROUP_CHARS : len + 1;
            memcpy(out, digits, (size_t)group_len);
            out += group_len;
        }
    }
    return out;
}

/* binascii.b2a_ascii85: foldspaces, wrapcol, pad and the Adobe frame. */
static PyObject *
b2a_ascii85(const unsigned char *data, Py_ssize_t len, int foldspaces, size_t wrapcol, int pad, int adobe)
{
    if (adobe != 0 && wrapcol == 1) {
        wrapcol = 2;
    }
    const size_t out_len = radixly_b85_bound(len, wrapcol, pad, adobe != 0 ? FRAME_BOTH : 0);
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
        *out++ = PREFIX;
        *out++ = AFFIX;
    }
    out = words(out, data, len, foldspaces, pad);
    if (adobe != 0) {
        *out++ = AFFIX;
        *out++ = SUFFIX;
    }
    if (wrapcol != 0 && out_len != 0) {
        out = start + radixly_compat_wraplines(start, out - start, wrapcol);
        /* The "~>" goes on a line of its own when the wrap split it from its text. */
        if (adobe != 0 && out[-2] == '\n') {
            assert(out[-1] == SUFFIX);
            assert(out[-3] == AFFIX);
            out[-3] = '\n';
            out[-2] = AFFIX;
        }
    }
    return radixly_compat_finish(result, out - start);
}

const char radixly_a85encode_py315_doc[] =
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
radixly_a85encode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    PyObject *foldspaces = NULL;
    PyObject *wrapcol = NULL;
    PyObject *pad = NULL;
    PyObject *adobe = NULL;
    radixly_param params[] = {
        {"b", &arg}, {"foldspaces", &foldspaces}, {"wrapcol", &wrapcol}, {"pad", &pad}, {"adobe", &adobe},
    };
    if (radixly_bind_args("a85encode", args, nargs, kwnames, params, RADIXLY_ARRAY_SIZE(params), 1, 1) < 0) {
        return NULL;
    }
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) < 0) {
        return NULL;
    }
    /* binascii's keywords in its own order: foldspaces, wrapcol, pad, adobe. */
    PyObject *result = NULL;
    size_t width = 0;
    const int fold = radixly_compat_truth(foldspaces);
    if (fold >= 0 && (wrapcol == NULL || radixly_compat_size_t(wrapcol, &width) == 0)) {
        const int padding = radixly_compat_truth(pad);
        const int framed = padding < 0 ? -1 : radixly_compat_truth(adobe);
        if (framed >= 0) {
            result = b2a_ascii85(view.buf, view.len, fold, width, padding, framed);
        }
    }
    PyBuffer_Release(&view);
    return result;
}

const char radixly_a85decode_py315_doc[] =
    PyDoc_STR("a85decode($module, /, b, *, foldspaces=False, adobe=False, ignorechars=b' \\t\\n\\r\\v', "
              "canonical=False)\n"
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
              "If canonical is true, non-canonical encodings are rejected.\n"
              "\n"
              "The result is returned as a bytes object.");
PyObject *
radixly_a85decode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *arg = NULL;
    PyObject *foldspaces = NULL;
    PyObject *adobe = NULL;
    PyObject *ignorechars = NULL;
    PyObject *canonical = NULL;
    radixly_param params[] = {
        {"b", &arg},
        {"foldspaces", &foldspaces},
        {"adobe", &adobe},
        {"ignorechars", &ignorechars},
        {"canonical", &canonical},
    };
    if (radixly_bind_args("a85decode", args, nargs, kwnames, params, RADIXLY_ARRAY_SIZE(params), 1, 1) < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_ascii_buffer_input(arg, &source) < 0) {
        return NULL;
    }
    /* binascii's keywords in its own order: foldspaces, adobe, ignorechars, canonical. */
    PyObject *result = NULL;
    const int fold = radixly_compat_truth(foldspaces);
    const int framed = fold < 0 ? -1 : radixly_compat_truth(adobe);
    radixly_compat_bytes ignore;
    if (framed >= 0 && radixly_compat_bytes_init(&ignore, ignorechars, (const unsigned char *)DEFAULT_IGNORED,
                                                 (Py_ssize_t)(sizeof(DEFAULT_IGNORED) - 1)) == 0) {
        const int strict = radixly_compat_truth(canonical);
        if (strict >= 0) {
            result = a2b_ascii85(source.data, source.len, fold, framed, ignore.data, ignore.len, strict);
        }
        radixly_compat_bytes_release(&ignore);
    }
    radixly_compat_input_release(&source);
    return result;
}
