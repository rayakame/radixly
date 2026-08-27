#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "braille.h"

#include "_common/block.h"

enum {
    BRAILLE_START = 0x2800,
    BRAILLE_BITS_PER_CHAR = 8,
};

const char radixly_braille_encode_doc[] =
    PyDoc_STR("braille_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as braille patterns, one byte per character.");
PyObject *
radixly_braille_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_block_encode(arg, BRAILLE_START, BRAILLE_BITS_PER_CHAR);
}

const char radixly_braille_decode_doc[] =
    PyDoc_STR("braille_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode braille patterns back to bytes.\n"
              "\n"
              "Strict and canonical; DecodeError carries the offending position.");
PyObject *
radixly_braille_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_block_decode(arg, BRAILLE_START, BRAILLE_BITS_PER_CHAR);
}
