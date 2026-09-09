# braille

8 bits per character: every byte becomes one Braille pattern (U+2800–U+28FF).
A preset of the contiguous-block factory.

## When to use it

One character per byte — no density gain over bytes, but a visually uniform,
single-block alphabet that survives channels which mangle wider ranges.

## Benchmarks

```{include} ../benchmarks/braille.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.braille

.. autofunction:: encode
.. autofunction:: decode
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. autodata:: BITS_PER_CHAR
.. data:: BRAILLE
   :type: radixly.Codec

   The codec as a value, registered under ``"braille"``.
```
