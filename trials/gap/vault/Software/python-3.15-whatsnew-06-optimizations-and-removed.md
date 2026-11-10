---
source: https://docs.python.org/3.15/whatsnew/3.15.html
fetched: 2026-11-10
published: 2026-10-09
title: What’s new in Python 3.15 — Optimizations and Removed
---

# What’s new in Python 3.15 (continued: Optimizations and Removed)

## Optimizations

- `mimalloc` is now used as the default allocator for raw memory allocations such as via `PyMem_RawMalloc()` for better performance on free-threaded builds. (Contributed by Kumar Aditya in gh-144914.)

### base64 & binascii

- CPython’s underlying base64 implementation now encodes 2x faster and decodes 3x faster thanks to simple CPU pipelining optimizations. (Contributed by Gregory P. Smith and Serhiy Storchaka in gh-143262.)
- Implementation for Ascii85, Base85, and Z85 encoding has been rewritten in C. Encoding and decoding is now two orders of magnitude faster and consumes two orders of magnitude less memory. (Contributed by James Seo and Serhiy Storchaka in gh-101178.)
- Implementation for Base32 has been rewritten in C. Encoding and decoding is now two orders of magnitude faster. (Contributed by James Seo in gh-146192.)

### csv

- `csv.Sniffer.sniff()` delimiter detection is now up to 1.6x faster. (Contributed by Maurycy Pawłowski-Wieroński in gh-137628.)

### Upgraded experimental JIT compiler

Results from the pyperformance benchmark suite report a 7-8% geometric mean performance improvement for the JIT over the standard CPython interpreter built with all optimizations enabled on x86-64 Linux. On AArch64 macOS, the JIT has an 11-12% speedup over the tail calling interpreter with all optimizations enabled. The speedups for JIT builds versus no JIT builds range from roughly 15% slowdown to over 100% speedup (ignoring the `unpack_sequence` microbenchmark) on x86-64 Linux and AArch64 macOS systems.

The major upgrades to the JIT are:

- LLVM 21 build-time dependency
- New tracing frontend
- Basic register allocation in the JIT
- More JIT optimizations
- GDB and GNU `backtrace()` unwinding support
- Better machine code generation

LLVM 21 build-time dependency

The JIT compiler now uses LLVM 21 for build-time stencil generation. As always, LLVM is only needed when building CPython with the JIT enabled; end users running Python do not need LLVM installed. Instructions for installing LLVM can be found in the JIT compiler documentation for all supported platforms. (Contributed by Savannah Ostrowski in gh-140973.)

A new tracing frontend

The JIT compiler now supports significantly more bytecode operations and control flow than in Python 3.14, enabling speedups on a wider variety of code. For example, simple Python object creation is now understood by the 3.15 JIT compiler. Overloaded operations and generators are also partially supported. This was made possible by an overhauled JIT tracing frontend that records actual execution paths through code, rather than estimating them as the previous implementation did. (Contributed by Ken Jin in gh-139109. Support for Windows added by Mark Shannon in gh-141703.)

Basic register allocation in the JIT

A basic form of register allocation has been added to the JIT compiler’s optimizer. This allows the JIT compiler to avoid certain stack operations altogether and instead operate on registers. This allows the JIT to produce more efficient traces by avoiding reads and writes to memory. (Contributed by Mark Shannon in gh-135379.)

More JIT optimizations

More constant-propagation is now performed. This means when the JIT compiler detects that certain user code results in constants, the code can be simplified by the JIT. (Contributed by Ken Jin and Savannah Ostrowski in gh-132732.)

Reference counts are avoided whenever it is safe to do so. This generally reduces the cost of most operations in Python. (Contributed by Ken Jin, Donghee Na, Zheao Li, Hai Zhu, Savannah Ostrowski, Reiden Ong, Noam Cohen, Tomas Roun, PuQing, Cajetan Rodrigues, and Sacul in gh-134584.)

By tracking unique references to objects, the JIT optimizer can now eliminate reference count updates and perform in-place operations on ints and floats. (Contributed by Reiden Ong, and Pieter Eendebak in gh-143414 and gh-146306.)

The JIT optimizer now supports significantly more operations than in 3.14. (Contributed by Kumar Aditya, Ken Jin, Jiahao Li, and Sacul in gh-131798.)

GDB and GNU `backtrace()` unwinding support

The JIT compiler now publishes unwind information for generated machine code to the GDB interface on supported Linux ELF platforms. When libgcc frame registration is available, the same unwind information is also registered for GNU `backtrace()` stack walkers. This allows native debuggers, crash handlers, and diagnostic tools using these mechanisms to unwind through JIT frames instead of stopping at generated code. (Contributed by Diego Russo and Pablo Galindo Salgado in gh-146071 and gh-149104.)

Better machine code generation

