#ifndef RADIXLY_BLOCK_H
#define RADIXLY_BLOCK_H

PyObject *radixly_block_encode(PyObject *arg, Py_UCS4 start, unsigned bits_per_char);
PyObject *radixly_block_decode(PyObject *arg, Py_UCS4 start, unsigned bits_per_char);

#endif // RADIXLY_BLOCK_H
