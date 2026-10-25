# Choosing a codec

All thirteen codecs turn bytes into a string and back. They differ in how many
characters they need, which characters they use, and whether a string cut short
is caught. Start from the channel, not from the codec.

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/choose.svg
```

## Characters or bytes?

radixly pays off when the limit is a count of characters: a form field, an
identifier, a file name. When the limit is in bytes, every non-ASCII character
costs two to four of them as UTF-8, and base64 or raw binary wins.

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/cost.svg
```

A channel that counts UTF-16 code units, like JavaScript's `length` or a Java
`String`, sees base65536's astral characters as two units each. There base32768
is the densest.

## Does a cut-off string have to be caught?

Only uro14 can tell that a string is incomplete, through its length prefix, for
every payload below 16,384 bytes. The others decode some cuts without an error,
to a shorter payload. If that matters and uro14 does not fit, carry a length or
a checksum yourself.

```{eval-rst}
.. raw:: html
   :file: ../_static/diagrams/truncation.svg
```

## How narrow does the alphabet have to be?

The fewer characters a codec uses, the more channels take it unchanged.

| channel | safe choices |
|---|---|
| anything that takes text | {doc}`../codecs/base16` |
| folds case | {doc}`../codecs/base32`, uppercased again before `decode` |
| sorted keys | {doc}`../codecs/base32hex` |
| URLs and file names | {doc}`../codecs/base64url` |
| JSON strings | {doc}`../codecs/base85`, {doc}`../codecs/z85`: no quote, no backslash |
| backquotes, pipes, `;`, `_`, `~` matter | {doc}`../codecs/z85` |
| Unicode, but nothing astral | {doc}`../codecs/base32768`, {doc}`../codecs/uro14` |
| Unicode below U+1100, text that reads as letters | {doc}`../codecs/base2048` |
| one small block of symbols | {doc}`../codecs/hexagram`, {doc}`../codecs/braille` |

Neither 85 alphabet is safe raw in Markdown or a shell, where `*`, `&`, `!`,
`<>` and brackets mean something: quote it, or use base64url. Every Unicode
codec avoids whitespace, control characters and combining marks, and survives
Unicode normalization, so chat clients, databases and normalizing frameworks
pass it through.

## All thirteen

| codec | bits per char | characters for `n` bytes | 100 chars hold | alphabet |
|---|---|---|---|---|
| {doc}`../codecs/base65536` | 16 | `ceil(n / 2)` | 200 bytes | 256 blocks of 256, most of them astral, and one for a final odd byte |
| {doc}`../codecs/base32768` | 15 | `ceil(8n / 15)` | 187 bytes | 32,768 BMP code points |
| {doc}`../codecs/uro14` | 14 | `1 + ceil(8n / 14)` | 173 bytes | 16,384 CJK ideographs |
| {doc}`../codecs/base2048` | 11 | `ceil(8n / 11)` | 137 bytes | 2,048 letters and numerals below U+1100 |
| {doc}`../codecs/braille` | 8 | `n` | 100 bytes | 256 Braille patterns |
| {doc}`../codecs/base85` | 6.4 | `ceil(5n / 4)` | 80 bytes | `0-9A-Za-z` and 23 punctuation marks |
| {doc}`../codecs/z85` | 6.4 | `ceil(5n / 4)` | 80 bytes | `0-9a-zA-Z` and 23 others, no quotes |
| {doc}`../codecs/base64` | 6 | `4 * ceil(n / 3)` | 75 bytes | `A-Za-z0-9+/`, `=` padding |
| {doc}`../codecs/base64url` | 6 | `4 * ceil(n / 3)` | 75 bytes | `A-Za-z0-9-_`, `=` padding |
| {doc}`../codecs/hexagram` | 6 | `ceil(8n / 6)` | 75 bytes | 64 hexagrams |
| {doc}`../codecs/base32` | 5 | `8 * ceil(n / 5)` | 60 bytes | `A-Z2-7`, `=` padding |
| {doc}`../codecs/base32hex` | 5 | `8 * ceil(n / 5)` | 60 bytes | `0-9A-V`, `=` padding |
| {doc}`../codecs/base16` | 4 | `2n` | 50 bytes | `0-9A-F` |

Speed is not the deciding factor: none of them is slow, and the benchmarks on
each codec page are there to confirm that whichever you pick will not be the
bottleneck.
