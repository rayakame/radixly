# Base32768 conformance vectors

`pairs/` and `bad/` are vendored from qntm's base32768 test-data
(<https://github.com/qntm/base32768>), MIT licensed — see `LICENSE.txt`.

One exception: `pairs/seven-bit-final.{bin,txt}` is a radixly addition.
qntm's 264 pairs only ever exercise three of the 128 seven-bit characters
(z = 47, 63, 127), which leaves the `ƀ`..`Ɵ` block of the 7-bit repertoire
unpinned. This vector's 14-byte payload (bytes 0x00..0x0D — 112 bits, i.e.
seven full 15-bit characters plus a 7-bit final) ends in `ƍ` (U+018D, z = 13)
from that block.

The expected encoding was produced by qntm's actual JS implementation
(base32768@5.0.1 under Node), not by radixly's reference codec, so the pin
stays external. To regenerate or verify (`.txt` is UTF-8 with no trailing
newline — see `.gitattributes`):

```sh
npm install base32768@5.0.1
node --input-type=module -e '
  import { encode } from "base32768";
  import { writeFileSync } from "node:fs";
  const payload = Uint8Array.from({ length: 14 }, (_, i) => i);
  writeFileSync("seven-bit-final.bin", payload);
  writeFileSync("seven-bit-final.txt", encode(payload));
'
```
