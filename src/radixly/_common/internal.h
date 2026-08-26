#ifndef RADIXLY_INTERNAL_H
#define RADIXLY_INTERNAL_H

#ifdef __GNUC__
#define RADIXLY_SAME_TYPE(a, b) __builtin_types_compatible_p(__typeof__(a), __typeof__(b))

#define RADIXLY_MUST_BE_ARRAY(a) (0 * sizeof(int[1 - (2 * RADIXLY_SAME_TYPE(a, &(a)[0]))]))
#else
#define RADIXLY_MUST_BE_ARRAY(a) 0
#endif

#define RADIXLY_ARRAY_SIZE(a) ((sizeof(a) / sizeof((a)[0])) + RADIXLY_MUST_BE_ARRAY(a))

#endif /* RADIXLY_INTERNAL_H */
