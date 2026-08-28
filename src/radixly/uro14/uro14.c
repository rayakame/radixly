#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "uro14.h"

#include "_common/errors.h"
#include "_common/internal.h"

enum {
    URO14_START = 0x4E00,
    URO14_BITS_PER_CHAR = 14,
    URO14_MODULUS = 16384, /* 1 << URO14_BITS_PER_CHAR */
    URO14_MAX_CHAR = URO14_START + URO14_MODULUS - 1,
    URO14_CEIL_PAD = URO14_BITS_PER_CHAR - 1,
};

const char radixly_uro14_encode_doc[] =
    PyDoc_STR("uro14_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as uro14: a length character, then the\n"
              "body at 14 bits per CJK character.");
PyObject *
radixly_uro14_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) == -1) {
        return NULL;
    }
    if (view.len > (PY_SSIZE_T_MAX - URO14_CEIL_PAD) / BITS_PER_BYTE) {
        PyBuffer_Release(&view);
        return PyErr_NoMemory();
    }
    const Py_ssize_t n_body = ((BITS_PER_BYTE * view.len) + URO14_CEIL_PAD) / URO14_BITS_PER_CHAR;

    PyObject *result = PyUnicode_New(1 + n_body, URO14_MAX_CHAR);
    if (result == NULL) {
        PyBuffer_Release(&view);
        return result;
    }
    Py_UCS2 *out = PyUnicode_2BYTE_DATA(result);
    out[0] = (Py_UCS2)(URO14_START + (view.len % URO14_MODULUS));

    const unsigned char *data = view.buf;
    uint32_t acc = 0;
    unsigned num_bits = 0;
    Py_ssize_t out_i = 1;
    for (Py_ssize_t i = 0; i < view.len; i++) {
        acc = (acc << (unsigned)BITS_PER_BYTE) | data[i];
        num_bits += BITS_PER_BYTE;

        while (num_bits >= URO14_BITS_PER_CHAR) {
            num_bits -= URO14_BITS_PER_CHAR;
            out[out_i] = (Py_UCS2)(URO14_START + (acc >> num_bits));
            out_i++;
            acc &= (1U << num_bits) - 1;
        }
    }

    if (num_bits > 0) {
        const unsigned gap = URO14_BITS_PER_CHAR - num_bits;
        acc = (acc << gap) | ((1U << gap) - 1);
        out[out_i] = (Py_UCS2)(URO14_START + acc);
        out_i++;
    }
    assert(out_i == 1 + n_body);
    PyBuffer_Release(&view);
    return result;
}

const char radixly_uro14_decode_doc[] =
    PyDoc_STR("uro14_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode uro14 text back to bytes.\n"
              "\n"
              "Strict and canonical; DecodeError carries the offending position.\n"
              "Every tail truncation of a payload under 16,384 bytes is rejected;\n"
              "bigger payloads wrap the length claim (see the codec docs).");
PyObject *
radixly_uro14_decode(PyObject *Py_UNUSED(self), PyObject *arg)
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
        return radixly_raise_decode_error(0, "empty string: missing the length prefix");
    }
    int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);

    const Py_UCS4 first = PyUnicode_READ(kind, data, 0);
    if (first < URO14_START || first > URO14_MAX_CHAR) {
        return radixly_raise_decode_error(0, "invalid character U+%x at index 0", (unsigned)first);
    }
    const Py_ssize_t claim = (Py_ssize_t)(first - URO14_START);

    const Py_ssize_t num_body = num_chars - 1;
    if (num_body > PY_SSIZE_T_MAX / URO14_BITS_PER_CHAR) {
        return PyErr_NoMemory();
    }
    /* A 14-bit single-width alphabet can leave up to 13 padding bits -- more
     * than a byte -- so the bit stream alone cannot say where the payload
     * ends. The claim resolves it: a body of k characters fits at most two
     * payload lengths (ceil(8n/14) == k), and the claim picks one. That is
     * the prefix's second job, after making every tail truncation
     * detectable. Lockstep with tests/reference/uro14.py. */
    const Py_ssize_t upper = URO14_BITS_PER_CHAR * num_body / BITS_PER_BYTE;
    Py_ssize_t payload_len = -1;
    for (Py_ssize_t cand = upper; cand >= upper - 1; cand--) {
        const int fits =
            cand >= 0 && ((BITS_PER_BYTE * cand) + URO14_CEIL_PAD) / URO14_BITS_PER_CHAR == num_body;
        if (fits && cand % URO14_MODULUS == claim) {
            payload_len = cand;
            break;
        }
    }
    if (payload_len == -1) {
        return radixly_raise_decode_error(
            0, "length prefix claims %zd bytes, impossible for %zd body characters", claim, num_body);
    }

    PyObject *result = PyBytes_FromStringAndSize(NULL, payload_len);
    if (result == NULL) {
        return NULL;
    }
    char *out = PyBytes_AS_STRING(result);

    uint32_t acc = 0;
    unsigned num_bits = 0;
    Py_ssize_t out_i = 0;
    for (Py_ssize_t i = 1; i < num_chars; i++) {
        const Py_UCS4 code_point = PyUnicode_READ(kind, data, i);
        if (code_point < URO14_START || code_point > URO14_MAX_CHAR) {
            Py_DECREF(result);
            return radixly_raise_decode_error(i, "invalid character U+%x at index %zd", (unsigned)code_point,
                                              i);
        }
        acc = (acc << (unsigned)URO14_BITS_PER_CHAR) | (code_point - URO14_START);
        num_bits += URO14_BITS_PER_CHAR;
        while (num_bits >= BITS_PER_BYTE && out_i < payload_len) {
            num_bits -= BITS_PER_BYTE;
            out[out_i] = (char)((acc >> num_bits) & BYTE_MASK);
            out_i++;
            acc &= (1U << num_bits) - 1U;
        }
    }
    assert(out_i == payload_len);

    /* 0..13 bits remain; unmasked comparison so stray bits fail loudly. */
    if (acc != (1U << num_bits) - 1U) {
        Py_DECREF(result);
        return radixly_raise_decode_error(num_chars - 1,
                                          "expected %u padding bits set to 1 in final character at index %zd",
                                          num_bits, num_chars - 1);
    }
    return result;
}
