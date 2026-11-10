---
source: https://docs.python.org/3.15/whatsnew/3.15.html
fetched: 2026-11-10
published: 2026-10-09
title: What’s new in Python 3.15 — Improved modules, os to zlib
---

# What’s new in Python 3.15 (continued: Improved modules, os to zlib)

### os

- Add `os.statx()` on Linux kernel versions 4.11 and later with glibc versions 2.28 and later. (Contributed by Jeffrey Bosboom and Victor Stinner in gh-83714.)
- `os.makedirs()` function now has a parent_mode parameter that allows specifying the mode for intermediate directories. This can be used to match the behavior from Python 3.6 and earlier by passing `parent_mode=mode`. (Contributed by Zackery Spytz and Gregory P. Smith in gh-86533.)

### os.path

- Add support of the all-but-last mode in `realpath()`. (Contributed by Serhiy Storchaka in gh-71189.)
- The strict parameter to `os.path.realpath()` accepts a new value, `os.path.ALLOW_MISSING`. If used, errors other than `FileNotFoundError` will be re-raised; the resulting path can be missing but it will be free of symlinks. (Contributed by Petr Viktorin for CVE 2025-4517.)

### pathlib

- `pathlib.Path.mkdir()` now has a parent_mode parameter that allows specifying the mode for intermediate directories when `parents=True`. (Contributed by Gregory P. Smith in gh-86533.)

### pdb

- Use the new interactive shell as the default input shell for `pdb`. (Contributed by Tian Gao in gh-145379.)

### pickle

- Add support for pickling private methods and nested classes. (Contributed by Zackery Spytz and Serhiy Storchaka in gh-77188.)

### pickletools

- The output of the `pickletools` command-line interface is colored by default. This can be controlled with environment variables. (Contributed by Hugo van Kemenade in gh-149026.)

### pprint

- Add an expand keyword argument for `pprint.pprint()`, `pprint.pformat()`, `pprint.pp()`. If true, the output will be formatted similar to pretty-printed `json.dumps()` when indent is supplied. (Contributed by Stefan Todoran, Semyon Moroz and Hugo van Kemenade in gh-112632.)
- Add t-string support to `pprint`. (Contributed by Loïc Simon and Hugo van Kemenade in gh-134551.)

### re

- `re.prefixmatch()` and a corresponding `re.Pattern.prefixmatch()` have been added as alternate, more explicit names for the existing and now soft deprecated `re.match()` and `re.Pattern.match()` APIs. These are intended to be used to alleviate confusion around what match means by following the Zen of Python’s “Explicit is better than implicit” mantra. Most other language regular expression libraries use an API named match to mean what Python has always called search. (Contributed by Gregory P. Smith in gh-86519.)

### resource

- Add new constants: `RLIMIT_NTHR`, `RLIMIT_UMTXP`, `RLIMIT_THREADS`, `RLIM_SAVED_CUR`, and `RLIM_SAVED_MAX`. (Contributed by Serhiy Storchaka in gh-137512.)

### shelve

- Added new `reorganize()` method to `shelve` used to recover unused free space previously occupied by deleted entries. (Contributed by Andrea Oliveri in gh-134004.)
- Add support for custom serialization and deserialization functions in the `shelve` module. (Contributed by Furkan Onder in gh-99631.)

### socket

- Add constants for the ISO-TP CAN protocol. (Contributed by Patrick Menschel and Stefan Tatschner in gh-86819.)

### sqlite3

- The command-line interface has several new features:
  - SQL keyword completion on `Tab`. (Contributed by Long Tan in gh-133393.)
  - Prompts, error messages, and help text are now colored. This is enabled by default, see Controlling color for details. (Contributed by Stan Ulbrych and Łukasz Langa in gh-133461.)
  - Table, index, trigger, view, column, function, and schema completion on `Tab`. (Contributed by Long Tan in gh-136101.)

### ssl

- Indicate through `ssl.HAS_PSK_TLS13` whether the `ssl` module supports “External PSKs” in TLSv1.3, as described in RFC 9258. (Contributed by Will Childs-Klein in gh-133624.)
- Added new methods for managing groups used for SSL key agreement:
  - `ssl.SSLContext.set_groups()` sets the groups allowed for doing key agreement, extending the previous `ssl.SSLContext.set_ecdh_curve()` method. This new API provides the ability to list multiple groups and supports finite-field and post-quantum groups in addition to ECDH curves. This method can also be used to control what key shares are sent in the TLS handshake.
  - `ssl.SSLSocket.group()` returns the group selected for doing key agreement on the current connection after the TLS handshake completes. This call requires OpenSSL 3.2 or later.
  - `ssl.SSLContext.get_groups()` returns a list of all available key agreement groups compatible with the minimum and maximum TLS versions currently set in the context. This call requires OpenSSL 3.5 or later.
  (Contributed by Ron Frederick in gh-136306.)
