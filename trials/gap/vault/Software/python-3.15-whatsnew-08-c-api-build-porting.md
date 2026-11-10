---
source: https://docs.python.org/3.15/whatsnew/3.15.html
fetched: 2026-11-10
published: 2026-10-09
title: What’s new in Python 3.15 — C API changes, build changes, porting, notable changes in 3.15.2
---

# What’s new in Python 3.15 (continued: C API changes, build changes, porting, notable changes in 3.15.2)

## C API changes

### New features

- Add `PyArg_ParseArray()` and `PyArg_ParseArrayAndKeywords()` functions to parse arguments of functions using the `METH_FASTCALL` calling convention. (Contributed by Victor Stinner in gh-144175.)
- Add the following functions for the new `frozendict` type:
  - `PyAnyDict_Check()`
  - `PyAnyDict_CheckExact()`
  - `PyFrozenDict_Check()`
  - `PyFrozenDict_CheckExact()`
  - `PyFrozenDict_New()`
  (Contributed by Victor Stinner in gh-141510.)
- Add `PyObject_CallFinalizerFromDealloc()` function to the limited C API. (Contributed by Victor Stinner in gh-146063.)
- Add `PySys_GetAttr()`, `PySys_GetAttrString()`, `PySys_GetOptionalAttr()`, and `PySys_GetOptionalAttrString()` functions as replacements for `PySys_GetObject()`. (Contributed by Serhiy Storchaka in gh-108512.)
- Add `PyUnstable_Unicode_GET_CACHED_HASH()` to get the cached hash of a string. See the documentation for caveats. (Contributed by Petr Viktorin in gh-131510.)
- Add API for checking an extension module’s ABI compatibility: `Py_mod_abi`, `PyABIInfo_Check()`, and `PyABIInfo_VAR`. (Contributed by Petr Viktorin in gh-137210.)

- Implement PEP 782, the PyBytesWriter API. Add functions:
  - `PyBytesWriter_Create()`
  - `PyBytesWriter_Discard()`
  - `PyBytesWriter_Finish()`
  - `PyBytesWriter_FinishWithPointer()`
  - `PyBytesWriter_FinishWithSize()`
  - `PyBytesWriter_Format()`
  - `PyBytesWriter_GetData()`
  - `PyBytesWriter_GetSize()`
  - `PyBytesWriter_Grow()`
  - `PyBytesWriter_GrowAndUpdatePointer()`
  - `PyBytesWriter_Resize()`
  - `PyBytesWriter_WriteBytes()`
  (Contributed by Victor Stinner in gh-129813.)
- `PyCriticalSection` and related functions are added to the Stable ABI. (Contributed by Petr Viktorin in gh-149225.)
- Add a new `PyImport_CreateModuleFromInitfunc()` C API for creating a module from a spec and initfunc. (Contributed by Itamar Oren in gh-116146.)
- Add `PyTuple_FromArray()` to create a `tuple` from an array. (Contributed by Victor Stinner in gh-111489.)
- Add a new module export hook, `PyModExport_*`.
  (Contributed by Petr Viktorin in PEP 793 and gh-140550.)
- Add functions that are guaranteed to be safe for use in `tp_traverse` handlers: `PyObject_GetTypeData_DuringGC()`, `PyObject_GetItemData_DuringGC()`, `PyType_GetModuleState_DuringGC()`, `PyModule_GetState_DuringGC()`, `PyModule_GetToken_DuringGC()`, `PyType_GetBaseByToken_DuringGC()`, `PyType_GetModule_DuringGC()`, `PyType_GetModuleByToken_DuringGC()`. (Contributed by Petr Viktorin in gh-145925.)
- Add `PyObject_Dump()` to dump an object to `stderr`. It should only be used for debugging. (Contributed by Victor Stinner in gh-141070.)
- Implement PEP 820: `PySlot` – Unified slot system for the C API. See Definition slots for documentation.
  This adds:
  - The `PySlot` struct;
  - the `PyType_FromSlots()` function;
  - new slot IDs: `Py_slot_end`, `Py_slot_invalid`; `Py_slot_subslots`, `Py_tp_slots`, `Py_mod_slots`; `Py_tp_name`, `Py_tp_basicsize`, `Py_tp_extra_basicsize`, `Py_tp_itemsize`, `Py_tp_flags`, `Py_tp_metaclass`, `Py_tp_module`;
  - convenience macros: `PySlot_DATA`, `PySlot_FUNC`, `PySlot_SIZE`, `PySlot_INT64`, `PySlot_UINT64`, `PySlot_STATIC_DATA`, `PySlot_END`, `PySlot_PTR`, `PySlot_PTR_STATIC`.
  The `PyModule_FromSlotsAndSpec()` function and `PyModExport` module export hook also use the new `PySlot` struct.
  The following functions are soft deprecated:
  - `PyType_FromSpec()`
  - `PyType_FromSpecWithBases()`
  - `PyType_FromModuleAndSpec()`
  - `PyType_FromMetaclass()`
  - `PyModule_FromDefAndSpec()`
  - `PyModule_FromDefAndSpec2()`
  - `PyModule_ExecDef()`
  The slots `Py_tp_bases` and `Py_tp_base` are now equivalent: they can be set either to a single type or a tuple of types. The `Py_tp_bases` slot is preferred; the other is ignored if both are specified.
  (Contributed by Petr Viktorin in gh-149044.)
