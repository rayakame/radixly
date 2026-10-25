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

#include "_common/args.h"
#include "_common/compat.h"
#include "_common/internal.h"

enum {
    GROUP_BYTES = 5,
    GROUP_CHARS = 8,
    PAD = '=',
    ALPHABET_SIZE = 32,
};

static const unsigned BITS_PER_CHAR = 5U;

/* The stdlib's leftover bytes for a pad count, its (43 - 5 * padchars) // 8; 0 marks a count it refuses. */
static const int STDLIB_LEFTOVER[GROUP_CHARS + 1] = {0, 4, 0, 3, 2, 0, 1, 0, 0};

static Py_ssize_t
encoded_len(Py_ssize_t num_bytes)
{
    return GROUP_CHARS * ((num_bytes + GROUP_BYTES - 1) / GROUP_BYTES);
}

/* How s reads once the stdlib's translate() and upper() have been over it: a table for the fast path with
 * both folded in, and the mapping itself for the characters the slow path judges one by one. */
typedef struct {
    const unsigned char *fast;
    const unsigned char *translate; /* map01's table, or NULL */
    int fold;
    unsigned char combined[RADIXLY_B32_TABLE_SIZE];
} b32_view;

static unsigned char
mapped_char(const b32_view *view, unsigned char code)
{
    const unsigned char translated = view->translate != NULL ? view->translate[code] : code;
    return view->fold != 0 ? Py_TOUPPER(translated) : translated;
}

static void
view_init(b32_view *view, int which, const unsigned char *translate, int fold)
{
    view->translate = translate;
    view->fold = fold;
    view->fast = fold != 0 ? radixly_b32_fold_table(which) : radixly_b32_table(which);
    if (translate != NULL) {
        for (unsigned code = 0; code < RADIXLY_B32_TABLE_SIZE; code++) {
            view->combined[code] = view->fast[translate[code]];
        }
        view->fast = view->combined;
    }
}

/* The top count bytes of a 40-bit value, big-endian. */
static void
unpack(uint64_t acc, unsigned char *out, int count)
{
    for (int i = 0; i < count; i++) {
        out[i] = (unsigned char)((acc >> (BITS_PER_BYTE * (unsigned)(GROUP_BYTES - 1 - i))) & BYTE_MASK);
    }
}

PyObject *
radixly_b32encode_with(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                       int which)
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
    radixly_b32_encode(source.data, source.len, (unsigned char *)PyBytes_AS_STRING(result), which);
    radixly_compat_input_release(&source);
    return result;
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
    if (radixly_compat_check_length(&source, 1) < 0) {
        radixly_compat_input_release(&source);
        return -1;
    }
    *byte = source.data[0];
    radixly_compat_input_release(&source);
    return 0;
}

static void
identity_table(unsigned char *translate)
{
    for (unsigned code = 0; code < RADIXLY_B32_TABLE_SIZE; code++) {
        translate[code] = (unsigned char)code;
    }
}

/* The stdlib's group loop: every quantum decoded and checked before the padding count is judged. The acc of
 * the last group comes back for the caller's padding fix-up. */
static PyObject *
stdlib_decode_groups(const radixly_compat_input *source, Py_ssize_t stripped, const b32_view *view,
                     uint64_t *last_acc)
{
    const Py_ssize_t num_groups = (stripped + GROUP_CHARS - 1) / GROUP_CHARS;
    PyObject *result = PyBytes_FromStringAndSize(NULL, GROUP_BYTES * num_groups);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(result);
    const Py_ssize_t whole = GROUP_CHARS * (stripped / GROUP_CHARS);
    const Py_ssize_t consumed = radixly_b32_octas(source->data, whole, out, view->fast);
    /* What the fast path left: a group holding a bad character, or the partial last group. */
    uint64_t acc = 0;
    for (Py_ssize_t i = consumed; i < stripped; i++) {
        const unsigned value = view->fast[source->data[i]];
        if (value >= ALPHABET_SIZE) {
            Py_DECREF(result);
            /* The stdlib fails in `b32rev[c]` and hides that KeyError with `from None`; c is upper by then.
             */
            return radixly_binascii_error_from(
                "Non-base32 digit found",
                PyObject_CallFunction(PyExc_KeyError, "I", (unsigned)mapped_char(view, source->data[i])));
        }
        acc = (acc << BITS_PER_CHAR) | value;
        if (((i + 1) % GROUP_CHARS) == 0) {
            unpack(acc, out + (GROUP_BYTES * (i / GROUP_CHARS)), GROUP_BYTES);
            acc = 0;
        }
    }
    if ((stripped % GROUP_CHARS) != 0) {
        unpack(acc, out + (GROUP_BYTES * (stripped / GROUP_CHARS)), GROUP_BYTES);
    }
    *last_acc = acc;
    return result;
}