- Added a new method `ssl.SSLContext.set_ciphersuites()` for setting TLS 1.3 ciphers. For TLS 1.2 or earlier, `ssl.SSLContext.set_ciphers()` should continue to be used. Both calls can be made on the same context and the selected cipher suite will depend on the TLS version negotiated when a connection is made. (Contributed by Ron Frederick in gh-137197.)
- Added new methods for managing signature algorithms:
  - `ssl.get_sigalgs()` returns a list of all available TLS signature algorithms. This call requires OpenSSL 3.4 or later.
  - `ssl.SSLContext.set_client_sigalgs()` sets the signature algorithms allowed for certificate-based client authentication.
  - `ssl.SSLContext.set_server_sigalgs()` sets the signature algorithms allowed for the server to complete the TLS handshake.
  - `ssl.SSLSocket.client_sigalg()` returns the signature algorithm selected for client authentication on the current connection. This call requires OpenSSL 3.5 or later.
  - `ssl.SSLSocket.server_sigalg()` returns the signature algorithm selected for the server to complete the TLS handshake on the current connection. This call requires OpenSSL 3.5 or later.
  (Contributed by Ron Frederick in gh-138252.)

### subprocess

- `subprocess.Popen.wait()`: when `timeout` is not `None` and the platform supports it, an efficient event-driven mechanism is used to wait for process termination:
  - Linux >= 5.3 uses `os.pidfd_open()` + `select.poll()`.
  - macOS and other BSD variants use `select.kqueue()` + `KQ_FILTER_PROC` + `KQ_NOTE_EXIT`.
  - Windows keeps using `WaitForSingleObject` (unchanged).
  If none of these mechanisms are available, the function falls back to the traditional busy loop (non-blocking call and short sleeps). (Contributed by Giampaolo Rodola in gh-83069.)

### symtable

- Add `symtable.Function.get_cells()` and `symtable.Symbol.is_cell()` methods. (Contributed by Yashp002 in gh-143504.)

### sys

- Add `sys.abi_info` namespace to improve access to ABI information. (Contributed by Klaus Zimmermann in gh-137476.)

### sys.monitoring

- The other events (`PY_THROW`, `PY_UNWIND`, `RAISE`, `EXCEPTION_HANDLED`, and `RERAISE`) can now be turned on and disabled on a per code object basis. Returning `DISABLE` from a callback for one of these events disables the event for the entire code object (for the current tool), rather than raising `ValueError` as in prior versions. (Contributed by Gabriele N. Tornetta in gh-146182.)

### tarfile

- `data_filter()` now normalizes symbolic link targets in order to avoid path traversal attacks. (Contributed by Petr Viktorin in gh-127987 and CVE 2025-4138.)
- `extractall()` now skips fixing up directory attributes when a directory was removed or replaced by another kind of file. (Contributed by Petr Viktorin in gh-127987 and CVE 2024-12718.)
- `extract()` and `extractall()` now (re-)apply the extraction filter when substituting a link (hard or symbolic) with a copy of another archive member, and when fixing up directory attributes. The former raises a new exception, `LinkFallbackError`. (Contributed by Petr Viktorin for CVE 2025-4330 and CVE 2024-12718.)
- `extract()` and `extractall()` no longer extract rejected members when `errorlevel()` is zero. (Contributed by Matt Prodani and Petr Viktorin in gh-112887 and CVE 2025-4435.)
- `extract()` and `extractall()` now replace slashes with backslashes in symlink targets on Windows to prevent creation of corrupted links. (Contributed by Christoph Walcher in gh-57911.)
- `gettarinfo()` now replaces backslashes with slashes in symlink targets on Windows to conform to the tar format standard. (Contributed by Daniele Nicolodi in gh-151669.)

### threading

- Added `serialize_iterator`, `synchronized_iterator()`, and `concurrent_tee()` to support concurrent access to generators and iterators. (Contributed by Raymond Hettinger in gh-124397.)

### timeit

- The output of the `timeit` command-line interface is colored by default. This can be controlled with environment variables. (Contributed by Hugo van Kemenade in gh-146609.)
- The command-line interface now colorizes error tracebacks by default. This can be controlled with environment variables. (Contributed by Yi Hong in gh-139374.)
- Make the target time of `timeit.Timer.autorange()` configurable and add `--target-time` option to the command-line interface. (Contributed by Alessandro Cucci and Miikka Koskinen in gh-80642.)

