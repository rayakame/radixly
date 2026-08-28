#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "block.h"

#include "errors.h"
#include "internal.h"

PyObject *
radixly_block_encode(PyObject *arg, Py_UCS4 start, unsigned bits_per_char)
{
    assert(bits_per_char >= 1 && bits_per_char <= 15);
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len == 0) {
        PyBuffer_Release(&view);
        return PyUnicode_New(0, 0);
    }
    const unsigned ceil_pad = bits_per_char - 1;
    if (view.len > (PY_SSIZE_T_MAX - ceil_pad) / BITS_PER_BYTE) {
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    const Py_ssize_t n_chars = ((BITS_PER_BYTE * view.len) + ceil_pad) / bits_per_char;
    const Py_UCS4 max_char = start + (1U << bits_per_char) - 1;
    assert(0x100 <= max_char && max_char <= 0xFFFF);
    PyObject *result = PyUnicode_New(n_chars, max_char);
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

        while (num_bits >= bits_per_char) {
            num_bits -= bits_per_char;
            out[out_i] = (Py_UCS2)(start + (acc >> num_bits));
            out_i++;
            acc &= (1U << num_bits) - 1;
        }
    }

    if (num_bits > 0) {
        const unsigned gap = bits_per_char - num_bits;
        acc = (acc << gap) | ((1U << gap) - 1);
        out[out_i] = (Py_UCS2)(start + acc);
        out_i++;
    }
    assert(out_i == n_chars);
    PyBuffer_Release(&view);
    return result;
}

PyObject *
radixly_block_decode(PyObject *arg, Py_UCS4 start, unsigned bits_per_char)
{
    assert(bits_per_char >= 1 && bits_per_char <= 15);
    const Py_UCS4 max_char = start + (1U << bits_per_char) - 1;
    assert(0x100 <= max_char && max_char <= 0xFFFF);
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
    if (num_chars > PY_SSIZE_T_MAX / bits_per_char) {
        return PyErr_NoMemory();
    }
    int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);
    const Py_ssize_t total_bits = num_chars * bits_per_char;
    Py_ssize_t num_bytes = total_bits / BITS_PER_BYTE;
    unsigned num_pad = (unsigned)(total_bits % BITS_PER_BYTE);
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
        /* These two comparisons are the whole reverse table: surrogates and
         * astral characters land in the same rejection. */
        if (code_point < start || code_point > max_char) {
            Py_DECREF(result);
            return radixly_raise_decode_error(i, "invalid character U+%x at index %zd", (unsigned)code_point,
                                              i);
        }
        acc = (acc << bits_per_char) | (code_point - start);
        bits += bits_per_char;
        while (bits >= BITS_PER_BYTE) {
            bits -= BITS_PER_BYTE;
            out[out_i] = (char)((acc >> bits) & BYTE_MASK);
            out_i++;
            acc &= (1U << bits) - 1U;
        }
    }
    assert(out_i == num_bytes);

    /* Canonicality (fixed decision, lockstep with tests/reference/block.py):
     * the final character must carry at least one payload bit. Checked after
     * the character scan although the length alone decides it: an invalid
     * character must win the position race, matching the reference. */
    if (bits_per_char <= num_pad) {
        Py_DECREF(result);
        return radixly_raise_decode_error(
            num_chars - 1, "non-canonical input: %u-bit final character at index %zd carries no payload bits",
            bits_per_char, num_chars - 1);
    }

    /* acc holds exactly num_pad bits; comparing it unmasked makes stray bits fail. */
    if (acc != (1U << num_pad) - 1U) {
        Py_DECREF(result);
        return radixly_raise_decode_error(num_chars - 1,
                                          "expected %u padding bits set to 1 in final character at index %zd",
                                          num_pad, num_chars - 1);
    }
    return result;
}
