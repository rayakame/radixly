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
#ifndef RADIXLY_TEXT_H
#define RADIXLY_TEXT_H
#include <Python.h>

/* The text a strict decoder reads as bytes. A 1-byte str lends its own buffer. A wider str holds a character
 * outside ASCII, so its decode ends in an error at or before that character: the text through the end of that
 * character's group is copied, an invalid placeholder standing in from the character on, so every earlier
 * error keeps its place and the group shapes stay what they were. */
typedef struct {
    const unsigned char *text;
    Py_ssize_t len;
    Py_ssize_t wide_index; /* the placeholder's index, or -1 */
    Py_UCS4 wide_code_point;
    unsigned char *scratch;
} radixly_text;

/* 0 with text filled, -1 with the exception set: a TypeError for anything but a str. Release afterwards. */
int radixly_text_init(radixly_text *text, PyObject *arg, int group_chars);
void radixly_text_release(radixly_text *text);

/* The character at index as the caller saw it, the placeholder's real one included. */
Py_UCS4 radixly_text_code_point(const radixly_text *text, Py_ssize_t index);

#endif // RADIXLY_TEXT_H