### tkinter

- The `tkinter.Text.search()` method now supports two additional arguments: nolinestop which allows the search to continue across line boundaries; and strictlimits which restricts the search to within the specified range. (Contributed by Rihaan Meher in gh-130848.)
- A new method `tkinter.Text.search_all()` has been introduced. This method allows for searching for all matches of a pattern using Tcl’s `-all` and `-overlap` options. (Contributed by Rihaan Meher in gh-130848.)
- Added new methods `pack_content()`, `place_content()` and `grid_content()` which use Tk commands with new names (introduced in Tk 8.6) instead of `*_slaves()` methods which use Tk commands with outdated names. (Contributed by Serhiy Storchaka in gh-143754.)
- Added `Event` attributes `user_data` for Tk virtual events and `detail` for `Enter`, `Leave`, `FocusIn`, `FocusOut`, and `ConfigureRequest` events. (Contributed by Matthias Kievernagel and Serhiy Storchaka in gh-47655.)

### tokenize

- The output of the `tokenize` command-line interface is colored by default. This can be controlled with environment variables. (Contributed by Hugo van Kemenade in gh-148991.)

### tomllib

- The `tomllib` module now supports TOML 1.1.0. This is a backwards compatible update, meaning that all valid TOML 1.0.0 documents are parsed the same way.
  The changes, according to the official TOML changelog, are:
  - Allow newlines and trailing commas in inline tables.
    Previously an inline table had to be on a single line and couldn’t end with a trailing comma. This is now relaxed so that the following is valid:
    ```
    tbl = {
       key      = "a string",
       moar-tbl =  {
          key = 1,
       },
    }
    ```
  - Add `\xHH` notation to basic strings for codepoints under 255, and the `\e` escape for the escape character:
    ```
    null = "null byte: \x00; letter a: \x61"
    csi = "\e["
    ```
  - Seconds in datetime and time values are now optional. The following are now valid:
    ```
    dt = 2010-02-03 14:15
    t  = 14:15
    ```
  (Contributed by Taneli Hukkinen in gh-142956.)

### types

- Expose the write-through `locals()` proxy type as `types.FrameLocalsProxyType`. This represents the type of the `frame.f_locals` attribute, as described in PEP 667. (Contributed by Peter Bierma in gh-136492.)

### typing

- PEP 747: Add `TypeForm`, a new special form for annotating values that are themselves type expressions. `TypeForm[T]` means “a type form object describing `T` (or a type assignable to `T`)”. At runtime, `TypeForm(x)` simply returns `x`, which allows explicit annotation of type-form values without changing behavior.
  This helps libraries that accept user-provided type expressions (for example `int`, `str | None`, `TypedDict` classes, or `list[int]`) expose precise signatures:
  ```
  from typing import Any, TypeForm
  
  def cast[T](typ: TypeForm[T], value: Any) -> T: ...
  ```
  (Contributed by Jelle Zijlstra in gh-145033.)

- PEP 728: Add support in `TypedDict` for the closed and extra_items class arguments. A closed `TypedDict` does not allow extra keys beyond those specified in the class body, while a `TypedDict` with `extra_items` allows arbitrary extra items where the values are of the specified type. (Contributed by Angela Liss in gh-137840.)
- Code like `class ExtraTypeVars(P1[S], Protocol[T, T2]): ...` now raises a `TypeError`, because `S` is not listed in `Protocol` parameters. (Contributed by Nikita Sobolev in gh-137191.)
- Code like `class B2(A[T2], Protocol[T1, T2]): ...` now correctly handles type parameters order: it is `(T1, T2)`, not `(T2, T1)` as it was incorrectly inferred at runtime before. (Contributed by Nikita Sobolev in gh-137191.)
- PEP 800: Add `@typing.disjoint_base`, a new decorator marking a class as a disjoint base. This is an advanced feature primarily intended to allow type checkers to faithfully reflect the runtime semantics of types defined as builtins or in compiled extensions. If a class `C` is a disjoint base, then child classes of that class cannot inherit from other disjoint bases that are not parent or child classes of `C`. (Contributed by Jelle Zijlstra in gh-148639.)
- `TypeVarTuple` now accepts `bound`, `covariant`, `contravariant`, and `infer_variance` keyword arguments, matching the interface of `TypeVar` and `ParamSpec`. `bound` semantics remain undefined in the specification.

### unicodedata

