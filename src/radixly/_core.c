#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "base32768/base32768.h"
#include "_common/errors.h"

static PyMethodDef radixly_methods[] = {
    {"base32768_encode", radixly_base32768_encode, METH_O, radixly_base32768_encode_doc},
    {NULL, NULL, 0, NULL},
};

static PyModuleDef_Slot radixly_execs[] = {
    {Py_mod_exec, (void *)radixly_errors_exec},
    {Py_mod_exec, (void *)radixly_base32768_exec},
    {0, NULL},
};

static struct PyModuleDef radixly_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "radixly._core",
    .m_doc = "C implementations of radixly's encode/decode routines. Private "
             "module: import radixly's public API instead! Names and "
             "signatures here may change without notice.",
    .m_size = 0,
    .m_methods = radixly_methods,
    .m_slots = radixly_execs,
};

PyMODINIT_FUNC
PyInit__core(void)
{
    return PyModuleDef_Init(&radixly_module);
}