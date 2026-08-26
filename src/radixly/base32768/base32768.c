#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "_tables.h"
#include "base32768.h"

#include "_common/errors.h"
#include "_common/internal.h"

enum {
    BITS_PER_BYTE = 8,
    BITS_PER_CHAR = 15,
    MAX_CHAR = 0xFFFF,
    REV_INVALID = MAX_CHAR,
    CEIL_PAD = BITS_PER_CHAR - 1,
};

static const uint16_t REV_7BIT_FLAG = 0x8000;
static const uint32_t REV_VALUE_MASK = 0x7FFF;
static const uint32_t BYTE_MASK = 0xFF;

static uint16_t REV[MAX_CHAR + 1];

int
radixly_base32768_exec(PyObject *Py_UNUSED(module))
{
    for (size_t i = 0; i < RADIXLY_ARRAY_SIZE(REV); i++) {
        REV[i] = REV_INVALID;
    }

    for (size_t i = 0; i < RADIXLY_ARRAY_SIZE(RADIXLY_B32768_FWD15); i++) {
        REV[RADIXLY_B32768_FWD15[i]] = i;
    }

    for (size_t i = 0; i < RADIXLY_ARRAY_SIZE(RADIXLY_B32768_FWD7); i++) {
        REV[RADIXLY_B32768_FWD7[i]] = REV_7BIT_FLAG | i;
    }
    return 0;
}

const char radixly_base32768_encode_doc[] =
    PyDoc_STR("base32768_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as base32768 text.\n"
              "\n"
              "Returns a str of BMP code points, 15 bits of payload per character\n"
              "(7 in a final short character). Exact output length: ceil(8*n/15).");
PyObject *
radixly_base32768_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len == 0) {
        PyBuffer_Release(&view);
        return PyUnicode_New(0, 0);
    }
    if (view.len > (PY_SSIZE_T_MAX - CEIL_PAD) / BITS_PER_BYTE) {
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    const Py_ssize_t n_chars = ((BITS_PER_BYTE * view.len) + CEIL_PAD) / BITS_PER_CHAR;

    PyObject *result = PyUnicode_New(n_chars, MAX_CHAR);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return result;
    }
    Py_UCS2 *out = PyUnicode_2BYTE_DATA(result);

    const unsigned char *data = view.buf;
    uint32_t acc = 0;
    unsigned num_bits = 0;
    Py_ssize_t out_i = 0;
    for (Py_ssize_t i = 0; i < view.len; i++) {
        acc = (acc << (unsigned)BITS_PER_BYTE) | data[i];
        num_bits += BITS_PER_BYTE;

        while (num_bits >= BITS_PER_CHAR) {
            num_bits -= BITS_PER_CHAR;
            out[out_i] = RADIXLY_B32768_FWD15[acc >> num_bits];
            out_i++;
            acc &= (1U << num_bits) - 1;
        }
    }

    if (num_bits > 0) {
        unsigned width;
        const uint16_t *table;
        if (num_bits <= (BITS_PER_CHAR - BITS_PER_BYTE)) {
            width = BITS_PER_CHAR - BITS_PER_BYTE;
            table = RADIXLY_B32768_FWD7;
        }
        else {
            width = BITS_PER_CHAR;
            table = RADIXLY_B32768_FWD15;
        }

        const unsigned gap = width - num_bits;
        acc = (acc << gap) | ((1U << gap) - 1);
        out[out_i] = table[acc];
        out_i++;
    }
    assert(out_i == n_chars);
    PyBuffer_Release(&view);
    return result;
}

const char radixly_base32768_decode_doc[] =
    PyDoc_STR("base32768_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode base32768 text back to bytes.\n"
              "\n"
              "Decoding is strict and canonical: an invalid or misplaced\n"
              "character, broken padding, or a non-canonical final character\n"
              "raises DecodeError carrying the offending position.");
PyObject *
radixly_base32768_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    if (!PyUnicode_Check(arg)) {
        PyErr_Format(PyExc_TypeError, "expected str, not %.200s", Py_TYPE(arg)->tp_name);
        return NULL;
    }