- The Unicode database has been updated to Unicode 17.0.0. (Contributed by Benjamin Peterson in gh-138706.)
- Add `unicodedata.isxidstart()` and `unicodedata.isxidcontinue()` functions to check whether a character can start or continue a Unicode Standard Annex #31 identifier. (Contributed by Stan Ulbrych in gh-129117.)
- Add the `iter_graphemes()` function to iterate over grapheme clusters according to rules defined in Unicode Standard Annex #29, “Unicode Text Segmentation”. Add `grapheme_cluster_break()`, `indic_conjunct_break()` and `extended_pictographic()` functions to get the properties of the character which are related to the above algorithm. (Contributed by Serhiy Storchaka and Guillaume Sanchez in gh-74902.)
- Add `block()` function to return the Unicode block assigned to a character. (Contributed by Stan Ulbrych in gh-66802.)

### unittest

- `unittest.TestCase.assertLogs()` will now accept a formatter to control how messages are formatted. (Contributed by Garry Cairns in gh-134567.)
- `unittest.TestCase.assertWarns()` and `unittest.TestCase.assertWarnsRegex()` no longer swallow warnings that do not match the specified category or regex. Nested context managers are now supported. (Contributed by Serhiy Storchaka in gh-143231.)

### urllib.parse

- Add the missing_as_none parameter to `urlsplit()`, `urlparse()` and `urldefrag()` functions. Add the keep_empty parameter to `urlunsplit()` and `urlunparse()` functions. This allows distinguishing between empty and undefined URI components and preserving empty components. (Contributed by Serhiy Storchaka in gh-67041.)

### venv

- On POSIX platforms, platlib directories will be created if needed when creating virtual environments, instead of using a `lib64 -> lib` symlink. This means purelib and platlib of virtual environments no longer share the same `lib` directory on platforms where `sys.platlibdir` is not equal to `lib`. (Contributed by Rui Xi in gh-133951.)

### warnings

- Improve filtering by module in `warnings.warn_explicit()` if no module argument is passed. It now tests the module regular expression in the warnings filter not only against the filename with `.py` stripped, but also against module names constructed starting from different parent directories of the filename (with `/__init__.py`, `.py` and, on Windows, `.pyw` stripped). (Contributed by Serhiy Storchaka in gh-135801.)

### wave

- Added support for IEEE floating-point WAVE audio (`WAVE_FORMAT_IEEE_FLOAT`) in `wave`.
- Added `wave.Wave_read.getformat()`, `wave.Wave_write.getformat()`, and `wave.Wave_write.setformat()` for explicit frame format handling.
- `wave.Wave_write.setparams()` accepts both 7-item tuples including `format` and 6-item tuples for backwards compatibility (defaulting to `WAVE_FORMAT_PCM`).
- `WAVE_FORMAT_IEEE_FLOAT` output now includes a `fact` chunk, as required for non-PCM WAVE formats.

(Contributed by Lionel Koenig and Michiel W. Beijen in gh-60729.)

### webbrowser

- On macOS, the new `webbrowser.MacOS` class opens URLs via /usr/bin/open instead of constructing and executing AppleScript via osascript. The default browser is detected from the LaunchServices preferences file using `plistlib`, with `com.apple.Safari` as the fallback on fresh installations. For non-HTTP(S) URLs, open -b <bundle-id> is used to route the URL through a browser rather than the OS file handler, preventing file injection attacks. (Contributed by Jeff Lyon in gh-137586.)

### xml

- Add the `xml.is_valid_name()` function to check whether a string can be used as an element or attribute name in XML. (Contributed by Serhiy Storchaka in gh-139489.)
- Add the `xml.is_valid_text()` function to check whether a string can be used in an XML document. (Contributed by Serhiy Storchaka in gh-139489.)

### xml.parsers.expat

- Add `SetAllocTrackerActivationThreshold()` and `SetAllocTrackerMaximumAmplification()` to xmlparser objects to tune protections against disproportional amounts of dynamic memory usage from within an Expat parser. (Contributed by Bénédikt Tran in gh-90949.)
- Add `SetBillionLaughsAttackProtectionActivationThreshold()` and `SetBillionLaughsAttackProtectionMaximumAmplification()` to xmlparser objects to tune protections against billion laughs attacks. (Contributed by Bénédikt Tran in gh-90949.)

### zlib

- Allow combining two Adler-32 checksums via `adler32_combine()`. (Contributed by Callum Attryde and Bénédikt Tran in gh-134635.)
- Allow combining two CRC-32 checksums via `crc32_combine()`. (Contributed by Bénédikt Tran in gh-134635.)
