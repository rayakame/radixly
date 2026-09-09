# Choosing a codec

The trade is always the same: more bits per character means fewer characters
for the same payload, at the price of a wider, less "printable" alphabet.

| codec | bits / char | 100 code points hold | alphabet |
|---|---|---|---|
| base32768 | 15 | 187 bytes | 32,768 BMP code points (qntm's spec) |
| uro14 | 14 | 173 bytes | one contiguous CJK block from U+4E00, plus a length-prefix character |
| braille | 8 | 100 bytes | U+2800–U+28FF, one pattern per byte |
| hexagram | 6 | 75 bytes | U+4DC0–U+4DFF, one hexagram per six bits |

The motivating case is a Discord `custom_id`: 100 code points, counted as code
points, not bytes.

:::{note}
This guide is a skeleton; the decision walkthrough is still being written.
:::
