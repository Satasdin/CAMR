---
source: https://docs.python.org/3.15/whatsnew/3.15.html
fetched: 2026-11-10
published: 2026-10-09
title: What’s new in Python 3.15 — Deprecated and pending removals
---

# What’s new in Python 3.15 (continued: Deprecated and pending removals)

## Deprecated

### New deprecations

- `ast`:
  - Creating instances of abstract AST nodes (such as `ast.AST` or `ast.expr`) is deprecated and will raise an error in Python 3.20.
    (Contributed by Brian Schubert in gh-116021.)
- `base64`:
  - Accepting the `+` and `/` characters with an alternative alphabet in `b64decode()` and `urlsafe_b64decode()` is now deprecated. In future Python versions they will be errors in the strict mode and discarded in the non-strict mode. (Contributed by Serhiy Storchaka in gh-125346.)
- CLI:
  - Deprecate `-b` and `-bb` command-line options and schedule them to become no-ops in Python 3.17. These were primarily helpers for the Python 2 -> 3 transition. Starting with Python 3.17, no `BytesWarning` will be raised for these cases; use a type checker instead.
    (Contributed by Nikita Sobolev in gh-136355.)
- `collections.abc`:
  - The following statements now cause `DeprecationWarning`s to be emitted at runtime:
    - `from collections.abc import ByteString`
    - `import collections.abc; collections.abc.ByteString`.
    `DeprecationWarning`s were already emitted if `collections.abc.ByteString` was subclassed or used as the second argument to `isinstance()` or `issubclass()`, but warnings were not previously emitted if it was merely imported or accessed from the `collections.abc` module. (Contributed by Alex Waygood in gh-118803.)
- `hashlib`:
  - In hash function constructors such as `new()` or the direct hash-named constructors such as `md5()` and `sha256()`, the optional initial data parameter could also be passed as a keyword argument named `data=` or `string=` in various `hashlib` implementations.
    Support for the `string` keyword argument name is now deprecated and is slated for removal in Python 3.19. Prefer passing the initial data as a positional argument for maximum backwards compatibility.
    (Contributed by Bénédikt Tran in gh-134978.)
- `http.cookies`:
  - `Morsel.js_output` and `BaseCookie.js_output` are deprecated and will be removed in Python 3.19. Use `Morsel.output` or `BaseCookie.output` instead. (Contributed by kishorhange111 in gh-148849.)
- `imaplib`:
  - Altering `IMAP4.file` is now deprecated and slated for removal in Python 3.19. This property is now unused and changing its value does not explicitly close the current file. (Contributed by Bénédikt Tran in gh-142307.)
- `profile`:
  - The `profile` module is deprecated and will be removed in Python 3.17. Use `profiling.tracing` instead, which provides a compatible API. See PEP 799 for details. (Contributed by Pablo Galindo and László Kiss Kollár in gh-138122.)
- `re`:
  - `re.match()` and `re.Pattern.match()` are now soft deprecated in favor of the new `re.prefixmatch()` and `re.Pattern.prefixmatch()` APIs, which have been added as alternate, more explicit names. These are intended to be used to alleviate confusion around what match means by following the Zen of Python’s “Explicit is better than implicit” mantra. Most other language regular expression libraries use an API named match to mean what Python has always called search.
    We do not plan to remove the older `match()` name, as it has been used in code for over 30 years. Code supporting older versions of Python should continue to use `match()`, while new code should prefer `prefixmatch()`. See prefixmatch() vs. match().
    (Contributed by Gregory P. Smith in gh-86519 and Hugo van Kemenade in gh-148100.)
- `struct`:
  - Calling `Struct.__new__()` without a required argument is now deprecated and will be removed in Python 3.20. Calling the `__init__()` method on an initialized `Struct` object is deprecated and will be removed in Python 3.20.
    (Contributed by Sergey B Kirpichev and Serhiy Storchaka in gh-143715.)
  - The `'F'` and `'D'` type codes are now soft deprecated in favor of the two-letter forms `'Zf'` and `'Zd'`. (Contributed by Sergey B Kirpichev in gh-121249.)
- `typing`:
  - The following statements now cause `DeprecationWarning`s to be emitted at runtime:
    - `from typing import ByteString`
    - `import typing; typing.ByteString`.
    `DeprecationWarning`s were already emitted if `typing.ByteString` was subclassed or used as the second argument to `isinstance()` or `issubclass()`, but warnings were not previously emitted if it was merely imported or accessed from the `typing` module. (Contributed by Alex Waygood in gh-118803.)
  - It is deprecated to call `isinstance()` and `issubclass()` checks on protocol classes that were not explicitly decorated with `runtime_checkable()` but that inherit from a runtime-checkable protocol class. This will raise a `TypeError` in Python 3.20.
    (Contributed by Bartosz Sławecki in gh-132604.)
