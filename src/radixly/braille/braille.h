#ifndef RADIXLY_BRAILLE_H
#define RADIXLY_BRAILLE_H
#include <Python.h>

extern const char radixly_braille_encode_doc[];
PyObject *radixly_braille_encode(PyObject *self, PyObject *arg);

extern const char radixly_braille_decode_doc[];
PyObject *radixly_braille_decode(PyObject *self, PyObject *arg);

#endif // RADIXLY_BRAILLE_H