/* A faithful port of the stdlib's _b32decode. */
PyObject *
radixly_b32decode_with(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                       int which)
{
    PyObject *arg = NULL;
    PyObject *casefold = NULL;
    PyObject *map01 = NULL;
    radixly_param params[] = {{"s", &arg}, {"casefold", &casefold}, {"map01", &map01}};
    const Py_ssize_t num_params = which == RADIXLY_B32_HEX ? 2 : 3;
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
    unsigned char translate[RADIXLY_B32_TABLE_SIZE];
    const int mapped = map01 != NULL && map01 != Py_None;
    if (mapped) {
        unsigned char one;
        if (map01_byte(map01, &one) < 0) {
            radixly_compat_input_release(&source);
            return NULL;
        }
        identity_table(translate);
        translate['0'] = 'O';
        translate['1'] = one;
    }
    /* The stdlib reads s and map01 before it looks at casefold, so a flag that raises comes last here too. */
    const int fold = radixly_compat_truth(casefold);
    if (fold < 0) {
        radixly_compat_input_release(&source);
        return NULL;
    }
    b32_view view;
    view_init(&view, which, mapped ? translate : NULL, fold);
    /* The stdlib strips '=' after translating, so a map01 of '=' strips the ones it made. */
    Py_ssize_t stripped = source.len;
    while (stripped > 0 && mapped_char(&view, source.data[stripped - 1]) == PAD) {
        stripped--;
    }
    const Py_ssize_t padchars = source.len - stripped;
    uint64_t last_acc = 0;
    PyObject *result = stdlib_decode_groups(&source, stripped, &view, &last_acc);
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

const char radixly_b32encode_doc[] =
    PyDoc_STR("b32encode($module, /, s)\n"
              "--\n"
              "\n"
              "Encode the bytes-like objects using base32 and return a bytes object.");
PyObject *
radixly_b32encode(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b32encode_with("b32encode", args, nargs, kwnames, RADIXLY_B32_STD);
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
    return radixly_b32decode_with("b32decode", args, nargs, kwnames, RADIXLY_B32_STD);
}

/* Python 3.15 made the base32 functions shells over binascii.b2a_base32 and a2b_base32. */

/* binascii.b2a_base32: padded and wrapcol included. */
static PyObject *
b2a_base32(const unsigned char *data, Py_ssize_t len, int padded, size_t wrapcol, int which)
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
    if (out_len > (size_t)PY_SSIZE_T_MAX) {
        return radixly_binascii_error("Too much data for base32");
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)out_len);
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    const Py_ssize_t whole = radixly_b32_fill(data, len, start, which);
    unsigned char *out = start + ((whole / GROUP_BYTES) * GROUP_CHARS);
    out += radixly_b32_tail(data + whole, len - whole, out, which);
    for (; pads != 0; pads--) {
        *out++ = PAD;
    }
    if (wrapcol != 0 && out_len != 0) {
        out = start + radixly_compat_wraplines(start, out - start, wrapcol);
    }
    return radixly_compat_finish(result, out - start);
}

PyObject *
radixly_b32encode_with_py315(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                             int which)
{
    PyObject *arg = NULL;
    PyObject *padded = NULL;
    PyObject *wrapcol = NULL;
    radixly_param params[] = {{"s", &arg}, {"padded", &padded}, {"wrapcol", &wrapcol}};
    if (radixly_bind_args(function, args, nargs, kwnames, params, 3, 1, 1) < 0) {
        return NULL;
    }
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) < 0) {
        return NULL;
    }
    PyObject *result = NULL;
    size_t width = 0;
    const int pad = padded == NULL ? 1 : PyObject_IsTrue(padded);
    if (pad >= 0 && (wrapcol == NULL || radixly_compat_size_t(wrapcol, &width) == 0)) {
        result = b2a_base32(view.buf, view.len, pad, width, which);
    }
    PyBuffer_Release(&view);
    return result;
}

