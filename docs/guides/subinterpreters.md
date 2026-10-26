# Subinterpreters and threads

::::{grid} 1 3 3 3
:gutter: 2

:::{grid-item-card} Threads
Supported. Calls hold the GIL while they run, so threads share the work but do
not run it in parallel.
:::

:::{grid-item-card} Subinterpreters
Not supported. Importing radixly inside one raises `ImportError`.
:::

:::{grid-item-card} Free-threaded builds
Import, but switch the GIL back on for the whole interpreter.
:::

::::

## Subinterpreters

The extension keeps state at module level, its exception type and the decoders'
lookup tables, and that state exists once per process. A second copy in a
subinterpreter would share objects that belong to one, so the import refuses:

```text
ImportError: module radixly._core does not support loading in subinterpreters
```

Python 3.12 and later refuse through the module's own declaration; 3.11 has no
such declaration, so radixly checks the interpreter itself and raises the same
error. For parallelism across cores use processes: each imports its own copy.

## Free-threaded builds

On `3.13t`, `3.14t` and `3.15t` the import succeeds, but the module does not
declare itself safe without the GIL, so CPython turns the GIL back on for that
interpreter and prints a `RuntimeWarning` saying so. radixly works; the rest of
the program loses its free threading. Running with `PYTHON_GIL=0` removes even
that protection and is not supported.
