#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "base32768/base32768.h"
#include "_common/errors.h"

static PyMethodDef radixly_methods[] = {
    {"base32768_encode", radixly_base32768_encode, METH_O, radixly_base32768_encode_doc},
    {"base32768_decode", radixly_base32768_decode, METH_O, radixly_base32768_decode_doc},
    {NULL, NULL, 0, NULL},
};

static PyModuleDef_Slot radixly_execs[] = {
/* Static globals make this module single-interpreter only; 3.11 cannot refuse (see README). */
#if PY_VERSION_HEX >= 0x030C0000
    {Py_mod_multiple_interpreters, Py_MOD_MULTIPLE_INTERPRETERS_NOT_SUPPORTED},
#endif
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