- `webbrowser`:
  - `webbrowser.MacOSXOSAScript` is deprecated in favour of `webbrowser.MacOS` and scheduled for removal in Python 3.17. (Contributed by Jeff Lyon in gh-137586.)
- `__version__`:
  - The `__version__`, `version` and `VERSION` attributes have been deprecated in these standard library modules and will be removed in Python 3.20. Use `sys.version_info` instead.
    - `argparse`
    - `csv`
    - `ctypes`
    - `ctypes.macholib`
    - `decimal` (use `decimal.SPEC_VERSION` instead)
    - `http.server`
    - `imaplib`
    - `ipaddress`
    - `json`
    - `logging` (`__date__` also deprecated)
    - `optparse`
    - `pickle`
    - `platform`
    - `re`
    - `socketserver`
    - `tabnanny`
    - `tarfile`
    - `tkinter.font`
    - `tkinter.ttk`
    - `wsgiref.simple_server`
    - `xml.etree.ElementTree`
    - `xml.sax.expatreader`
    - `xml.sax.handler`
    - `zlib`
    (Contributed by Hugo van Kemenade and Stan Ulbrych in gh-76007.)

### Pending removal in Python 3.16

- The import system:
  - Setting `__loader__` on a module while failing to set `__spec__.loader` is deprecated. In Python 3.16, `__loader__` will cease to be set or taken into consideration by the import system or the standard library.
- `array`:
  - The `'u'` format code (`wchar_t`) has been deprecated in documentation since Python 3.3 and at runtime since Python 3.13. Use the `'w'` format code (`Py_UCS4`) for Unicode characters instead.
- `asyncio`:
  - `asyncio.iscoroutinefunction()` is deprecated and will be removed in Python 3.16; use `inspect.iscoroutinefunction()` instead. (Contributed by Jiahao Li and Kumar Aditya in gh-122875.)
  - `asyncio` policy system is deprecated and will be removed in Python 3.16. In particular, the following classes and functions are deprecated:
    - `asyncio.AbstractEventLoopPolicy`
    - `asyncio.DefaultEventLoopPolicy`
    - `asyncio.WindowsSelectorEventLoopPolicy`
    - `asyncio.WindowsProactorEventLoopPolicy`
    - `asyncio.get_event_loop_policy()`
    - `asyncio.set_event_loop_policy()`
    Users should use `asyncio.run()` or `asyncio.Runner` with loop_factory to use the desired event loop implementation.
    For example, to use `asyncio.SelectorEventLoop` on Windows:
    ```
    import asyncio
    
    async def main():
        ...
    
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
    ```
    (Contributed by Kumar Aditya in gh-127949.)
- `builtins`:
  - Bitwise inversion on boolean types, `~True` or `~False` has been deprecated since Python 3.12, as it produces surprising and unintuitive results (`-2` and `-1`). Use `not x` instead for the logical negation of a Boolean. In the rare case that you need the bitwise inversion of the underlying integer, convert to `int` explicitly (`~int(x)`).
- `functools`:
  - Calling the Python implementation of `functools.reduce()` with function or sequence as keyword arguments has been deprecated since Python 3.14.
- `logging`:
  - Support for custom logging handlers with the strm argument is deprecated and scheduled for removal in Python 3.16. Define handlers with the stream argument instead. (Contributed by Mariusz Felisiak in gh-115032.)
- `mimetypes`:
  - Valid extensions start with a ‘.’ or are empty for `mimetypes.MimeTypes.add_type()`. Undotted extensions are deprecated and will raise a `ValueError` in Python 3.16. (Contributed by Hugo van Kemenade in gh-75223.)
- `shutil`:
  - The `ExecError` exception has been deprecated since Python 3.14. It has not been used by any function in `shutil` since Python 3.4, and is now an alias of `RuntimeError`.
- `symtable`:
  - The `Class.get_methods` method has been deprecated since Python 3.14.
- `sys`:
  - The `_enablelegacywindowsfsencoding()` function has been deprecated since Python 3.13. Use the `PYTHONLEGACYWINDOWSFSENCODING` environment variable instead.
- `sysconfig`:
  - The `sysconfig.expand_makefile_vars()` function has been deprecated since Python 3.14. Use the `vars` argument of `sysconfig.get_paths()` instead.
- `tarfile`:
  - The undocumented and unused `TarFile.tarfile` attribute has been deprecated since Python 3.13.

