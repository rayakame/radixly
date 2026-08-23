#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "_tables.h"
#include "base32768.h"

enum {
    BITS_PER_BYTE = 8,
    BITS_PER_CHAR = 15,
    MAX_CHAR = 0xFFFF,
    CEIL_PAD = BITS_PER_CHAR - 1,
};

const char radixly_base32768_encode_doc[] = PyDoc_STR(
    "base32768_encode($module, data, /)\n"
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
    const Py_ssize_t n_chars =
        ((BITS_PER_BYTE * view.len) + CEIL_PAD) / BITS_PER_CHAR;

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
        if (num_bits <= (BITS_PER_CHAR - BITS_PER_BYTE)) {
            width = BITS_PER_CHAR - BITS_PER_BYTE;
        }
        else {
            width = BITS_PER_CHAR;
        }

        const unsigned gap = width - num_bits;
        acc = (acc << gap) | ((1U << gap) - 1);
        if (width == BITS_PER_CHAR) {
            out[out_i] = RADIXLY_B32768_FWD15[acc];
            out_i++;
        }
        else {
            out[out_i] = RADIXLY_B32768_FWD7[acc];
            out_i++;
        }
    }
    assert(out_i == n_chars);
    PyBuffer_Release(&view);
    return result;
}