- Add `PyUnstable_ThreadState_SetStackProtection()` and `PyUnstable_ThreadState_ResetStackProtection()` functions to set the stack protection base address and stack protection size of a Python thread state. (Contributed by Victor Stinner in gh-139653.)
- Add `PyUnstable_SetImmortal()` C API function to mark objects as immortal. (Contributed by Kumar Aditya in gh-143300.)
- Restore private provisional `_Py_InitializeMain()` function removed in Python 3.14. (Contributed by Victor Stinner in gh-142417.)
- Add `PyUnstable_DumpTraceback()` and `PyUnstable_DumpTracebackThreads()` functions to output Python stacktraces. (Contributed by Alex Malyshev in gh-145559.)

### Changed C APIs

- If the `Py_TPFLAGS_MANAGED_DICT` or `Py_TPFLAGS_MANAGED_WEAKREF` flag is set then `Py_TPFLAGS_HAVE_GC` must be set too. (Contributed by Sergey Miryanov in gh-134786.)
- `PyDateTime_IMPORT` is now thread safe. Code that directly checks `PyDateTimeAPI` for `NULL` should be updated to call `PyDateTime_IMPORT` instead. (Contributed by Kumar Aditya in gh-141563.)

### Removed C APIs

- Remove deprecated `PyUnicode` functions:
  - `PyUnicode_AsDecodedObject()`: Use `PyCodec_Decode()` instead.
  - `PyUnicode_AsDecodedUnicode()`: Use `PyCodec_Decode()` instead; note that some codecs (for example, “base64”) may return a type other than `str`, such as `bytes`.
  - `PyUnicode_AsEncodedObject()`: Use `PyCodec_Encode()` instead.
  - `PyUnicode_AsEncodedUnicode()`: Use `PyCodec_Encode()` instead; note that some codecs (for example, “base64”) may return a type other than `bytes`, such as `str`.
  (Contributed by Stan Ulbrych in gh-133612.)
- `PyImport_ImportModuleNoBlock()`: deprecated alias of `PyImport_ImportModule()`. (Contributed by Bénédikt Tran in gh-133644.)
- `PyWeakref_GetObject()` and `PyWeakref_GET_OBJECT`: use `PyWeakref_GetRef()` instead. The pythoncapi-compat project can be used to get `PyWeakref_GetRef()` on Python 3.12 and older. (Contributed by Bénédikt Tran in gh-133644.)
- Remove deprecated `PySys_ResetWarnOptions()`. Clear `sys.warnoptions` and `warnings.filters` instead.
  (Contributed by Nikita Sobolev in gh-138886.)

The following functions are removed in favor of `PyConfig_Get()`. The pythoncapi-compat project can be used to get `PyConfig_Get()` on Python 3.13 and older.

- Python initialization functions:
  - `Py_GetExecPrefix()`: use `PyConfig_Get("base_exec_prefix")` (`sys.base_exec_prefix`) instead. Use `PyConfig_Get("exec_prefix")` (`sys.exec_prefix`) if virtual environments need to be handled.
  - `Py_GetPath()`: use `PyConfig_Get("module_search_paths")` (`sys.path`) instead.
  - `Py_GetPrefix()`: use `PyConfig_Get("base_prefix")` (`sys.base_prefix`) instead. Use `PyConfig_Get("prefix")` (`sys.prefix`) if virtual environments need to be handled.
  - `Py_GetProgramFullPath()`: use `PyConfig_Get("executable")` (`sys.executable`) instead.
  - `Py_GetProgramName()`: use `PyConfig_Get("executable")` (`sys.executable`) instead.
  - `Py_GetPythonHome()`: use `PyConfig_Get("home")` or the `PYTHONHOME` environment variable instead.
  (Contributed by Bénédikt Tran in gh-133644.)