The JIT compiler’s machine code generator now produces better machine code for x86-64 and AArch64 macOS and Linux targets. In general, users should experience lower memory usage for generated machine code and more efficient machine code versus 3.14. (Contributed by Brandt Bucher in gh-136528 and gh-135905. Implementation for AArch64 contributed by Mark Shannon in gh-139855. Additional optimizations for AArch64 contributed by Mark Shannon and Diego Russo in gh-140683 and gh-142305.)

Maintainability

The JIT optimizer’s operations have been simplified. This was made possible by a refactoring of JIT data structures. (Contributed by Zhongtian Zheng in gh-148211 and Hai Zhu in gh-143421.)

## Removed

### ast

- The constructors of AST nodes now raise a `TypeError` when a required argument is omitted or when a keyword argument that does not map to a field on the AST node is passed. These cases had previously raised a `DeprecationWarning` since Python 3.13. (Contributed by Brian Schubert and Jelle Zijlstra in gh-137600 and gh-105858.)

### collections.abc

- `collections.abc.ByteString` has been removed from `collections.abc.__all__`. `collections.abc.ByteString` has been deprecated since Python 3.12, and is scheduled for removal in Python 3.17. (Contributed by Alex Waygood in gh-118803.)

### ctypes

- Removed the undocumented function `ctypes.SetPointerType()`, which has been deprecated since Python 3.13. (Contributed by Bénédikt Tran in gh-133866.)

### datetime

- `strptime()` now raises `ValueError` when the format string contains `%d` (day of month) without a year directive. This has been deprecated since Python 3.13. (Contributed by Stan Ulbrych and Gregory P. Smith in gh-70647.)

### glob

- Removed the undocumented `glob.glob0()` and `glob.glob1()` functions, which have been deprecated since Python 3.13. Use `glob.glob()` and pass a directory to its root_dir argument instead. (Contributed by Barney Gale in gh-137466.)

### http.server

- Removed the `CGIHTTPRequestHandler` class and the `--cgi` flag from the python -m http.server command-line interface. They were deprecated in Python 3.13. (Contributed by Bénédikt Tran in gh-133810.)

### importlib

- The `load_module()` methods of `Loader` and its subclasses is removed. The import system will no longer call it when defined on custom subclasses. The method has been deprecated in favor of `exec_module()` since Python 3.4. (Contributed by Brett Cannon in gh-97850.)

### importlib.resources

- Removed deprecated `package` parameter from `importlib.resources.files()` function. (Contributed by Semyon Moroz in gh-138044.)

### pathlib

- Removed deprecated `pathlib.PurePath.is_reserved()`. Use `os.path.isreserved()` to detect reserved paths on Windows. (Contributed by Nikita Sobolev in gh-133875.)

### platform

- Removed the `platform.java_ver()` function, which was deprecated since Python 3.13. (Contributed by Alexey Makridenko in gh-133604.)

### sre_*

- Removed `sre_compile`, `sre_constants` and `sre_parse` modules. (Contributed by Stan Ulbrych in gh-135994.)

### sysconfig

- Removed the check_home parameter of `sysconfig.is_python_build()`. (Contributed by Filipe Laíns in gh-92897.)

### threading

- Remove support for arbitrary positional or keyword arguments in the C implementation of `RLock` objects. This was deprecated in Python 3.14. (Contributed by Bénédikt Tran in gh-134087.)

### types

- Removed `codeobject.co_lnotab` from `types.CodeType`, deprecated since Python 3.12 by PEP 626. (Contributed by Nikita Sobolev in gh-134690.)

### typing

- `typing.ByteString` has been removed from `typing.__all__`. `typing.ByteString` has been deprecated since Python 3.9, and is scheduled for removal in Python 3.17. (Contributed by Alex Waygood in gh-118803.)
- The undocumented keyword argument syntax for creating `NamedTuple` classes (for example, `Point = NamedTuple("Point", x=int, y=int)`) is no longer supported. Use the class-based syntax or the functional syntax instead. (Contributed by Bénédikt Tran in gh-133817.)
- Using `TD = TypedDict("TD")` or `TD = TypedDict("TD", None)` to construct a `TypedDict` type with zero fields is no longer supported. Use `class TD(TypedDict): pass` or `TD = TypedDict("TD", {})` instead. (Contributed by Bénédikt Tran in gh-133823.)
- Deprecated `typing.no_type_check_decorator` has been removed. (Contributed by Nikita Sobolev in gh-133601.)

### wave

- Removed the `getmark()`, `setmark()` and `getmarkers()` methods of the `Wave_read` and `Wave_write` classes, which were deprecated since Python 3.13. (Contributed by Bénédikt Tran in gh-133873.)

### zipimport

- Remove deprecated `zipimport.zipimporter.load_module()`. Use `zipimport.zipimporter.exec_module()` instead. (Contributed by Jiahao Li in gh-133656.)
