# Codec registry

Each codec module also exposes its codec as a value — `radixly.base32768.BASE32768`
and so on — and registers it under its name. The registry is populated as soon as
`radixly` is imported.

```{eval-rst}
.. autoclass:: radixly.Codec
   :members:

.. autofunction:: radixly.get_codec
.. autofunction:: radixly.register
.. autodata:: radixly.CODECS
   :no-value:
```
