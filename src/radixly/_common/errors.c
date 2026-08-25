#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stddef.h>
#include "errors.h"
#if PY_VERSION_HEX < 0x030C0000
#include <structmember.h>
#define Py_T_PYSSIZET T_PYSSIZET
#define Py_READONLY READONLY
#endif

typedef struct {
    PyBaseExceptionObject base;
    Py_ssize_t position;
} RadixlyDecodeErrorObject;

static const char radixly_decode_error_doc[] =
    PyDoc_STR("Malformed or non-canonical input was rejected during decoding.\n"
              "\n"
              "Subclasses ValueError, so existing `except ValueError` handlers keep\n"
              "working. The `position` attribute carries the index of the offending\n"
              "character in the input string.");

static int
decode_error_init(PyObject *self, PyObject *args, PyObject *kwargs)
{
    Py_ssize_t position;
    PyObject *message = NULL;

    static char *kwlist[] = {"position", "message", NULL};
    if (PyArg_ParseTupleAndKeywords(args, kwargs, "n|$U:DecodeError", kwlist, &position, &message) == 0) {
        return -1;
    }

    ((RadixlyDecodeErrorObject *)self)->position = position;
    PyObject *msg;
    if (message == NULL) {
        msg = PyUnicode_FromFormat("Decode Error at position %zd", position);
        if (msg == NULL) {
            return -1;
        }
    }
    else {
        msg = Py_NewRef(message);
    }
    PyObject *base_args = PyTuple_Pack(1, msg);
    if (base_args == NULL) {
        Py_DECREF(msg);
        return -1;
    }
    int return_code = ((PyTypeObject *)PyExc_ValueError)->tp_init(self, base_args, NULL);
    Py_DECREF(base_args);
    Py_DECREF(msg);
    return return_code;
}

static PyMemberDef decode_error_members[] = {
    {"position", Py_T_PYSSIZET, offsetof(RadixlyDecodeErrorObject, position), Py_READONLY,
     PyDoc_STR("Index of the offending character in the input.")},
    {NULL},
};

static int
decode_error_traverse(PyObject *self, visitproc visit, void *arg)
{
    /* Instances of heap types own a strong reference to their type, and the
     * collector only learns about it here; ValueError's traverse is a
     * static-type traverse and will never report it for us. */
    Py_VISIT(Py_TYPE(self));
    return ((PyTypeObject *)PyExc_ValueError)->tp_traverse(self, visit, arg);
}

static int
decode_error_clear(PyObject *self)
{
    return ((PyTypeObject *)PyExc_ValueError)->tp_clear(self);
}

static PyObject *
decode_error_get_message(PyObject *self, void *Py_UNUSED(closure))
{
    PyObject *args = ((PyBaseExceptionObject *)self)->args;
    if (args == NULL) {
        Py_RETURN_NONE;
    }
    if (PyTuple_GET_SIZE(args) <= 0) {
        Py_RETURN_NONE;
    }
    PyObject *item = PyTuple_GET_ITEM(args, 0);
    return Py_NewRef(item);
}

static PyGetSetDef decode_error_getset[] = {
    {"message", decode_error_get_message, NULL,
     PyDoc_STR(
         "Human-readable description of the failure, or None if the exception was built without arguments."),
     NULL},
    {NULL},
};

static PyType_Slot decode_error_slots[] = {
    {Py_tp_doc, (void *)radixly_decode_error_doc},
    {Py_tp_init, (void *)decode_error_init},
    {Py_tp_members, decode_error_members},
    {Py_tp_traverse, (void *)decode_error_traverse},
    {Py_tp_clear, (void *)decode_error_clear},
    {Py_tp_getset, decode_error_getset},
    {0, NULL},
};

static PyType_Spec decode_error_spec = {
    .name = "radixly._core.DecodeError",
    .basicsize = sizeof(RadixlyDecodeErrorObject),
    // NOLINTNEXTLINE(hicpp-signed-bitwise)
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC,
    .slots = decode_error_slots,
};

static PyObject *decode_error = NULL;

int
radixly_errors_exec(PyObject *module)
{
    int created = 0;
    if (decode_error == NULL) {
        decode_error = PyType_FromModuleAndSpec(module, &decode_error_spec, PyExc_ValueError);
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

PyObject *
radixly_raise_decode_error(Py_ssize_t position, const char *format, ...)
{
    PyObject *msg = NULL;
    PyObject *args = NULL;
    PyObject *kwargs = NULL;
    PyObject *instance = NULL;

    va_list vargs;
    va_start(vargs, format);
    msg = PyUnicode_FromFormatV(format, vargs);
    va_end(vargs);
    if (msg == NULL) {
        goto done;
    }
    args = Py_BuildValue("(n)", position);
    if (args == NULL) {
        goto done;
    }
    kwargs = PyDict_New();
    if (kwargs == NULL) {
        goto done;
    }
    if (PyDict_SetItemString(kwargs, "message", msg) == -1) {
        goto done;
    }
    instance = PyObject_Call(decode_error, args, kwargs);
    if (instance == NULL) {
        goto done;
    }
    PyErr_SetObject(decode_error, instance);

done:
    Py_XDECREF(msg);
    Py_XDECREF(args);
    Py_XDECREF(kwargs);
    Py_XDECREF(instance);
    return NULL;
}