#ifndef RADIXLY_HEXAGRAM_H
#define RADIXLY_HEXAGRAM_H
#include <Python.h>

extern const char radixly_hexagram_encode_doc[];
PyObject *radixly_hexagram_encode(PyObject *self, PyObject *arg);

extern const char radixly_hexagram_decode_doc[];
PyObject *radixly_hexagram_decode(PyObject *self, PyObject *arg);

#endif // RADIXLY_HEXAGRAM_H
