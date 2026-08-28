#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "hexagram.h"

#include "_common/block.h"

enum {
    HEXAGRAM_START = 0x4DC0,
    HEXAGRAM_BITS_PER_CHAR = 6,
};

const char radixly_hexagram_encode_doc[] =
    PyDoc_STR("hexagram_encode($module, data, /)\n"
              "--\n"
              "\n"
              "Encode a bytes-like object as Yijing hexagrams, 6 bits per character.");
PyObject *
radixly_hexagram_encode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_block_encode(arg, HEXAGRAM_START, HEXAGRAM_BITS_PER_CHAR);
}

const char radixly_hexagram_decode_doc[] =
    PyDoc_STR("hexagram_decode($module, data, /)\n"
              "--\n"
              "\n"
              "Decode hexagram symbols back to bytes.\n"
              "\n"
              "Strict and canonical; DecodeError carries the offending position.");
PyObject *
radixly_hexagram_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_block_decode(arg, HEXAGRAM_START, HEXAGRAM_BITS_PER_CHAR);
}
