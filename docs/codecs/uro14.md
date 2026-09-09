# uro14

14 bits per character from one contiguous CJK block starting at U+4E00, with
a length-prefix character — radixly's own design.

## When to use it

Nearly base32768's density (173 bytes per 100 code points) from a single
contiguous block, plus truncation detection below the 16,384-byte window.

## Benchmarks

```{include} ../benchmarks/uro14.md
```

## The length window

The 14-bit length claim wraps at 16,384 bytes — see {doc}`../guides/uro14-window`.

## Reference

```{eval-rst}
.. currentmodule:: radixly.uro14

.. autofunction:: encode
.. autofunction:: decode
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. autodata:: BITS_PER_CHAR
.. data:: URO14
   :type: radixly.Codec

   The codec as a value, registered under ``"uro14"``.
```