/* Indexed by the characters read into the group: after 2, 4, 5 and 7 the bytes are whole and a pad may
 * follow; after 1, 3 and 6 a byte dangles, which binascii refuses outright. */
static const unsigned char PAD_MAY_FOLLOW[GROUP_CHARS] = {0, 0, 1, 0, 1, 1, 0, 1};
static const unsigned char BYTE_DANGLES[GROUP_CHARS] = {0, 1, 0, 1, 0, 0, 1, 0};

/* The accumulator behind binascii's octa_pos switch: leftchar holds the bits no byte has taken yet. */
typedef struct {
    unsigned char *start;
    unsigned char *out;
    unsigned pos;
    unsigned leftchar;
    unsigned leftbits;
    unsigned pads;
    radixly_ignore_set skip;
} a2b_state;

static int
a2b_pad(a2b_state *state)
{
    state->pads++;
    if (PAD_MAY_FOLLOW[state->pos] != 0 && state->pos + state->pads <= GROUP_CHARS) {
        return 1;
    }
    if (radixly_ignored(&state->skip, PAD) != 0) {
        return 1;
    }
    if (BYTE_DANGLES[state->pos] != 0) {
        return 0;
    }
    radixly_binascii_error(state->pos == 0 && state->out == state->start ? "Leading padding not allowed"
                                                                         : "Excess padding not allowed");
    return -1;
}

/* One character of binascii's slow path: 1 to go on, 0 to leave the loop, -1 with the error set. */
static int
a2b_step(a2b_state *state, unsigned char this_ch, int padded, const unsigned char *rev)
{
    const unsigned value = rev[this_ch];
    if (padded != 0 && value == RADIXLY_B32_PAD_VALUE) {
        return a2b_pad(state);
    }
    if (value >= ALPHABET_SIZE) {
        if (radixly_ignored(&state->skip, this_ch) == 0) {
            radixly_binascii_error(this_ch == PAD ? "Padding not allowed" : "Only base32 data is allowed");
            return -1;
        }
        return 1;
    }
    if (state->pads != 0 && radixly_ignored(&state->skip, PAD) == 0) {
        radixly_binascii_error(state->pos + state->pads == GROUP_CHARS ? "Excess data after padding"
                                                                       : "Discontinuous padding not allowed");
        return -1;
    }
    state->pos = (state->pos + 1U) % GROUP_CHARS;
    state->leftchar = (state->leftchar << BITS_PER_CHAR) | value;
    state->leftbits += BITS_PER_CHAR;
    if (state->leftbits >= BITS_PER_BYTE) {
        state->leftbits -= BITS_PER_BYTE;
        *state->out++ = (unsigned char)((state->leftchar >> state->leftbits) & BYTE_MASK);
        state->leftchar &= (1U << state->leftbits) - 1U;
    }
    if (state->pos == 0) {
        state->pads = 0; /* binascii restarts its slow path, pads included, after every whole group */
    }
    return 1;
}

/* binascii.a2b_base32 on s as the stdlib's translate() and upper() left it, read through view without a copy.
 */
static PyObject *
a2b_base32(const unsigned char *data, Py_ssize_t len, int padded, int which, const b32_view *view,
           const unsigned char *ignore, Py_ssize_t ignore_len, int canonical)
{
    const unsigned char *rev = radixly_b32_table(which);
    PyObject *result = PyBytes_FromStringAndSize(NULL, radixly_b32_decode_bound(data, len, view->fast));
    if (result == NULL) {
        return NULL;
    }
    unsigned char *start = (unsigned char *)PyBytes_AS_STRING(result);
    a2b_state state = {start, start, 0, 0, 0, 0, {NULL, 0, {0}}};
    radixly_ignore_set_init(&state.skip, ignore, ignore_len);
    Py_ssize_t index = 0;
    while (index < len) {
        if (state.pos == 0 && state.pads == 0) {
            const Py_ssize_t consumed = radixly_b32_octas(data + index, len - index, state.out, view->fast);
            index += consumed;
            state.out += (consumed / GROUP_CHARS) * GROUP_BYTES;
            if (index >= len) {
                break;
            }
        }
        const int outcome = a2b_step(&state, mapped_char(view, data[index++]), padded, rev);
        if (outcome < 0) {
            Py_DECREF(result);
            return NULL;
        }
        if (outcome == 0) {
            break;
        }
    }
    if (BYTE_DANGLES[state.pos] != 0) {
        Py_DECREF(result);
        return radixly_binascii_error_format("Invalid base32-encoded string: number of data characters (%zd) "
                                             "cannot be 1, 3, or 6 more than a multiple of 8",
                                             ((state.out - start) / GROUP_BYTES * GROUP_CHARS) +
                                                 (Py_ssize_t)state.pos);
    }
    if (padded != 0 && state.pos != 0 && state.pos + state.pads < GROUP_CHARS) {
        Py_DECREF(result);
        return radixly_binascii_error("Incorrect padding");
    }
    if (canonical != 0 && state.leftchar != 0) {
        Py_DECREF(result);
        return radixly_binascii_error("Non-zero padding bits");
    }
    return radixly_compat_finish(result, state.out - start);
}

