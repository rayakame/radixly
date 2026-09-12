# Choosing a codec

All nine codecs turn bytes into a string and back. They differ in how many
characters they need, which characters they use, and whether a string that
was cut short is caught. Start from your constraint, not from the codec.

| codec | bits per char | characters for `n` bytes | 100 chars hold | alphabet | catches truncation |
|---|---|---|---|---|---|
| {doc}`../codecs/base65536` | 16 | `ceil(n / 2)` | 200 bytes | 65,792 code points in 257 blocks, most of them astral | no |
| {doc}`../codecs/base32768` | 15 | `ceil(8n / 15)` | 187 bytes | 32,768 code points across many BMP blocks | partly |
| {doc}`../codecs/base2048` | 11 | `ceil(8n / 11)` | 137 bytes | 2,048 letters and numerals, all below U+1100 | partly |
| {doc}`../codecs/uro14` | 14 | `1 + ceil(8n / 14)` | 173 bytes | one CJK block, 16,384 code points | yes, below 16,384 bytes |
| {doc}`../codecs/braille` | 8 | `n` | 100 bytes | one block, 256 Braille patterns | no |
| {doc}`../codecs/hexagram` | 6 | `ceil(8n / 6)` | 75 bytes | one block, 64 hexagrams | partly |
| {doc}`../codecs/base32` | 5 | `8 * ceil(n / 5)` | 60 bytes | `A` to `Z`, `2` to `7`, `=` padding | partly |
| {doc}`../codecs/base32hex` | 5 | `8 * ceil(n / 5)` | 60 bytes | `0` to `9`, `A` to `V`, `=` padding | partly |
| {doc}`../codecs/base16` | 4 | `2n` | 50 bytes | 16 uppercase hexadecimal digits | no |

In the last column, *yes* means every cut below the stated size raises,
*partly* that most cuts raise but a cut at the right place passes, and *no*
that half or more of the cuts pass.

## Does the channel count characters or bytes?

radixly pays off when the limit is a character count: a field, an identifier,
a filename. If the limit is in bytes, every one of these characters costs one
to four bytes as UTF-8 and base64 or raw binary will beat all of them. That is
not a weakness to work around, it is the wrong tool.

One more question for the densest option: does the channel count code points
or UTF-16 code units? base65536 lives mostly outside the BMP, where each
character is two code units. A JavaScript `length`, a Java `String`, or
anything else that counts UTF-16 will see it as sparser than base32768: an
astral character carries 8 bits per code unit against base32768's 15.

## Does a cut-off string have to be caught?

Only uro14 can tell that a string is incomplete, thanks to its length
prefix, and only for payloads under 16,384 bytes. The others decode a
truncated string either without complaint (braille and base65536 always,
base32768 and base2048 just under a quarter of the time, hexagram about a
third, base16 half, base32 and base32hex one cut in eight) or with an error
that depends on where the cut landed. If that matters and uro14 does not fit,
carry a length or a checksum yourself.

## How narrow does the alphabet have to be?

The fewer distinct characters a codec uses, the more channels accept it
unchanged. base16 is plain ASCII letters and digits, which every channel
takes; base32 and base32hex add `=` padding on most lengths, and base32 is
the one for case-insensitive channels.
Among the Unicode codecs, hexagram uses 64 symbols from one block, braille
256, uro14 one block of 16,384 ideographs, base2048 letters and numerals from
two dozen scripts, base32768 characters from many BMP blocks, base65536
blocks from three planes. All of them avoid whitespace, control characters
and combining marks, so the usual suspects (chat clients, databases,
normalizing frameworks) pass them through. base2048 is the one whose output
can look like ordinary text, and base65536 the one a channel might reject
for leaving the BMP.

## Speed is not the deciding factor

None of the nine is slow. Pick by alphabet and truncation behavior; the
numbers on each codec page are there to confirm that whichever you pick will
not be the bottleneck.