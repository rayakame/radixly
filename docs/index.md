# radixly

radixly encodes bytes as text for channels that count characters, not bytes.
Where base64 spends a whole character on six bits, radixly's codecs pack up
to fifteen bits into a single Unicode code point, so a 100-character field
holds 187 bytes instead of 75.

## What makes it different

**It is fast.** Every codec is a hand-written C extension with no Python in
the hot path, measured on every commit against a pure-Python reference of the
same algorithm. The numbers on each codec page come from the benchmark suite
that ships with the repository.

**Decoding is strict.** One payload has exactly one accepted spelling. An
invalid character, broken padding or a non-canonical final character raises
a {class}`~radixly.DecodeError` that tells you the position, instead of
quietly returning something.

**The alphabets are chosen, not just counted.** Each codec draws from
assigned, printable code points with no whitespace, control characters or
combining marks, so the text survives chat clients, databases and
normalizing frameworks unchanged.

**It is typed and small.** Four codecs behind one consistent interface,
shipped with type stubs and no dependencies.

## Codecs

::::{grid} 2
:gutter: 3

:::{grid-item-card} base32768
:link: codecs/base32768
:link-type: doc
15 bits per character from qntm's alphabet of 32,768 BMP code points.
:::

:::{grid-item-card} uro14
:link: codecs/uro14
:link-type: doc
14 bits per character from one CJK block, with a length prefix that catches truncation.
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
- {doc}`guides/choosing-a-codec` compares the four codecs side by side.
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
