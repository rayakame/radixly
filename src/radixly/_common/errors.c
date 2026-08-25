#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "errors.h"

static PyObject *decode_error = NULL;

static const char radixly_decode_error_doc[] =
    PyDoc_STR("Malformed or non-canonical input was rejected during decoding.\n"
              "\n"
              "Subclasses ValueError, so existing `except ValueError` handlers keep\n"
              "working. The `position` attribute carries the index of the offending\n"
              "character in the input string.");

int
radixly_errors_exec(PyObject *module)
{
    int created = 0;
    if (decode_error == NULL) {
        decode_error = PyErr_NewExceptionWithDoc("radixly._core.DecodeError", radixly_decode_error_doc,
                                                 PyExc_ValueError, NULL);
        if (decode_error == NULL) {
            return -1;
        }
        created = 1;
    }

    if (PyModule_AddObjectRef(module, "DecodeError", decode_error) < 0) {
        if (created == 1) {
            Py_CLEAR(decode_error);
        }
        return -1;
    }

    return 0;
}