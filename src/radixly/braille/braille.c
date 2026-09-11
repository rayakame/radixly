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
              "Encode a bytes-like object as braille patterns.\n"
              "\n"
              "One character per byte: byte ``b`` becomes the pattern ``U+2800 + b``,\n"
              "so the output is exactly as long as the input and never needs\n"
              "padding.\n"
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
              ">>> from radixly import braille\n"
              ">>> len(braille.encode(b'hi'))\n"
              "2\n"
              ">>> braille.decode(braille.encode(b'hi'))\n"
              "b'hi'");
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
              "Strict: every character must lie in U+2800..U+28FF.\n"
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
              "    On malformed input; ``position`` is the index of the offending\n"
              "    character.\n"
              "\n"
              "Examples\n"
              "--------\n"
              ">>> import radixly\n"
              ">>> try:\n"
              "...     radixly.braille.decode('!')\n"
              "... except radixly.DecodeError as error:\n"
              "...     error.position\n"
              "0");
PyObject *
radixly_braille_decode(PyObject *Py_UNUSED(self), PyObject *arg)
{
    return radixly_block_decode(arg, BRAILLE_START, BRAILLE_BITS_PER_CHAR);
}
