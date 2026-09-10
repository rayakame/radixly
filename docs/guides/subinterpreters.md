# Subinterpreters and threads

radixly does not support subinterpreters. The extension keeps state at
module level, its exception type and the decoders' lookup tables, and that
state exists once per process. Loading a second copy into a subinterpreter
would have two interpreters sharing objects that belong to one.

On Python 3.12 and later the module says so itself: importing radixly inside
a subinterpreter raises

```
ImportError: module radixly._core does not support loading in subinterpreters
```

On Python 3.11 there is no way for an extension to refuse the import, and
the behavior is undefined. Do not do it.

Ordinary threads are fine. `encode` and `decode` hold the GIL for the
duration of a call, which for these functions is microseconds, so threads
share the work but do not run it in parallel. For real parallelism across
cores use processes; every process imports its own copy of the extension.
Free-threaded CPython builds are not supported for the same reason as
subinterpreters: the module-level state is not prepared for it.
