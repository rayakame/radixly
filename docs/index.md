# radixly

Dense binary-to-text codecs that pack many bits per Unicode code point — for
channels limited by *code-point count* rather than bytes. A hand-written
CPython C extension, built to be the fastest Python implementation of these
codecs.

```python
import radixly

text = radixly.base32768.encode(b"\x00\x01\x02\x03")   # 3 characters for 4 bytes
data = radixly.base32768.decode(text)
```

::::{grid} 2
:gutter: 3

:::{grid-item-card} base32768
:link: codecs/base32768
:link-type: doc
15 bits per character, BMP only — qntm's specification.
:::

:::{grid-item-card} uro14
:link: codecs/uro14
:link-type: doc
14 bits per character from a contiguous CJK block, with a length-prefix character.
:::

:::{grid-item-card} braille
:link: codecs/braille
:link-type: doc
8 bits per character: one Braille pattern per byte.
:::

:::{grid-item-card} hexagram
:link: codecs/hexagram
:link-type: doc
6 bits per character: one I Ching hexagram per six bits.
:::

::::

```{toctree}
:hidden:
:caption: Guides

guides/getting-started
guides/choosing-a-codec
guides/truncation
guides/uro14-window
guides/subinterpreters
```

```{toctree}
:hidden:
:caption: Codecs

codecs/base32768
codecs/uro14
codecs/braille
codecs/hexagram
```

```{toctree}
:hidden:
:caption: Reference

reference/errors
reference/registry
```
