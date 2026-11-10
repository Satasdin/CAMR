---
source: https://docs.python.org/3.15/whatsnew/3.15.html
fetched: 2026-11-10
published: 2026-10-09
title: What’s new in Python 3.15 — New features continued: PEP 831, 798, 829, 803, 788 and improved error messages
---

# What’s new in Python 3.15 (continued: New features continued: PEP 831, 798, 829, 803, 788 and improved error messages)

### PEP 831: Frame pointers enabled by default

CPython is now built with frame pointers by default on platforms that support them. This uses the compiler flags `-fno-omit-frame-pointer` and `-mno-omit-leaf-frame-pointer`, making native stack unwinding faster and more reliable for system profilers, debuggers, crash analysis tools, and eBPF-based observability tools.

The flags are exposed through `sysconfig`, so extension modules built by tools that consume Python’s build configuration inherit frame pointers by default. This propagation is intentional: mixed Python/native profiling needs an unbroken frame-pointer chain through the interpreter, extension modules, embedding applications, and native libraries.

Important

Third-party build backends and native build systems should preserve these flags when they consume Python’s `sysconfig` values. Build systems that compile C, C++, Rust, or other native code without inheriting Python’s compiler flags should enable equivalent frame-pointer flags themselves. A single native component built without frame pointers can break stack unwinding for the whole Python process.

(Contributed by Pablo Galindo Salgado and Savannah Ostrowski in gh-149201; PEP 831 written by Pablo Galindo Salgado, Ken Jin, Savannah Ostrowski, and Diego Russo.)

See also

PEP 831 for further details.

### PEP 798: Unpacking in comprehensions

List, set, and dictionary comprehensions, as well as generator expressions, now support unpacking with `*` and `**`. This extends the unpacking syntax from PEP 448 to comprehensions, providing a new syntax for combining an arbitrary number of iterables or dictionaries into a single flat structure. This new syntax is a direct alternative to nested comprehensions, `itertools.chain()`, and `itertools.chain.from_iterable()`. For example:

```
>>> lists = [[1, 2], [3, 4], [5]]
>>> [*L for L in lists]  # equivalent to [x for L in lists for x in L]
[1, 2, 3, 4, 5]

>>> sets = [{1, 2}, {2, 3}, {3, 4}]
>>> {*s for s in sets}  # equivalent to {x for s in sets for x in s}
{1, 2, 3, 4}

>>> dicts = [{'a': 1}, {'b': 2}, {'a': 3}]
>>> {**d for d in dicts}  # equivalent to {k: v for d in dicts for k,v in d.items()}
{'a': 3, 'b': 2}
```

Generator expressions can similarly use unpacking to yield values from multiple iterables:

```
>>> gen = (*L for L in lists)  # equivalent to (x for L in lists for x in L)
>>> list(gen)
[1, 2, 3, 4, 5]
```

This change also extends to asynchronous generator expressions, such that, for example, `(*a async for a in agen())` is equivalent to `(x async for a in agen() for x in a)`.

(Contributed by Adam Hartz in gh-143055.)

See also

PEP 798 for further details.

### PEP 829: Package startup configuration files

Loaded by the `site` module when `-S` is not given, .pth files can contain lines that both extend `sys.path` and execute arbitrary code when the line starts with `import` (followed by a space or tab). The latter functionality can be problematic, since it is difficult to know exactly what gets executed when Python starts up.

As a step towards improving the ability to audit pre-start executable code, Python 3.15 introduces .start files which contain entry point specifications of the form `pkg.mod:callable` where `pkg.mod` is the import path to the given callable. When Python starts up, the callable is located and called with no arguments.

`import` lines in `.pth` files are silently deprecated. When a matching `.start` file is found, `import` lines in `.pth` files are ignored. There is no change to `sys.path` extension lines in `.pth` files.

The `site` module also provides `site.StartupState` to batch startup processing for multiple site directories, ensuring all static path extensions are applied before any startup code is executed. `site.main()` uses an instance of this class implicitly to batch process all startup configuration files during normal interpreter startup. Callers needing the same batching behavior can build a `StartupState` directly and drive it with `addsitedir()`, `addusersitepackages()`, and `addsitepackages()`, then call `process()` once at the end of the batch.

(Contributed by Barry Warsaw in gh-148641 and gh-150228.)

### PEP 803: Stable ABI for free-threaded builds

C extensions that target the Stable ABI can now be compiled for the new Stable ABI for Free-Threaded Builds (also known as `abi3t`), which makes them compatible with free-threaded builds of CPython. This usually requires some non-trivial changes to the source code; specifically:

- Switching to API introduced in PEP 697 (Python 3.12), such as negative `basicsize` and `PyObject_GetTypeData()`, rather than making `PyObject` part of the instance struct; and
- Switching from a `PyInit_` function to a new export hook, `PyModExport_*`, introduced for this purpose in PEP 793, with a new `PySlot` structure introduced in PEP 820.