### Pending removal in Python 3.17

- `datetime`:
  - `strptime()` calls using a format string containing `%e` (day of month) without a year. This has been deprecated since Python 3.15. (Contributed by Stan Ulbrych in gh-70647.)
- `collections.abc`:
  - `collections.abc.ByteString` is scheduled for removal in Python 3.17.
    Use `isinstance(obj, collections.abc.Buffer)` to test if `obj` implements the buffer protocol at runtime. For use in type annotations, either use `Buffer` or a union that explicitly specifies the types your code supports (e.g., `bytes | bytearray | memoryview`).
    `ByteString` was originally intended to be an abstract class that would serve as a supertype of both `bytes` and `bytearray`. However, since the ABC never had any methods, knowing that an object was an instance of `ByteString` never actually told you anything useful about the object. Other common buffer types such as `memoryview` were also never understood as subtypes of `ByteString` (either at runtime or by static type checkers).
    See PEP 688 for more details. (Contributed by Shantanu Jain in gh-91896.)
- `encodings`:
  - Passing non-ascii encoding names to `encodings.normalize_encoding()` is deprecated and scheduled for removal in Python 3.17. (Contributed by Stan Ulbrych in gh-136702.)
- `profile`:
  - The `profile` module is deprecated and will be removed in Python 3.17. Use `profiling.tracing` instead, which provides a compatible API. See PEP 799 for details. (Contributed by Pablo Galindo and László Kiss Kollár in gh-138122.)
- `webbrowser`:
  - `webbrowser.MacOSXOSAScript` is deprecated in favour of `webbrowser.MacOS`. (gh-137586)
- `typing`:
  - Before Python 3.14, old-style unions were implemented using the private class `typing._UnionGenericAlias`. This class is no longer needed for the implementation, but it has been retained for backward compatibility, with removal scheduled for Python 3.17. Users should use documented introspection helpers like `typing.get_origin()` and `typing.get_args()` instead of relying on private implementation details.
  - `typing.ByteString`, deprecated since Python 3.9, is scheduled for removal in Python 3.17.
    Use `isinstance(obj, collections.abc.Buffer)` to test if `obj` implements the buffer protocol at runtime. For use in type annotations, either use `Buffer` or a union that explicitly specifies the types your code supports (e.g., `bytes | bytearray | memoryview`).
    `ByteString` was originally intended to be an abstract class that would serve as a supertype of both `bytes` and `bytearray`. However, since the ABC never had any methods, knowing that an object was an instance of `ByteString` never actually told you anything useful about the object. Other common buffer types such as `memoryview` were also never understood as subtypes of `ByteString` (either at runtime or by static type checkers).
    See PEP 688 for more details. (Contributed by Shantanu Jain in gh-91896.)
- `tkinter`:
  - The `tkinter.Variable` methods `trace_variable()`, `trace()` (an alias of `trace_variable()`), `trace_vdelete()` and `trace_vinfo()`, deprecated since Python 3.14, are scheduled for removal in Python 3.17. Use `trace_add()`, `trace_remove()` and `trace_info()` instead. (Contributed by Serhiy Storchaka in gh-120220.)

### Pending removal in Python 3.18

- No longer accept a boolean value when a file descriptor is expected. (Contributed by Serhiy Storchaka in gh-82626.)
- `decimal`:
  - The non-standard and undocumented `Decimal` format specifier `'N'`, which is only supported in the `decimal` module’s C implementation, has been deprecated since Python 3.13. (Contributed by Serhiy Storchaka in gh-89902.)
- Deprecations defined by PEP 829:
  - `import` lines in `name.pth` files are silently ignored.
  (Contributed by Barry Warsaw in gh-148641.)

### Pending removal in Python 3.19

- `ctypes`:
  - Implicitly switching to the MSVC-compatible struct layout by setting `_pack_` but not `_layout_` on non-Windows platforms.
- `hashlib`:
  - In hash function constructors such as `new()` or the direct hash-named constructors such as `md5()` and `sha256()`, their optional initial data parameter could also be passed a keyword argument named `data=` or `string=` in various `hashlib` implementations.
    Support for the `string` keyword argument name is now deprecated and slated for removal in Python 3.19.
    Before Python 3.13, the `string` keyword parameter was not correctly supported depending on the backend implementation of hash functions. Prefer passing the initial data as a positional argument for maximum backwards compatibility.
- `http.cookies`:
  - `http.cookies.Morsel.js_output()` is deprecated and will be removed in Python 3.19.
  - `http.cookies.BaseCookie.js_output()` is deprecated and will be removed in Python 3.19.
