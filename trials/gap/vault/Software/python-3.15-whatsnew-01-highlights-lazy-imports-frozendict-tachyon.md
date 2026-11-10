---
source: https://docs.python.org/3.15/whatsnew/3.15.html
fetched: 2026-11-10
published: 2026-10-09
title: What’s new in Python 3.15 — Summary, PEP 810 lazy imports, frozendict, sentinel, profiling and Tachyon
---

# What’s new in Python 3.15

**Editor:**

Hugo van Kemenade

This article explains the new features in Python 3.15, compared to 3.14. Python 3.15 was released on 9 October 2026. For full details, see the changelog.

See also

PEP 790 – Python 3.15 release schedule

## Summary – Release highlights

Python 3.15 is the latest stable release of the Python programming language, with a mix of changes to the language, the implementation, and the standard library. The biggest changes include lazy imports, frozendict and sentinel builtins, UTF-8 as the default encoding, unpacking in comprehensions, and a stable ABI for free-threaded builds.

The library changes include a new profiling package with Tachyon, a high-frequency statistical sampling profiler, more color in command-line output, as well as the usual deprecations and removals, and improvements in user-friendliness and correctness.

This article doesn’t attempt to provide a complete specification of all new features, but instead gives a convenient overview. For full details refer to the documentation, such as the Library Reference and Language Reference. To understand the complete implementation and design rationale for a change, refer to the PEP for a particular new feature; but note that PEPs usually are not kept up-to-date once a feature has been fully implemented.

See Porting to Python 3.15 for guidance on upgrading from earlier versions of Python.

Interpreter improvements:

- PEP 661: Add sentinel built-in type
- PEP 686: Python now uses UTF-8 as the default encoding
- PEP 798: Unpacking in comprehensions
- PEP 810: Explicit lazy imports for faster startup times
- PEP 814: Add frozendict built-in type
- PEP 829: Package startup configuration files
- The experimental JIT compiler has been significantly upgraded
- Improved error messages

Significant improvements in the standard library:

- PEP 799: A dedicated profiling package for organizing Python profiling tools
- PEP 799: Tachyon: High-frequency statistical sampling profiler
- More color

New typing features:

- PEP 728: TypedDict with typed extra items
- PEP 747: Annotating type forms with TypeForm
- PEP 800: Disjoint bases in the type system

C API improvements:

- PEP 782: A new PyBytesWriter C API to create a Python bytes object
- PEP 788: Protection against finalization in the C API
- PEP 803, 820, 793: Stable ABI for free-threaded builds and related C API

Build changes:

- PEP 831: Frame pointers are enabled by default for improved system-level observability

Release changes:

- The official Windows 64-bit binaries now use the tail-calling interpreter
- The official macOS binaries now install free-threading support by default

## New features

### PEP 810: Explicit lazy imports

Large Python applications often suffer from slow startup times. A significant contributor to this problem is the import system: when a module is imported, Python must locate the file, read it from disk, compile it to bytecode, and execute all top-level code. For applications with deep dependency trees, this process can take seconds, even when most of the imported code is never actually used during a particular run.

Developers have worked around this by moving imports inside functions, using `importlib` to load modules on demand, or restructuring code to avoid unnecessary dependencies. These approaches work but make code harder to read and maintain, scatter import statements throughout the codebase, and require discipline to apply consistently.

Python now provides a cleaner solution through explicit `lazy` imports using the new `lazy` soft keyword. When you mark an import as lazy, Python defers the actual module loading until the imported name is first used. This gives you the organizational benefits of declaring all imports at the top of the file while only paying the loading cost for modules you actually use.

The `lazy` keyword works with both `import` and `from ... import` statements. When you write `lazy import heavy_module`, Python does not immediately load the module. Instead, it creates a lightweight proxy object. The actual module loading happens transparently when you first access the name:

```
lazy import json
lazy from pathlib import Path

print("Starting up...")  # json and pathlib are not fully imported yet

data = json.loads('{"key": "value"}')  # json gets fully imported here
p = Path(".")  # pathlib gets fully imported here
```

This mechanism is particularly useful for applications that import many modules at the top level but may only use a subset of them in any given run. The deferred loading reduces startup latency without requiring code restructuring or conditional imports scattered throughout the codebase.

In the case where loading a lazily imported module fails (for example, if the module does not exist), Python raises the exception at the point of first use rather than at import time. The associated traceback includes both the location where the name was accessed and the original import statement, making it straightforward to diagnose and debug the failure.