### Deprecated C APIs

- Deprecate PEP 456 support for providing an external definition of the string hashing scheme. Removal is scheduled for Python 3.19.
  Previously, embedders could define `Py_HASH_ALGORITHM` to be `Py_HASH_EXTERNAL` to indicate that the hashing scheme was provided externally but this feature was undocumented, untested and most likely unused.
  (Contributed by Bénédikt Tran in gh-141226.)
- For unsigned integer formats in `PyArg_ParseTuple()`, accepting Python integers with value that is larger than the maximal value for the C type or less than the minimal value for the corresponding signed integer type of the same size is now deprecated. (Contributed by Serhiy Storchaka in gh-132629.)
- `PyBytes_FromStringAndSize(NULL, len)` and `_PyBytes_Resize()` are soft deprecated, use the `PyBytesWriter` API instead. (Contributed by Victor Stinner in gh-129813.)
- `_PyObject_CallMethodId()`, `_PyObject_GetAttrId()` and `_PyUnicode_FromId()` are deprecated since Python 3.15 and will be removed in Python 3.20. Instead, use `PyUnicode_InternFromString()` and cache the result in the module state, then call `PyObject_CallMethod()` or `PyObject_GetAttr()`. (Contributed by Victor Stinner in gh-141049.)
- Deprecate `cval` field of the `PyComplexObject` type. Use `PyComplex_AsCComplex()` and `PyComplex_FromCComplex()` to convert a Python complex number to/from the C `Py_complex` representation. (Contributed by Sergey B Kirpichev in gh-128813.)
- Functions `_Py_c_sum()`, `_Py_c_diff()`, `_Py_c_neg()`, `_Py_c_prod()`, `_Py_c_quot()`, `_Py_c_pow()` and `_Py_c_abs()` are soft deprecated. (Contributed by Sergey B Kirpichev in gh-128813.)
- `bytes_warning` is deprecated since Python 3.15 and will be removed in Python 3.17. (Contributed by Nikita Sobolev in gh-136355.)
- `Py_INFINITY` macro is soft deprecated, use the C11 standard `<math.h>` `INFINITY` instead. (Contributed by Sergey B Kirpichev in gh-141004.)
- The following macros are soft deprecated:
  - `Py_ALIGNED`: Prefer `alignas` instead.
  - `PY_FORMAT_SIZE_T`: Use `"z"` directly.
  - `Py_LL` and `Py_ULL`: Use standard suffixes, `LL` and `ULL`.
  - `PY_LONG_LONG`, `PY_LLONG_MIN`, `PY_LLONG_MAX`, `PY_ULLONG_MAX`, `PY_INT32_T`, `PY_UINT32_T`, `PY_INT64_T`, `PY_UINT64_T`, `PY_SIZE_MAX`: Use C99 types/limits.
  - `Py_UNICODE_SIZE`: Use `sizeof(wchar_t)` directly.
  - `Py_VA_COPY`: Use `va_copy` directly.
  The macro `Py_UNICODE_WIDE`, which was scheduled for removal, is soft deprecated instead.
  (Contributed by Petr Viktorin in gh-146175.)
- `Py_MATH_El` and `Py_MATH_PIl` are deprecated since Python 3.15 and will be removed in Python 3.20. (Contributed by Sergey B Kirpichev in gh-141004.)

## Build changes

- Removed implicit fallback to the bundled copy of the `libmpdec` library. Now this should be explicitly enabled with `--with-system-libmpdec` set to `no` or with `--without-system-libmpdec`. (Contributed by Sergey B Kirpichev in gh-115119.)
- The new configure option `--with-missing-stdlib-config=FILE` allows distributors to pass a JSON configuration file containing custom error messages for standard library modules that are missing or packaged separately. (Contributed by Stan Ulbrych and Petr Viktorin in gh-139707.)
- The new configure option `--with-pymalloc-hugepages` enables huge page support for pymalloc arenas. When enabled, arena size increases to 2 MiB and allocation uses `MAP_HUGETLB` (Linux) or `MEM_LARGE_PAGES` (Windows) with automatic fallback to regular pages. On Windows, use `build.bat --pymalloc-hugepages`. At runtime, huge pages must be explicitly enabled by setting the `PYTHON_PYMALLOC_HUGEPAGES` environment variable to `1`. (Contributed by Pablo Galindo Salgado in gh-144319.)
- Annotating anonymous mmap usage is now supported if the Linux kernel supports PR_SET_VMA_ANON_NAME (Linux 5.17 or newer). Annotations are visible in `/proc/<pid>/maps` if the kernel supports the feature and `-X dev` is passed to Python, or Python is built in debug mode. (Contributed by Donghee Na in gh-141770.)
- CPython is now built with frame pointers enabled by default (PEP 831). Pass `--without-frame-pointers` to opt out.
  Authors of C extensions and native libraries built with custom build systems should ensure the unwind chain is intact. This is usually done by adding `-fno-omit-frame-pointer` and similar flags to `CFLAGS`. See `--without-frame-pointers` documentation for the specific flags Python uses.
  (Contributed by Pablo Galindo Salgado and Savannah Ostrowski in gh-149201.)

