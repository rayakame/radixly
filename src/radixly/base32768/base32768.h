#ifndef RADIXLY_BASE32768_H
#define RADIXLY_BASE32768_H
#include <Python.h>

extern int radixly_base32768_exec(PyObject *module);

extern const char radixly_base32768_encode_doc[];
PyObject *radixly_base32768_encode(PyObject *self, PyObject *arg);

extern const char radixly_base32768_decode_doc[];
PyObject *radixly_base32768_decode(PyObject *self, PyObject *arg);

#endif // RADIXLY_BASE32768_H
