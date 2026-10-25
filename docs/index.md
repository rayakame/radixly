# radixly

Fast binary-to-text codecs for Python: thirteen of them, each a hand-written C
extension behind one small interface, and a drop-in for the standard library's
`base64` that runs every function in C.

```bash
pip install radixly
```

```python
import radixly

text = radixly.base32768.encode(b"hello")   # '媒腻㐿'
radixly.base32768.decode(text)              # b'hello'
radixly.base32768.max_bytes(100)            # 187
```

Every codec has `encode`, `decode`, `encoded_len` and `max_bytes`, typed, with
no dependencies. Decoding is strict: one payload, one spelling, and a
{class}`~radixly.DecodeError` that says where the text went wrong.

## Pick a codec

Start from the channel. If it counts characters, a Unicode codec carries two to
four times what base64 does; if it only takes ASCII, pick by alphabet.

```{eval-rst}
.. raw:: html
   :file: _static/diagrams/density.svg
```

```{eval-rst}
.. raw:: html
   :file: _static/diagrams/choose.svg
```

{doc}`guides/choosing-a-codec` has the full comparison, truncation behavior
included.

## Codecs

::::{grid} 2 2 3 3
:gutter: 2

:::{grid-item-card} base64
:link: codecs/base64
:link-type: doc
The one every channel speaks. 75 bytes per 100 characters.
:::

:::{grid-item-card} base64url
:link: codecs/base64url
:link-type: doc
base64 for URLs and file names.
:::

:::{grid-item-card} base32
:link: codecs/base32
:link-type: doc
Letters and digits only; survives case folding.
:::

:::{grid-item-card} base32hex
:link: codecs/base32hex
:link-type: doc
base32 whose text sorts like the bytes.
:::

:::{grid-item-card} base16
:link: codecs/base16
:link-type: doc
Hexadecimal. Reach over density.
:::

:::{grid-item-card} base85
:link: codecs/base85
:link-type: doc
Four bytes in five characters, git's alphabet.
:::

:::{grid-item-card} z85
:link: codecs/z85
:link-type: doc
base85 with ZeroMQ's quote-free alphabet.
:::

:::{grid-item-card} base32768
:link: codecs/base32768
:link-type: doc
15 bits per character, all in the BMP. 187 bytes per 100 characters.
:::

:::{grid-item-card} base65536
:link: codecs/base65536
:link-type: doc
Two bytes per character, the densest. Mostly astral.
:::

:::{grid-item-card} base2048
:link: codecs/base2048
:link-type: doc
11 bits per character that read like text.
:::

:::{grid-item-card} uro14
:link: codecs/uro14
:link-type: doc
14 bits per character and a length prefix that catches truncation.
:::

:::{grid-item-card} braille
:link: codecs/braille
:link-type: doc
One Braille pattern per byte.
:::

:::{grid-item-card} hexagram
:link: codecs/hexagram
:link-type: doc
One I Ching hexagram per six bits.
:::

::::

## Standard library drop-in

{doc}`compat` is the `base64` module with the same names, arguments, results
and errors, every function in C, on 3.11 through 3.15. Swap the import, keep
the behavior.

```python
from radixly.compat import base64
```

```{toctree}
:hidden:
:caption: Guides

guides/getting-started
guides/choosing-a-codec
guides/subinterpreters
```

```{toctree}
:hidden:
:caption: Codecs

codecs/base16
codecs/base32
codecs/base32hex
codecs/base64
codecs/base64url
codecs/base85
codecs/z85
codecs/base32768
codecs/base65536
codecs/base2048
codecs/uro14
codecs/braille
codecs/hexagram
```

```{toctree}
:hidden:
:caption: Standard library

compat
```

```{toctree}
:hidden:
:caption: Reference

reference/errors
reference/registry
```

```{toctree}
:hidden:
:caption: Project

changelog
```
