#ifndef RADIXLY_ERRORS_H
#define RADIXLY_ERRORS_H
#include <Python.h>

int radixly_errors_exec(PyObject *module);

PyObject *radixly_raise_decode_error(Py_ssize_t position, const char *format, ...);

#endif // RADIXLY_ERRORS_H
