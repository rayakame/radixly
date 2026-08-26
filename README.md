# radixly

## Support

- CPython 3.11+ only. radixly is a hand-written C extension and ships no
  pure-Python fallback.
- Subinterpreters are not supported: on Python 3.12+, importing radixly in a
  subinterpreter raises `ImportError`; on 3.11 the import cannot be refused
  and the behavior is undefined.