For cases where you want to enable lazy loading globally without modifying source code, Python provides the `-X lazy_imports` command-line option and the `PYTHON_LAZY_IMPORTS` environment variable. Both accept two values: `all` makes all imports lazy by default, and `normal` (the default) respects the `lazy` keyword in source code. The `sys.set_lazy_imports()` and `sys.get_lazy_imports()` functions allow changing and querying this mode at runtime.

For more selective control, `sys.set_lazy_imports_filter()` accepts a callable that determines whether a specific module should be loaded lazily. The filter receives three arguments: the importing module’s name (or `None`), the imported module’s name, and the fromlist (or `None` for regular imports). It should return `True` to allow the import to be lazy, or `False` to force eager loading. This allows patterns like making only your own application’s modules lazy while keeping third-party dependencies eager:

```
import sys

def myapp_filter(importing, imported, fromlist):
    return imported.startswith("myapp.")
sys.set_lazy_imports_filter(myapp_filter)
sys.set_lazy_imports("all")

import myapp.slow_module  # lazy (matches filter)
import json               # eager (does not match filter)
```

The proxy type itself is available as `types.LazyImportType` for code that needs to detect lazy imports programmatically.

There are some restrictions on where the `lazy` keyword can be used. Lazy imports are only permitted at module scope; using `lazy` inside a function, class body, or `try`/`except`/`finally` block raises a `SyntaxError`. Neither star imports nor future imports can be lazy (`lazy from module import *` and `lazy from __future__ import ...` both raise `SyntaxError`).

For code that cannot use the `lazy` keyword directly (for example, when supporting Python versions older than 3.15 while still using lazy imports on 3.15+), a module can define `__lazy_modules__` as a container of fully qualified module name strings. Regular `import` statements for those modules are then treated as lazy, with the same semantics as the `lazy` keyword:

```
__lazy_modules__ = ["json", "pathlib"]

import json     # lazy
import os       # still eager
```

(Contributed by Pablo Galindo Salgado and Dino Viehland in gh-142349.)

See also

PEP 810 for the full specification and rationale.

### PEP 814: Add frozendict built-in type

A new immutable type, `frozendict`, is added to the `builtins` module. It does not allow modification after creation. A `frozendict` is not a subclass of `dict`; it inherits directly from `object`. A `frozendict` is hashable as long as all of its keys and values are hashable. A `frozendict` preserves insertion order, but comparison does not take order into account.

For example:

```
>>> a = frozendict(x=1, y=2)
>>> a
frozendict({'x': 1, 'y': 2})
>>> a['z'] = 3
Traceback (most recent call last):
  File "<python-input-2>", line 1, in <module>
    a['z'] = 3
    ~^^^^^
TypeError: 'frozendict' object does not support item assignment
>>> b = frozendict(y=2, x=1)
>>> hash(a) == hash(b)
True
>>> a == b
True
```

The following standard library modules have been updated to accept `frozendict`: `copy`, `decimal`, `json`, `marshal`, `plistlib` (only for serialization), `pickle`, `pprint` and `xml.etree.ElementTree`.

`eval()` and `exec()` accept `frozendict` for globals, and `type()` and `str.maketrans()` accept `frozendict` for dict.

Code checking for `dict` type using `isinstance(arg, dict)` can be updated to `isinstance(arg, (dict, frozendict))` to accept also the `frozendict` type, or to `isinstance(arg, collections.abc.Mapping)` to accept also other mapping types such as `MappingProxyType`.

(Contributed by Victor Stinner and Donghee Na in gh-141510.)

See also

PEP 814 for the full specification and rationale.

### PEP 661: Add sentinel built-in type

A new `sentinel` type is added to the `builtins` module for creating unique sentinel values with a concise representation. Sentinel objects preserve identity when copied, support use in type expressions with the `|` operator, and can be pickled when they are importable by module and name.

(Contributed by Jelle Zijlstra in gh-148829; PEP 661 written by Tal Einat.)

See also

PEP 661 for further details.

### PEP 799: A dedicated profiling package

A new `profiling` module has been added to organize Python’s built-in profiling tools under a single, coherent namespace. This module contains:

- `profiling.tracing`: deterministic function-call tracing (relocated from `cProfile`).
- `profiling.sampling`: a new statistical sampling profiler (named Tachyon).