/* The stdlib's bytes.maketrans(b'01', b'O' + map01): map01 through _bytes_from_decode_data, joined by
 * bytes.__add__, and refused by maketrans unless the pair is two bytes long. */
static int
map01_translation_py315(PyObject *map01, unsigned char *translate)
{
    radixly_compat_input source;
    if (radixly_compat_decode_input(map01, &source) < 0) {
        return -1;
    }
    PyObject *letter = radixly_compat_input_object(&source);
    radixly_compat_input_release(&source);
    if (letter == NULL) {
        return -1;
    }
    PyObject *prefix = PyBytes_FromStringAndSize("O", 1);
    PyObject *joined = prefix == NULL ? NULL : PyNumber_Add(prefix, letter);
    Py_XDECREF(prefix);
    Py_DECREF(letter);
    if (joined == NULL) {
        return -1;
    }
    Py_buffer pair;
    if (PyObject_GetBuffer(joined, &pair, PyBUF_SIMPLE) < 0) {
        Py_DECREF(joined);
        return -1;
    }
    int outcome = 0;
    if (pair.len != 2) {
        PyErr_SetString(PyExc_ValueError, "maketrans arguments must have same length");
        outcome = -1;
    }
    else {
        identity_table(translate);
        translate['0'] = ((const unsigned char *)pair.buf)[0];
        translate['1'] = ((const unsigned char *)pair.buf)[1];
    }
    PyBuffer_Release(&pair);
    Py_DECREF(joined);
    return outcome;
}

/* A flag whose truth is read without running code, or a buffer whose export runs none: the stdlib reads them
 * while binascii holds its translated or uppercased copy of s, not s itself, so only one that could edit s
 * earns the copy. */
static int
inert_flag(PyObject *flag)
{
    return flag == NULL || PyBool_Check(flag) || PyLong_CheckExact(flag);
}

static int
inert_buffer(PyObject *arg)
{
    return arg == NULL || PyBytes_CheckExact(arg) || PyByteArray_CheckExact(arg) || PyMemoryView_Check(arg);
}

/* s as translate() and upper() leave it, materialised where a hook could otherwise edit the original: the
 * copy takes the live buffer's place in source. -1 with the exception set and source released. */
static int
snapshot(radixly_compat_input *source, const b32_view *view, PyObject **copy)
{
    PyObject *made = PyBytes_FromStringAndSize(NULL, source->len);
    if (made == NULL) {
        radixly_compat_input_release(source);
        return -1;
    }
    unsigned char *out = (unsigned char *)PyBytes_AS_STRING(made);
    for (Py_ssize_t i = 0; i < source->len; i++) {
        out[i] = mapped_char(view, source->data[i]);
    }
    radixly_compat_input_release(source);
    source->data = (const unsigned char *)PyBytes_AS_STRING(made);
    source->len = PyBytes_GET_SIZE(made);
    *copy = made;
    return 0;
}

/* a2b_base32 with the keywords read in binascii's order: padded, ignorechars, canonical. */
static PyObject *
a2b_base32_py315(const unsigned char *data, Py_ssize_t len, int which, const b32_view *view, PyObject *padded,
                 PyObject *ignorechars, PyObject *canonical)
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
        result = a2b_base32(data, len, pad, which, view, ignore.data, ignore.len, strict_pad_bits);
    }
    radixly_compat_bytes_release(&ignore);
    return result;
}

