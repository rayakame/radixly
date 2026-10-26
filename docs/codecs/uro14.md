# uro14

radixly's own design: 14 bits per character from one block of CJK ideographs, with a length prefix that catches truncation.

::::{grid} 2 4 4 4
:gutter: 2

:::{grid-item-card} 14 bits
per character
:::
:::{grid-item-card} 7 → 4
bytes to characters, plus one prefix
:::
:::{grid-item-card} 173 bytes
in 100 characters
:::
:::{grid-item-card} no cut
passes below 16,384 bytes
:::

::::

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/uro14-group.svg
```

```python
from radixly import uro14

text = uro14.encode(bytes(range(20)))   # 13 characters: the prefix, then 12
uro14.decode(text)                       # the 20 bytes
uro14.decode(text[:12])                  # DecodeError at position 0
```

## Alphabet

The 16,384 ideographs U+4E00 to U+8DFF, every one assigned and printable. The first character states the payload length modulo 16,384; the decoder uses it to check that the body is complete and to settle which of two lengths a body could mean. The text reads as Chinese to a human eye and to any tool that guesses languages.

::::{grid} 1 2 2 2
:gutter: 2

:::{grid-item-card} Use it for
Payloads that must not be accepted when cut short, at a cost of 14 bytes per 100 characters against base32768.
:::

:::{grid-item-card} Reach for another codec when
the channel counts bytes (three per character as UTF-8), or capacity matters more than catching a truncation ({doc}`base32768`).
:::

::::

## Truncation

The prefix is a checksum on length: a shortened body no longer holds what the prefix claims, and {class}`~radixly.DecodeError` is raised at position 0, for every cut of every payload below 16,384 bytes. Above that the claim wraps, and about one cut in sixty thousand slips through on random data.

## Benchmarks

```{include} ../benchmarks/uro14.md
```

## Reference

```{eval-rst}
.. currentmodule:: radixly.uro14

.. autofunction:: encode(data: collections.abc.Buffer, /) -> str
.. autofunction:: decode(data: str, /) -> bytes
.. autofunction:: encoded_len
.. autofunction:: max_bytes
.. data:: BITS_PER_CHAR
   :type: float
   :value: 14.0

   Payload bits carried by one body character; the length prefix is one character on top.

.. data:: URO14
   :type: radixly.Codec

   The codec as a value, registered under ``"uro14"``.
```