- 64-bit builds using Visual Studio 2026 (MSVC 18) may now use the new tail-calling interpreter. Results on Visual Studio 18.1.1 report between 15-20% speedup on the geometric mean of pyperformance on Windows x86-64 over the switch-case interpreter on an AMD Ryzen 7 5800X. We have observed speedups ranging from 14% for large pure-Python libraries to 40% for long-running small pure-Python scripts on Windows. This was made possible by a new feature introduced in MSVC 18, which the official Windows 64-bit binaries on python.org now use. (Contributed by Chris Eibl, Ken Jin, and Brandt Bucher in gh-143068. Special thanks to Steve Dower, and the MSVC team including Hulon Jenkins.)

## Porting to Python 3.15

This section lists previously described changes and other bugfixes that may require changes to your code.

- `sqlite3.Connection` APIs have been cleaned up.
  - All parameters of `sqlite3.connect()` except database are now keyword-only.
  - The first three parameters of methods `create_function()` and `create_aggregate()` are now positional-only.
  - The first parameter of methods `set_authorizer()`, `set_progress_handler()` and `set_trace_callback()` is now positional-only.
  (Contributed by Serhiy Storchaka in gh-133595.)
- `resource.RLIM_INFINITY` is now always positive. Passing a negative integer value that corresponded to its old value (such as `-1` or `-3`, depending on platform) to `resource.setrlimit()` and `resource.prlimit()` is now deprecated. (Contributed by Serhiy Storchaka in gh-137044.)
- `mmap.mmap.resize()` has been removed on platforms that don’t support the underlying syscall, instead of raising a `SystemError`. (Contributed by An Long in gh-138205.)
- A resource warning is now emitted for an unclosed `xml.etree.ElementTree.iterparse()` iterator if it opened a file. Use its `close()` method or the `contextlib.closing()` context manager to close it. (Contributed by Osama Abdelkader and Serhiy Storchaka in gh-140601.)
- If a short option and a single-dash long option are passed to `argparse.ArgumentParser.add_argument()`, dest is now inferred from the single-dash long option. For example, in `add_argument('-f', '-foo')`, dest is now `'foo'` instead of `'f'`. Pass an explicit dest argument to preserve the old behavior. (Contributed by Serhiy Storchaka in gh-138697.)
- Padding of input no longer required in `base64.urlsafe_b64decode()`. Pass a new argument `padded=True` or use `base64.b64decode()` with argument `altchars=b'-_'` (this works with older Python versions) to make padding required. (Contributed by Serhiy Storchaka in gh-73613.)
- Since `unittest.TestCase.assertWarns()` and `unittest.TestCase.assertWarnsRegex()` no longer swallow warnings that do not match the specified category or regex, your tests may start leaking some warnings that were previously masked. Use warning filters to silence them or additional `assertWarns*()` to catch and check them. (Contributed by Serhiy Storchaka in gh-143231.)

## Notable changes in 3.15.2

### importlib

- Threads that simultaneously perform first-time `import package.submodule` imports no longer risk a deadlock or spurious import errors, a regression introduced in 3.15.0 by the fix for gh-83065. A package’s import lock is now released as soon as its `__init__` returns. `importlib.import_module()` now returns the partially initialized module in a circular import split across threads, as the `import` statement already did, instead of raising `_DeadlockError`. (Contributed by Gregory P. Smith in gh-159963.)

### ssl

- The `ssl` module now rejects TLS certificate chains that contain one of a set of compromised eMudhra intermediate CA certificates. The affected certificates are identified by their public key, so cross-signed copies that reuse the same key are blocked as well. It is a defense-in-depth backstop that applies even when an application supplies its own root CA bundle, and regardless of whether the platform trust store has removed trust. (Contributed by Christian Heimes in gh-160040 for CVE 2026-115557.)