- `imaplib`:
  - Altering `IMAP4.file` is now deprecated and slated for removal in Python 3.19. This property is now unused and changing its value does not automatically close the current file.
    Before Python 3.14, this property was used to implement the corresponding `read()` and `readline()` methods for `IMAP4` but this is no longer the case since then.

### Pending removal in Python 3.20

- Calling the `__new__()` method of `struct.Struct` without the format argument is deprecated and will be removed in Python 3.20. Calling `__init__()` method on initialized `Struct` objects is deprecated and will be removed in Python 3.20.
  (Contributed by Sergey B Kirpichev and Serhiy Storchaka in gh-143715.)
- The `__version__`, `version` and `VERSION` attributes have been deprecated in these standard library modules and will be removed in Python 3.20. Use `sys.version_info` instead.
  - `argparse`
  - `csv`
  - `ctypes`
  - `ctypes.macholib`
  - `decimal` (use `decimal.SPEC_VERSION` instead)
  - `http.server`
  - `imaplib`
  - `ipaddress`
  - `json`
  - `logging` (`__date__` also deprecated)
  - `optparse`
  - `pickle`
  - `platform`
  - `re`
  - `socketserver`
  - `tabnanny`
  - `tarfile`
  - `tkinter.font`
  - `tkinter.ttk`
  - `wsgiref.simple_server`
  - `xml.etree.ElementTree`
  - `xml.sax.expatreader`
  - `xml.sax.handler`
  - `zlib`
  (Contributed by Hugo van Kemenade and Stan Ulbrych in gh-76007.)
- Deprecations defined by PEP 829:
  - Warnings are produced for `import` lines found in `name.pth` files.
  - `name.pth` files are no longer decoded in the locale encoding by default. They MUST be encoded in `utf-8-sig`.
  (Contributed by Barry Warsaw in gh-148641.)
- `ast`:
  - Creating instances of abstract AST nodes (such as `ast.AST` or `ast.expr`) is deprecated and will raise an error in Python 3.20.
- `typing`:
  - It is deprecated to call `isinstance()` and `issubclass()` checks on protocol classes that were not explicitly decorated with `runtime_checkable()` but that inherit from a runtime-checkable protocol class. This will raise a `TypeError` in Python 3.20.
    (Contributed by Bartosz Sławecki in gh-132604.)

### Pending removal in future versions

The following APIs will be removed in the future, although there is currently no date scheduled for their removal.

- `argparse`:
  - Nesting argument groups and nesting mutually exclusive groups are deprecated.
  - Passing the undocumented keyword argument prefix_chars to `add_argument_group()` is now deprecated.
  - The `argparse.FileType` type converter is deprecated.
- `builtins`:
  - Generators: `throw(type, exc, tb)` and `athrow(type, exc, tb)` signature is deprecated: use `throw(exc)` and `athrow(exc)` instead, the single argument signature.
  - Currently Python accepts numeric literals immediately followed by keywords, for example `0in x`, `1or x`, `0if 1else 2`. It allows confusing and ambiguous expressions like `[0x1for x in y]` (which can be interpreted as `[0x1 for x in y]` or `[0x1f or x in y]`). A syntax warning is raised if the numeric literal is immediately followed by one of keywords `and`, `else`, `for`, `if`, `in`, `is` and `or`. In a future release it will be changed to a syntax error. (gh-87999)
  - Support for `__index__()` and `__int__()` method returning non-int type: these methods will be required to return an instance of a strict subclass of `int`.
  - Support for `__float__()` method returning a strict subclass of `float`: these methods will be required to return an instance of `float`.
  - Support for `__complex__()` method returning a strict subclass of `complex`: these methods will be required to return an instance of `complex`.
  - Passing a complex number as the real or imag argument in the `complex()` constructor is now deprecated; it should only be passed as a single positional argument. (Contributed by Serhiy Storchaka in gh-109218.)
- `calendar`: `calendar.January` and `calendar.February` constants are deprecated and replaced by `calendar.JANUARY` and `calendar.FEBRUARY`. (Contributed by Prince Roshan in gh-103636.)
- `codecs`: use `open()` instead of `codecs.open()`. (gh-133038)
- `codeobject.co_lnotab`: use the `codeobject.co_lines()` method instead.
- `datetime`:
  - `utcnow()`: use `datetime.datetime.now(tz=datetime.UTC)`.
  - `utcfromtimestamp()`: use `datetime.datetime.fromtimestamp(timestamp, tz=datetime.UTC)`.
- `gettext`: Plural value must be an integer.
- `importlib`:
  - `cache_from_source()` debug_override parameter is deprecated: use the optimization parameter instead.