PyObject *
radixly_b32decode_with_py315(const char *function, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames,
                             int which)
{
    PyObject *arg = NULL;
    PyObject *casefold = NULL;
    PyObject *map01 = NULL;
    PyObject *padded = NULL;
    PyObject *ignorechars = NULL;
    PyObject *canonical = NULL;
    radixly_param standard[] = {
        {"s", &arg},         {"casefold", &casefold},       {"map01", &map01},
        {"padded", &padded}, {"ignorechars", &ignorechars}, {"canonical", &canonical},
    };
    radixly_param hexadecimal[] = {
        {"s", &arg},
        {"casefold", &casefold},
        {"padded", &padded},
        {"ignorechars", &ignorechars},
        {"canonical", &canonical},
    };
    const int bound =
        which == RADIXLY_B32_HEX
            ? radixly_bind_args(function, args, nargs, kwnames, hexadecimal, RADIXLY_ARRAY_SIZE(hexadecimal),
                                1, 2)
            : radixly_bind_args(function, args, nargs, kwnames, standard, RADIXLY_ARRAY_SIZE(standard), 1, 3);
    if (bound < 0) {
        return NULL;
    }
    radixly_compat_input source;
    if (radixly_compat_decode_input(arg, &source) < 0) {
        return NULL;
    }
    /* The stdlib's order: map01's translate() copies s, casefold is read, upper() copies, then binascii reads
     * the flags. A copy is made here only where a hook could otherwise edit what is decoded. */
    unsigned char translate[RADIXLY_B32_TABLE_SIZE];
    const unsigned char *mapping = NULL;
    if (map01 != NULL && map01 != Py_None) {
        if (map01_translation_py315(map01, translate) < 0) {
            radixly_compat_input_release(&source);
            return NULL;
        }
        mapping = translate;
    }
    b32_view view;
    PyObject *copy = NULL;
    if (mapping != NULL && !inert_flag(casefold)) {
        view_init(&view, which, mapping, 0);
        if (snapshot(&source, &view, &copy) < 0) {
            return NULL;
        }
        mapping = NULL;
    }
    const int fold = radixly_compat_truth(casefold);
    if (fold < 0) {
        radixly_compat_input_release(&source);
        Py_XDECREF(copy);
        return NULL;
    }
    view_init(&view, which, mapping, fold);
    if ((mapping != NULL || fold != 0) &&
        !(inert_flag(padded) && inert_flag(canonical) && inert_buffer(ignorechars))) {
        PyObject *previous = copy;
        if (snapshot(&source, &view, &copy) < 0) {
            Py_XDECREF(previous);
            return NULL;
        }
        Py_XDECREF(previous);
        view_init(&view, which, NULL, 0);
    }
    PyObject *result =
        a2b_base32_py315(source.data, source.len, which, &view, padded, ignorechars, canonical);
    radixly_compat_input_release(&source);
    Py_XDECREF(copy);
    return result;
}

const char radixly_b32encode_py315_doc[] =
    PyDoc_STR("b32encode($module, /, s, *, padded=True, wrapcol=0)\n"
              "--\n"
              "\n"
              "Encode the bytes-like objects using base32 and return a bytes object.\n"
              "\n"
              "If padded is false, omit padding in the output.\n"
              "\n"
              "If wrapcol is non-zero, insert a newline (b'\\n') character after at most\n"
              "every wrapcol characters.");
PyObject *
radixly_b32encode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b32encode_with_py315("b32encode", args, nargs, kwnames, RADIXLY_B32_STD);
}

const char radixly_b32decode_py315_doc[] =
    PyDoc_STR("b32decode($module, /, s, casefold=False, map01=None, *, padded=True, ignorechars=b'', "
              "canonical=False)\n"
              "--\n"
              "\n"
              "Decode the base32 encoded bytes-like object or ASCII string s.\n"
              "\n"
              "Optional casefold is a flag specifying whether a lowercase alphabet is\n"
              "acceptable as input.  For security purposes, the default is False.\n"
              "\n"
              "If padded is false, padding in input is not required.\n"
              "\n"
              "ignorechars should be a byte string containing characters to ignore\n"
              "from the input.\n"
              "\n"
              "RFC 4648 allows for optional mapping of the digit 0 (zero) to the\n"
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
radixly_b32decode_py315(PyObject *Py_UNUSED(self), PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return radixly_b32decode_with_py315("b32decode", args, nargs, kwnames, RADIXLY_B32_STD);
}
