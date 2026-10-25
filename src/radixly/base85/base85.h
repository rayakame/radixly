/*
 * Copyright (c) 2026-present rayakame
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
#ifndef RADIXLY_BASE85_H
#define RADIXLY_BASE85_H
#include <Python.h>

extern int radixly_base85_exec(PyObject *module);

/* The engine every 85-digit shape shares: base85, Z85 and Ascii85 differ in their alphabets alone. */

enum { RADIXLY_B85_STD, RADIXLY_B85_Z85, RADIXLY_B85_A85 };
enum {
    RADIXLY_B85_INVALID = 0xFF,
    RADIXLY_B85_TABLE_SIZE = 256,
    RADIXLY_B85_WORD_BYTES = 4,
    RADIXLY_B85_WORD_DIGITS = 5,
};

const char *radixly_b85_alphabet(int which);

/* The reverse table of an alphabet: its 85 values, everything else invalid. */
const unsigned char *radixly_b85_table(int which);

/* Up to four bytes as one big-endian word, the missing ones zero. */
uint32_t radixly_b85_word(const unsigned char *data, Py_ssize_t count);

/* The top count bytes of a word, big-endian. */
void radixly_b85_put_word(unsigned char *out, uint32_t word, int count);

/* The five digits of a word, most significant first. */
void radixly_b85_digits(uint32_t word, unsigned char *out, int which);

/* Encode whole words; returns the bytes consumed, a multiple of four. */
Py_ssize_t radixly_b85_fill(const unsigned char *data, Py_ssize_t len, unsigned char *out, int which);

/* Decode whole groups of five digits from the start; returns the characters consumed, a multiple of five,
 * stopping before the first group holding a non-digit or spelling a word above 32 bits, and with zero_stops
 * before a zero word too, which a canonical Ascii85 reading has to judge. */
Py_ssize_t radixly_b85_groups(const unsigned char *text, Py_ssize_t len, unsigned char *out,
                              const unsigned char *rev, int zero_stops);

/* binascii's canonical tail: a word spelled by chunk_len + 1 digits is the encoder's own when its dropped
 * bytes read as zero. */
int radixly_b85_canonical_tail(uint32_t word, int chunk_len);

PyObject *radixly_base85_encode_with(PyObject *arg, int which);
PyObject *radixly_base85_decode_with(PyObject *arg, int which);
extern const char radixly_base85_encode_doc[];
PyObject *radixly_base85_encode(PyObject *self, PyObject *arg);
extern const char radixly_base85_decode_doc[];
PyObject *radixly_base85_decode(PyObject *self, PyObject *arg);

/* The drop-in: base85/compat.c, shared with ascii85.c. */

/* The stdlib's pure-Python encoder before 3.15: words of five digits, 'z' for a zero word when fold_nuls, 'y'
 * for four spaces when fold_spaces is true (read when the first such word comes up), the tail's padding
 * digits dropped unless pad is true. */
PyObject *radixly_85_encode(const unsigned char *data, Py_ssize_t len, int which, PyObject *pad,
                            int fold_nuls, PyObject *fold_spaces);

/* The stdlib's pure-Python decoder before 3.15: the input padded with the top digit to whole groups, its
 * errors with their contexts; codec names the format in them. */
PyObject *radixly_85_decode(const unsigned char *data, Py_ssize_t len, int which, const char *codec);

/* binascii's bound for an 85 encoding: whole groups, the frame, the dropped padding and the newlines. */
size_t radixly_b85_bound(Py_ssize_t len, size_t wrapcol, int pad, size_t frame);

/* The bytes of a full group: four, or the one to three a tail spells; 0 is the lone character binascii
 * refuses.
 */
int radixly_b85_chunk_length(Py_ssize_t len);

/* The digit's place in the word; 1 when the fifth digit would carry the word past 32 bits. */
int radixly_b85_take_digit(uint32_t *leftchar, int *group_pos, unsigned digit);

extern const char radixly_b85encode_doc[];
PyObject *radixly_b85encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b85decode_doc[];
PyObject *radixly_b85decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_z85encode_doc[];
PyObject *radixly_z85encode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_z85decode_doc[];
PyObject *radixly_z85decode(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b85encode_py315_doc[];
PyObject *radixly_b85encode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_b85decode_py315_doc[];
PyObject *radixly_b85decode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_z85encode_py315_doc[];
PyObject *radixly_z85encode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);
extern const char radixly_z85decode_py315_doc[];
PyObject *radixly_z85decode_py315(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames);

#endif // RADIXLY_BASE85_H