- `importlib.metadata`:
  - `EntryPoints` tuple interface.
  - Implicit `None` on return values.
- `logging`: the `warn()` method has been deprecated since Python 3.3, use `warning()` instead.
- `mailbox`: Use of StringIO input and text mode is deprecated, use BytesIO and binary mode instead.
- `os`: Calling `os.register_at_fork()` in a multi-threaded process.
- `os.path`: `os.path.commonprefix()` is deprecated, use `os.path.commonpath()` for path prefixes. The `os.path.commonprefix()` function is being deprecated due to having a misleading name and module. The function is not safe to use for path prefixes despite being included in a module about path manipulation, meaning it is easy to accidentally introduce path traversal vulnerabilities into Python programs by using this function.
- `pydoc.ErrorDuringImport`: A tuple value for exc_info parameter is deprecated, use an exception instance.
- `re`: More strict rules are now applied for numerical group references and group names in regular expressions. Only sequence of ASCII digits is now accepted as a numerical reference. The group name in bytes patterns and replacement strings can now only contain ASCII letters and digits and underscore. (Contributed by Serhiy Storchaka in gh-91760.)
- `shutil`: `rmtree()`’s onerror parameter is deprecated in Python 3.12; use the onexc parameter instead.
- `ssl` options and protocols:
  - `ssl.SSLContext` without protocol argument is deprecated.
  - `ssl.SSLContext`: `set_npn_protocols()` and `selected_npn_protocol()` are deprecated: use ALPN instead.
  - `ssl.OP_NO_SSL*` options
  - `ssl.OP_NO_TLS*` options
  - `ssl.PROTOCOL_SSLv3`
  - `ssl.PROTOCOL_TLS`
  - `ssl.PROTOCOL_TLSv1`
  - `ssl.PROTOCOL_TLSv1_1`
  - `ssl.PROTOCOL_TLSv1_2`
  - `ssl.TLSVersion.SSLv3`
  - `ssl.TLSVersion.TLSv1`
  - `ssl.TLSVersion.TLSv1_1`
- `threading` methods:
  - `threading.Condition.notifyAll()`: use `notify_all()`.
  - `threading.Event.isSet()`: use `is_set()`.
  - `threading.Thread.isDaemon()`, `threading.Thread.setDaemon()`: use `threading.Thread.daemon` attribute.
  - `threading.Thread.getName()`, `threading.Thread.setName()`: use `threading.Thread.name` attribute.
  - `threading.currentThread()`: use `threading.current_thread()`.
  - `threading.activeCount()`: use `threading.active_count()`.
- `typing.Text` (gh-92332).
- The internal class `typing._UnionGenericAlias` is no longer used to implement `typing.Union`. To preserve compatibility with users using this private class, a compatibility shim will be provided until at least Python 3.17. (Contributed by Jelle Zijlstra in gh-105499.)
- `unittest.IsolatedAsyncioTestCase`: it is deprecated to return a value that is not `None` from a test case.
- `urllib.parse` deprecated functions: `urlparse()` instead
  - `splitattr()`
  - `splithost()`
  - `splitnport()`
  - `splitpasswd()`
  - `splitport()`
  - `splitquery()`
  - `splittag()`
  - `splittype()`
  - `splituser()`
  - `splitvalue()`
  - `to_bytes()`
- `wsgiref`: `SimpleHandler.stdout.write()` should not do partial writes.
- `xml.etree.ElementTree`: Testing the truth value of an `Element` is deprecated. In a future release it will always return `True`. Prefer explicit `len(elem)` or `elem is not None` tests instead.
- `sys._clear_type_cache()` is deprecated: use `sys._clear_internal_caches()` instead.

### Soft deprecations

There are no plans to remove soft deprecated APIs.

- `re.match()` and `re.Pattern.match()` are now soft deprecated in favor of the new `re.prefixmatch()` and `re.Pattern.prefixmatch()` APIs, which have been added as alternate, more explicit names. These are intended to be used to alleviate confusion around what match means by following the Zen of Python’s “Explicit is better than implicit” mantra. Most other language regular expression libraries use an API named match to mean what Python has always called search.
  We do not plan to remove the older `match()` name, as it has been used in code for over 30 years. Code supporting older versions of Python should continue to use `match()`, while new code should prefer `prefixmatch()`. See prefixmatch() vs. match().
  (Contributed by Gregory P. Smith in gh-86519 and Hugo van Kemenade in gh-148100.)
- Using `'F'` and `'D'` format type codes of the `struct` module now are soft deprecated in favor of two-letter forms `'Zf'` and `'Zd'`. (Contributed by Sergey B Kirpichev in gh-121249.)
