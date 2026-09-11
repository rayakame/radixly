# Codec registry

Each codec module also exposes its codec as a value, `radixly.base32768.BASE32768`
and so on, and registers it under its name. The registry is populated as soon as
`radixly` is imported.

```{eval-rst}
.. autoclass:: radixly.Codec

   .. method:: encode(data: collections.abc.Buffer, /) -> str

      Encode ``data`` with this codec.

   .. method:: decode(data: str, /) -> bytes

      Decode ``data`` with this codec.

   .. method:: encoded_len(num_bytes: int) -> int

      Exact output length in characters for a ``num_bytes``-byte payload,
      without encoding anything.

   .. method:: max_bytes(num_chars: int) -> int

      Largest payload that encodes into at most ``num_chars`` characters.

.. autofunction:: radixly.get_codec
.. autofunction:: radixly.register
.. autodata:: radixly.CODECS
   :no-value:
```
