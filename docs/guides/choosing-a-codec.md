# Choosing a codec

All four codecs turn bytes into a string and back. They differ in how many
characters they need, which characters they use, and whether a string that
was cut short is caught. Start from your constraint, not from the codec.

| codec | bits per char | characters for `n` bytes | 100 chars hold | alphabet | catches truncation |
|---|---|---|---|---|---|
| {doc}`../codecs/base32768` | 15 | `ceil(8n / 15)` | 187 bytes | 32,768 code points across many BMP blocks | no |
| {doc}`../codecs/uro14` | 14 | `1 + ceil(8n / 14)` | 173 bytes | one CJK block, 16,384 code points | yes, below 16,384 bytes |
| {doc}`../codecs/braille` | 8 | `n` | 100 bytes | one block, 256 Braille patterns | no |
| {doc}`../codecs/hexagram` | 6 | `ceil(8n / 6)` | 75 bytes | one block, 64 hexagrams | partly |

## Does the channel count characters or bytes?

radixly pays off when the limit is a character count: a field, an identifier,
a filename. If the limit is in bytes, every one of these characters costs
three bytes as UTF-8 and base64 or raw binary will beat all of them. That is
not a weakness to work around, it is the wrong tool.

## Does a cut-off string have to be caught?

Only uro14 can tell that a string is incomplete, thanks to its length
prefix, and only for payloads under 16,384 bytes. The others decode a
truncated string either without complaint (braille always, base32768 about
a quarter of the time, hexagram about a third) or with an error that depends
on where the cut landed. If that matters and uro14 does not fit, carry a
length or a checksum yourself.

## How narrow does the alphabet have to be?

The fewer distinct characters a codec uses, the more channels accept it
unchanged. hexagram uses 64 symbols from one block, braille 256, uro14 one
block of 16,384 ideographs, base32768 characters from many blocks. All four
avoid whitespace, control characters and combining marks, so the usual
suspects (chat clients, databases, normalizing frameworks) pass them through.

## Speed is not the deciding factor

All four sit in the same range, roughly 0.1 to 0.3 microseconds per call at
200 bytes and hundreds of megabytes per second on large inputs. Pick by
alphabet and truncation behavior; the numbers on each codec page are there
to confirm that whichever you pick will not be the bottleneck.

## In short

When in doubt, base32768. If a cut-off string must be detected, uro14. If the
alphabet has to be small, hexagram; braille if bytes and characters should
line up one to one.