#if PY_VERSION_HEX < 0x030C0000
    /* 3.11 can still meet legacy, non-ready strings built by other C
     * extensions via APIs removed in 3.12; GET_LENGTH/KIND/DATA on one is
     * UB. Deprecated call, but it compiles out on 3.12+ -- the 3.11 build
     * may need a deprecation suppression when M5 brings -Werror. */
    if (PyUnicode_READY(arg) == -1) {
        return NULL;
    }
#endif
    const Py_ssize_t num_chars = PyUnicode_GET_LENGTH(arg);
    if (num_chars == 0) {
        return PyBytes_FromStringAndSize("", 0);
    }
    if (num_chars > PY_SSIZE_T_MAX / BITS_PER_CHAR) {
        return PyErr_NoMemory();
    }
    int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);

    Py_ssize_t total_bits = 0;
    unsigned final_width = 0;
    for (Py_ssize_t i = 0; i < num_chars; i++) {
        Py_UCS4 code_point = PyUnicode_READ(kind, data, i);
        if (code_point > MAX_CHAR) {
            return radixly_raise_decode_error(i, "invalid base32768 character U+%x at index %zd",
                                              (unsigned)code_point, i);
        }
        const uint16_t rev_entry = REV[code_point];
        if (rev_entry == REV_INVALID) {
            return radixly_raise_decode_error(i, "invalid base32768 character U+%x at index %zd",
                                              (unsigned)code_point, i);
        }
        const unsigned width = (rev_entry & REV_7BIT_FLAG) ? 7 : 15;
        if (width != BITS_PER_CHAR && i != num_chars - 1) {
            return radixly_raise_decode_error(i, "7-bit character U+%x at index %zd, only valid at index %zd",
                                              (unsigned)code_point, i, num_chars - 1);
        }
        total_bits += width;
        final_width = width;
    }

    Py_ssize_t num_bytes = total_bits / BITS_PER_BYTE;
    const unsigned num_pad = (unsigned)(total_bits % BITS_PER_BYTE);

    /* Canonicality: the final character must carry at least one payload bit.
     * A 7-bit final character with 7 padding bits is pure filler, which the
     * encoder never emits (it stops instead of emitting an empty character).
     * Stated width-independently: reject when the final character is no wider
     * than the padding it would have to hold.
     *
     * NOTE: this deliberately diverges from qntm's reference JS, which accepts
     * such a string. radixly rejects it so that decode is injective: one
     * payload, exactly one accepted spelling. Mirrors the same check in
     * tests/reference/base32768.py — keep the two in lockstep. */
    if (final_width <= num_pad) {
        return radixly_raise_decode_error(
            num_chars - 1, "non-canonical input: %u-bit final character at index %zd carries no payload bits",
            final_width, num_chars - 1);
    }
    PyObject *result = PyBytes_FromStringAndSize(NULL, num_bytes);
    if (result == NULL) {
        return NULL;
    }
    char *out = PyBytes_AS_STRING(result);

    uint32_t acc = 0;
    unsigned bits = 0;
    Py_ssize_t out_i = 0;

    for (Py_ssize_t i = 0; i < num_chars; i++) {
        Py_UCS4 code_point = PyUnicode_READ(kind, data, i);
        const uint16_t rev_entry = REV[code_point];
        const unsigned width = (rev_entry & REV_7BIT_FLAG) ? 7 : 15;
        acc = (acc << width) | (rev_entry & REV_VALUE_MASK);
        bits += width;
        while (bits >= BITS_PER_BYTE) {
            bits -= BITS_PER_BYTE;
            out[out_i] = (char)((acc >> bits) & BYTE_MASK);
            out_i++;
            acc &= (1U << bits) - 1U;
        }
    }
    assert(out_i == num_bytes);
    /* The drain loop masks acc after every byte, so acc holds exactly num_pad
     * bits here. Comparing all of acc — no mask — makes stray high bits
     * (payload that never reached the output) fail this check instead of
     * being silently stripped. */
    if (acc != (1U << num_pad) - 1U) {
        Py_DECREF(result);
        return radixly_raise_decode_error(num_chars - 1,
                                          "expected %u padding bits set to 1 in final character at index %zd",
                                          num_pad, num_chars - 1);
    }
    return result;
}
