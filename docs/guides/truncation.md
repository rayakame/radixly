# Truncation

None of these codecs carry a checksum. What happens when an encoded string is
cut short differs by codec, and it matters more than it looks.

## base32768 accepts about half of all truncations

A base32768 string cut at an arbitrary character is a valid encoding of a
*shorter* payload roughly half of the time: whenever the cut point leaves the
final character's padding bits in a shape the decoder accepts, `decode`
returns a prefix of the original bytes without raising. If you need to detect
truncation, carry the length or a checksum yourself.

## uro14 detects truncation — within its window

uro14's length-prefix character lets the decoder reject a body that does not
match the claimed length. That guarantee is windowed: see
{doc}`../codecs/uro14`.

:::{note}
This guide is a skeleton; the worked examples are still being written.
:::