The `cProfile` module remains as an alias for backwards compatibility. The `profile` module is deprecated and will be removed in Python 3.17.

(Contributed by Pablo Galindo and László Kiss Kollár in gh-138122.)

See also

PEP 799 for further details.

### Tachyon: High-frequency statistical sampling profiler

A new statistical sampling profiler (Tachyon) has been added as `profiling.sampling`. This profiler enables low-overhead performance analysis of running Python processes without requiring code modification or process restart.

Tachyon follows earlier work on external sampling profilers such as Austin, py-spy, Pyflame, and rbspy. We thank their authors and the wider profiling community for their work and ideas.

Unlike deterministic profilers (such as `profiling.tracing`) that instrument every function call, the sampling profiler periodically captures stack traces from running processes. This approach provides virtually zero overhead while achieving sampling rates of up to 1,000,000 Hz, making it the fastest sampling profiler available for Python (at the time of its contribution) and ideal for debugging performance issues in production environments. This capability is particularly valuable for debugging performance issues in production systems where traditional profiling approaches would be too intrusive.

Key features include:

- Zero-overhead profiling: Attach to any running Python process without affecting its performance. Ideal for production debugging where you can’t afford to restart or slow down your application.
- No code modification required: Profile existing applications without restart. Simply point the profiler at a running process by PID and start collecting data.
- Flexible target modes:
  - Profile running processes by PID (`attach`) - attach to already-running applications
  - Run and profile scripts directly (`run`) - profile from the very start of execution
  - Execute and profile modules (`run -m`) - profile packages run as `python -m module`
  - Capture a one-shot snapshot of a running process (`dump`) - print a traceback-style stack of every thread (or all asyncio tasks with `--async-aware`). Useful for investigating hung processes.
- Multiple profiling modes: Choose what to measure based on your performance investigation:
  - Wall-clock time (`--mode wall`, default): Measures real elapsed time including I/O, network waits, and blocking operations. Use this to understand where your program spends calendar time, including when waiting for external resources.
  - CPU time (`--mode cpu`): Measures only active CPU execution time, excluding I/O waits and blocking. Use this to identify CPU-bound bottlenecks and optimize computational work.
  - GIL-holding time (`--mode gil`): Measures time spent holding Python’s Global Interpreter Lock. Use this to identify which threads dominate GIL usage in multi-threaded applications.
  - Exception handling time (`--mode exception`): Captures samples only from threads with an active exception. Use this to analyze exception handling overhead.
- Thread-aware profiling: Option to profile all threads (`-a`) or just the main thread, essential for understanding multi-threaded application behavior.
- Multiple output formats: Choose the visualization that best fits your workflow:
  - `--pstats`: Detailed tabular statistics compatible with `pstats`. Shows function-level timing with direct and cumulative samples. Best for detailed analysis and integration with existing Python profiling tools.
  - `--collapsed`: Generates collapsed stack traces (one line per stack). This format is specifically designed for creating flame graphs with external tools like Brendan Gregg’s FlameGraph scripts or speedscope.
  - `--flamegraph`: Generates a self-contained interactive HTML flame graph using D3.js. Opens directly in your browser for immediate visual analysis. Flame graphs show the call hierarchy where width represents time spent, making it easy to spot bottlenecks at a glance.
  - `--gecko`: Generates Gecko Profiler format compatible with Firefox Profiler. Upload the output to Firefox Profiler for advanced timeline-based analysis with features like stack charts, markers, and network activity.
  - `--heatmap`: Generates an interactive HTML heatmap visualization with line-level sample counts. Creates a directory with per-file heatmaps showing exactly where time is spent at the source code level.
- Live interactive mode: Real-time TUI profiler with a top-like interface (`--live`). Monitor performance as your application runs with interactive sorting and filtering.
- Async-aware profiling: Profile async/await code with task-based stack reconstruction (`--async-aware`). See which coroutines are consuming time, with options to show only running tasks or all tasks including those waiting.
- Opcode-level profiling: Gather bytecode opcode information for instruction-level profiling (`--opcodes`). Shows which bytecode instructions are executing, including specializations from the adaptive interpreter.

See `profiling.sampling` for the complete documentation, including all available output formats, profiling modes, and configuration options.

(Contributed by Pablo Galindo and László Kiss Kollár in gh-135953 and gh-138122.)
