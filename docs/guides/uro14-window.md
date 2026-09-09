# The uro14 length window

uro14 prefixes every encoding with one character that claims the payload
length. The claim is 14 bits wide, so it wraps at 16,384 bytes.

Below the modulus the guarantee is absolute: a truncated string never decodes
to a wrong length. At and above it, a claim-matching truncation of a bigger
payload can be byte-identical to a valid shorter encoding when its cut point
leaves no padding, and no decoder can tell two meanings of one string apart.
Payload sizes are not capped — the window is the documented limit of the
guarantee, not of the codec.

:::{note}
This guide is a skeleton; the illustration is still being written.
:::
