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
#ifndef RADIXLY_INTERNAL_H
#define RADIXLY_INTERNAL_H

#define BITS_PER_BYTE 8

static const uint32_t BYTE_MASK = 0xFF;

#ifdef __GNUC__
#define RADIXLY_SAME_TYPE(a, b) __builtin_types_compatible_p(__typeof__(a), __typeof__(b))

#define RADIXLY_MUST_BE_ARRAY(a) (0 * sizeof(int[1 - (2 * RADIXLY_SAME_TYPE(a, &(a)[0]))]))
#else
#define RADIXLY_MUST_BE_ARRAY(a) 0
#endif

#define RADIXLY_ARRAY_SIZE(a) ((sizeof(a) / sizeof((a)[0])) + RADIXLY_MUST_BE_ARRAY(a))

#endif /* RADIXLY_INTERNAL_H */
