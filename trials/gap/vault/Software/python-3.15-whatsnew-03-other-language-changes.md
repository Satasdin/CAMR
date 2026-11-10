---
source: https://docs.python.org/3.15/whatsnew/3.15.html
fetched: 2026-11-10
published: 2026-10-09
title: What’s new in Python 3.15 — Other language changes, default interactive shell, new modules
---

# What’s new in Python 3.15 (continued: Other language changes, default interactive shell, new modules)

## Other language changes

- Python now uses UTF-8 as the default encoding, independent of the system’s environment. This means that I/O operations without an explicit encoding, for example, `open('flying-circus.txt')`, will use UTF-8. UTF-8 is a widely-supported Unicode character encoding that has become a de facto standard for representing text, including nearly every webpage on the internet, many common file formats, programming languages, and more.
  This only applies when no `encoding` argument is given. For best compatibility between versions of Python, ensure that an explicit `encoding` argument is always provided. The opt-in encoding warning can be used to identify code that may be affected by this change. The special `encoding='locale'` argument uses the current locale encoding, and has been supported since Python 3.10.
  To retain the previous behaviour, Python’s UTF-8 mode may be disabled with the `PYTHONUTF8=0` environment variable or the `-X utf8=0` command-line option.
  (Contributed by Adam Turner in gh-133711; PEP 686 written by Inada Naoki.)
  See also
  PEP 686 for further details.
- The interpreter help (such as `python --help`) is now in color. This can be controlled by environment variables. (Contributed by Hugo van Kemenade in gh-148766.)
- Unraisable exceptions are now highlighted with color by default. This can be controlled by environment variables. (Contributed by Peter Bierma in gh-134170.)
- More color in argparse, ast, calendar, difflib, http.server, pickletools, PyREPL tab completion, python –help, sqlite3, timeit, tokenize, unraisable exceptions and stdlib (ast, compileall, doctest, gzip, inspect, json.tool, pdb, profiling.sampling, random, regrtest, sqlite3, timeit, tokenize, trace, unittest, uuid, zipapp, zipfile) CLI help.
- The `__repr__()` of `ImportError` and `ModuleNotFoundError` now shows “name” and “path” as `name=<name>` and `path=<path>` if they were given as keyword arguments at construction time. (Contributed by Serhiy Storchaka, Oleg Iarygin, and Yoav Nir in gh-74185.)
- The `__dict__` and `__weakref__` descriptors now use a single descriptor instance per interpreter, shared across all types that need them. This speeds up class creation, and helps avoid reference cycles. (Contributed by Petr Viktorin in gh-135228.)
- The `-W` option and the `PYTHONWARNINGS` environment variable can now specify regular expressions instead of literal strings to match the warning message and the module name, if the corresponding field starts and ends with a forward slash (`/`). (Contributed by Serhiy Storchaka in gh-134716.)
- Functions that take timestamp or timeout arguments now accept any real numbers (such as `Decimal` and `Fraction`), not only integers or floats, although this does not improve precision. (Contributed by Serhiy Storchaka in gh-67795.)

- Added `bytearray.take_bytes(n=None, /)` to take bytes out of a `bytearray` without copying. This enables optimizing code which must return `bytes` after working with a mutable buffer of bytes such as data buffering, network protocol parsing, encoding, decoding, and compression. Common code patterns which can be optimized with `take_bytes()` are listed below.
  | Description | Old | New |
  | --- | --- | --- |
  | Return `bytes` after working with `bytearray` | def read() -> bytes: buffer = bytearray(1024) ... return bytes(buffer) | def read() -> bytes: buffer = bytearray(1024) ... return buffer.take_bytes() |
  | Empty a buffer getting the bytes | buffer = bytearray(1024) ... data = bytes(buffer) buffer.clear() | buffer = bytearray(1024) ... data = buffer.take_bytes() |
  | Split a buffer at a specific separator | buffer = bytearray(b'abc\ndef') n = buffer.find(b'\n') data = bytes(buffer[:n + 1]) del buffer[:n + 1] assert data == b'abc\n' assert buffer == bytearray(b'def') | buffer = bytearray(b'abc\ndef') n = buffer.find(b'\n') data = buffer.take_bytes(n + 1) |
  | Split a buffer at a specific separator; discard after the separator | buffer = bytearray(b'abc\ndef') n = buffer.find(b'\n') data = bytes(buffer[:n]) buffer.clear() assert data == b'abc' assert len(buffer) == 0 | buffer = bytearray(b'abc\ndef') n = buffer.find(b'\n') buffer.resize(n) data = buffer.take_bytes() |
  (Contributed by Cody Maloney in gh-139871.)
- Many functions related to compiling or parsing Python code, such as `compile()`, `ast.parse()`, `symtable.symtable()`, and `importlib.abc.InspectLoader.source_to_code()`, now allow the module name to be passed. It is needed to unambiguously filter syntax warnings by module name. (Contributed by Serhiy Storchaka in gh-135801.)
- Allowed defining the __dict__ and __weakref__ __slots__ for any class. (Contributed by Serhiy Storchaka in gh-41779.)
- Allowed defining any __slots__ for a class derived from `tuple` (including classes created by `collections.namedtuple()`). (Contributed by Serhiy Storchaka in gh-41779.)
- The `slice` type now supports subscription, making it a generic type. (Contributed by James Hilton-Balfe in gh-128335.)
- The class `memoryview` now supports the float complex and double complex C types: formatting characters `'Zf'` and `'Zd'` respectively. (Contributed by Victor Stinner in gh-146151 and gh-148675.)
- Allow the count argument of `bytes.replace()` to be a keyword. (Contributed by Stan Ulbrych in gh-147856.)
- Unary plus is now accepted in `match` literal patterns, mirroring the existing support for unary minus. (Contributed by Bartosz Sławecki in gh-145239.)
- The import system now acquires per-module locks in hierarchical order (parent packages before their submodules). This fixes a long-standing deadlock where one thread importing `pkg.sub` and another importing `pkg.sub.mod` could each block the other when `pkg/sub/__init__.py` imports `pkg.sub.mod`. (Contributed by Gregory P. Smith in gh-83065.)
- File names of Stable ABI extensions that use the `.so` suffix may now include a multiarch tuple, for example, `foo.abi3-x86-64-linux-gnu.so`. This permits stable ABI extensions for multiple architectures to be co-installed into the same directory, without clashing with each other, as regular dynamic extensions do. (Contributed by Stefano Rivera in gh-122931.)
- The `__cached__` attribute on modules, which was deprecated since version 3.13, is no longer set or taken into consideration by the import system or standard library. Use `__spec__.cached` instead. (Contributed by Brett Cannon in gh-97879.)
  Note that the `__loader__` and `__package__` attributes are also deprecated and scheduled for removal.

## Default interactive shell

- Tab completions are now colored by object kind, based on fancycompleter. Set `PYTHON_BASIC_COMPLETER` to fall back to `rlcompleter`. Color can also be controlled by environment variables. (Contributed by Antonio Cuni and Pablo Galindo in gh-130472.)
- Tab completion now suggests module attributes in `from ... import` statements. Attributes can only be suggested once the module is imported, so stdlib modules are imported automatically, while for other modules the completer offers to import them when `Tab` is pressed a second time. (Contributed by Loïc Simon and Pablo Galindo in gh-140870.)

## New modules

### math.integer

This module provides access to the mathematical functions for integer arguments (PEP 791). (Contributed by Serhiy Storchaka in gh-81313.)