Note that Stable ABI does not offer all the functionality that CPython has to offer. Extensions that cannot switch to `abi3t` should continue to build for the existing Stable ABI (`abi3`) and the version-specific ABI for free-threading (`cp315t`) separately.

Stable ABI for Free-Threaded Builds should typically be selected in a build tool. Tools with `abi3t` support include meson-python, scikit-build-core, and Maturin; see Setting up the build for links to their documentation on `abi3t` builds. If your build tool does not support `abi3t`, compile for `cp315t` separately. If not using a build tool – or when writing such a tool – you can select `abi3t` by setting the macro `Py_TARGET_ABI3T` as discussed in Compiling for Stable ABI.

A practical migration guide for switching to `abi3t` is available. The community-maintained Python Free-Threading Guide provides examples of building and testing `abi3t` wheels.

See also

PEP 803 for further details.

### PEP 788: Protecting the C API from interpreter finalization

In the C API, interpreter finalization can be problematic for many extensions, because attaching a thread state will permanently hang the thread, resulting in deadlocks and other spurious issues. Additionally, it has historically been impossible to safely check whether an interpreter is alive before using it, leading to crashes when a thread concurrently deletes an interpreter while another thread is trying to attach to it.

There are now several new suites of APIs to circumvent these problems:

- Interpreter guards, which prevent an interpreter from finalizing.
- Interpreter views, which allow thread-safe access to an interpreter that may be concurrently finalizing or deleted.
- New APIs to automatically attach and detach thread states that come with built-in protection against finalization.

In addition, APIs in the `PyGILState` family (most notably `PyGILState_Ensure()` and `PyGILState_Release()`) have been soft deprecated. There is no plan to remove them, and existing code will continue to work, but there will be no new `PyGILState` APIs in future versions of Python.

(Contributed by Peter Bierma in gh-149101.)

See also

PEP 788 for further details.

### Improved error messages

- The interpreter now provides more helpful suggestions in `AttributeError` exceptions when accessing an attribute on an object that does not exist, but a similar attribute is available through one of its members.
  For example, if the object has an attribute that itself exposes the requested name, the error message will suggest accessing it via that inner attribute:
  ```
  from dataclasses import dataclass
  from math import pi
  
  @dataclass
  class Circle:
     radius: float
  
     @property
     def area(self) -> float:
        return pi * self.radius**2
  
  class Container:
     def __init__(self, inner: Circle) -> None:
        self.inner = inner
  
  circle = Circle(radius=4.0)
  container = Container(circle)
  print(container.area)
  ```
  Running this code now produces a clearer suggestion:
  ```
  Traceback (most recent call last):
    File "example.py", line 18, in <module>
      print(container.area)
            ^^^^^^^^^^^^^^
  AttributeError: 'Container' object has no attribute 'area'. Did you mean '.inner.area' instead of '.area'?
  ```
- When an `AttributeError` on a builtin type has no close match via Levenshtein distance, the error message now checks a static table of common method names from other languages (JavaScript, Java, Ruby, C#) and suggests the Python equivalent:
  ```
  >>> [1, 2, 3].push(4)
  Traceback (most recent call last):
  ...
  AttributeError: 'list' object has no attribute 'push'. Did you mean '.append'?
  
  >>> 'hello'.toUpperCase()
  Traceback (most recent call last):
  ...
  AttributeError: 'str' object has no attribute 'toUpperCase'. Did you mean '.upper'?
  ```
  When the Python equivalent is a language construct rather than a method, the hint describes the construct directly:
  ```
  >>> {}.put("a", 1)
  Traceback (most recent call last):
  ...
  AttributeError: 'dict' object has no attribute 'put'. Use d[k] = v.
  ```
  When a mutable method is called on an immutable type, the hint suggests the mutable counterpart:
  ```
  >>> (1, 2, 3).append(4)
  Traceback (most recent call last):
  ...
  AttributeError: 'tuple' object has no attribute 'append'. Did you mean to use a 'list' object?
  ```
  These hints also work for subclasses of builtin types.
  (Contributed by Matt Van Horn in gh-146406.)
- The interpreter now tries to provide a suggestion when `delattr()` fails due to a missing attribute. When an attribute name that closely resembles an existing attribute is used, the interpreter will suggest the correct attribute name in the error message. For example:
  ```
  >>> class A:
  ...     pass
  >>> a = A()
  >>> a.abcde = 1
  >>> del a.abcdf
  Traceback (most recent call last):
  ...
  AttributeError: 'A' object has no attribute 'abcdf'. Did you mean: 'abcde'?
  ```
  (Contributed by Nikita Sobolev and Pranjal Prajapati in gh-136588.)
- Several error messages incorrectly using the term “argument” have been corrected. (Contributed by Stan Ulbrych in gh-133382.)
