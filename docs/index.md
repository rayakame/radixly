# radixly

radixly is a fast Python library for binary-to-text codecs. It ships the
codecs you reach for when bytes have to travel as a string, each one
implemented in C and exposed through the same small interface, so switching
from one to another is a change of import.

## What makes it different

**Speed.** Every codec is a hand-written C extension with no Python in the
hot path. Pull requests are gated on its speed relative to a pure-Python
reference of the same algorithm, and the numbers on each codec page are a
committed record from the benchmark suite that ships with the repository.

**One interface.** Every codec offers `encode`, `decode` and the size math
to plan around a length limit, with type stubs and no dependencies.

**A drop-in for the standard library.** {doc}`compat` is the `base64`
module with the same names, arguments and errors, ported to C family by
family.

## Codecs

::::{grid} 2
:gutter: 3

:::{grid-item-card} base16
:link: codecs/base16
:link-type: doc
Two hexadecimal digits per byte, RFC 4648. Reach over density.
:::

:::{grid-item-card} base32
:link: codecs/base32
:link-type: doc
Letters and digits only, RFC 4648. For case-insensitive channels.
:::

:::{grid-item-card} base32hex
:link: codecs/base32hex
:link-type: doc
base32 whose alphabet sorts like the bytes.
:::

:::{grid-item-card} base32768
:link: codecs/base32768
:link-type: doc
15 bits per character from qntm's alphabet of 32,768 BMP code points.
:::

:::{grid-item-card} base65536
:link: codecs/base65536
:link-type: doc
Two bytes per code point, the densest of the set. Most of its blocks are astral.
:::

:::{grid-item-card} base2048
:link: codecs/base2048
:link-type: doc
11 bits per character, all below U+1100. Letters and numerals from two dozen scripts.
:::

:::{grid-item-card} uro14
:link: codecs/uro14
:link-type: doc
14 bits per character from one CJK block, with a length prefix that catches truncation below 16,384 bytes.
:::

:::{grid-item-card} braille
:link: codecs/braille
:link-type: doc
One Braille pattern per byte. Bytes as plain text.
:::

:::{grid-item-card} hexagram
:link: codecs/hexagram
:link-type: doc
One I Ching hexagram per six bits. base64's density in a single block.
:::

::::

## Next steps

- {doc}`guides/getting-started` installs radixly and walks through a first
  round trip.
- {doc}`guides/choosing-a-codec` compares the nine codecs side by side.
- Source, issues and releases live on [GitHub](https://github.com/rayakame/radixly).

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
