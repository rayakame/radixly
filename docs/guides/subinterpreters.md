# Subinterpreters

radixly does not support subinterpreters. The extension keeps static state
(the `DecodeError` type object, the reverse lookup tables), so one copy per
process is the design.

- On Python 3.12 and later, importing radixly inside a subinterpreter raises
  `ImportError` — the module declares `Py_mod_multiple_interpreters` as not
  supported.
- On Python 3.11 there is no mechanism to refuse the import, and the behavior
  is undefined.

If per-interpreter state is ever needed, the shape is per-module state
(`m_size > 0`) reached through each function's module argument.
