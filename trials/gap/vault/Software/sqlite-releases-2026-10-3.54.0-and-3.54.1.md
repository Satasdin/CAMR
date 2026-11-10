---
source: https://sqlite.org/changes.html
fetched: 2026-11-10
published: 2026-10-09 to 2026-10-16
title: SQLite Release History — releases 3.54.0 and 3.54.1 (October 2026)
---

# Release History Of SQLite (releases dated October 2026)

### 2026-10-16 (3.54.1)

1. Fix a possible heap-buffer overflow on 32-bit builds. (64-bit builds are not affected by this problem.)
2. Fixes other problems in 3.54.0 reported by users. See the check-in timeline for details.
  Hashes:
3. SQLITE_SOURCE_ID: 2026-10-16 14:45:20 555e07ef33f69a0957d24d8e555b702464a131d6f1607f4c3c1e4551e8e6ca76
4. SHA3-256 for sqlite3.c: e2b869d3003b33c942b7dd7063604fbc53553e1b66609570df39b9b7b558ee81

### 2026-10-09 (3.54.0)

1. CLI enhancements:
  a. CLI prompt strings may contain escape sequences that expand to show state information. The initial CLI prompt is now be initialized the values of the SQLITE_PS1 and SQLITE_PS2 environment variables, if those variables exist.
  b. The default CLI prompt has been enhanced to take advantage of the new escape sequences described in the previous.
  c. For columnar output modes, the CLI now shows the column name header by default even if the query returns no rows.
  d. Use the new diskused() extension to implement the ".diskused" dot-command. The replaces the separate sqlite3_analyzer utility program, which is now deprecated.
  e. On unix, the CLI preserves zero bytes when outputing unformatted BLOB values.
  f. Enhance the .mode command with new options "--rowcount on" and "--titles always". The "--titles always" is now the default behavior (see item 3a above). Legacy behavior can be restored using "-titles on".
  g. Enhance the .mode command with the new --ifmt option and --fpfmt option that allow the rendering of integer and floating-point values to be more precisely controlled using a printf-style format string.
  h. The -csv command-line option automatically disables display limits, for legacy compatibility.
  i. The default CLI prompt honors the NO_COLOR environment variable.
  j. The ability to end an SQL command using the line that contains just "go" or "/" (for compatibility with SQL Server and Oracle, respectively) is discontinued, unless the CLI is compiled with option -DSQLITE_SHELL_LEGACY_COMMAND_TERMINATOR.
2. Query planner improvements:
  a. When doing an UPDATE on a table that has expression indexes, do not change the expression index if the value being indexed is unchanged.
  b. Improved optimization of "expr OR TRUE" and "expr OR FALSE".
  c. Ignore DISTINCT in the SELECT statement on the right-hand side of an IN operator.
  d. UNION queries with a LIMIT of exactly 1 are now handled faster and with less memory.
3. The ALTER TABLE command raises an error on any attempt to add, drop, or rename columns with the special names "ROWID", "_ROWID_", or "OID".
4. Add the diskused() SQL function as an optional extension.
5. Added the %J and %j conversions used to render JSON string literals to the built-in printf() and the format() SQL function.
6. Add the sqlite3_result_str() interface and use it internally to simplify the code.
7. Add the sqlite3_incomplete() interface and use it as part of the newly enhanced CLI prompt string management.
8. Enhancements to date/time functions:
  a. Added the "weekday -N" form of the weekday modifier.
  b. Added the end of modifier.
9. Use O_TMPFILE when generating temporary files, on systems that support that feature.
10. Drop support for WindowsXP and earlier Windows versions, including WindowsCE. SQLite for Windows now requires Windows Vista (circa 2007) or later.
  a. Improve performance by using Slim Reader/Writer Locks (SRWLs) to implement non-recursive mutexes, instead of CriticalSection, since all supported Windows platforms now provide SRWLs.
  b. Use the -DSQLITE_UWP=1 compile-time option for UWP and WebUI applications.
  c. To be clear: This changes above only affects SQLite on Windows. Builds for Linux, Mac, BSD, and other unix variants are unaffected.
11. The authorizer callback is now invoked for SQL functions found in the DEFAULT clauses of CREATE TABLE statements. This happens both when the CREATE TABLE statement is first issued and when the DEFAULT value is actually used, but not when reading the schema while opening a database.
12. Added SQLITE_LIMIT_SCHEMA and SQLITE_LIMIT_TRIGGER_STEPS to the sqlite3_limit() interface.
13. About 4% faster, as measured by counting CPU cycles in the speedtest1 preformance benchmark using valgrind on Linux x64. About 7.5% faster compared to one year ago (version 3.51.0). Your mileage may vary depending on workload, build options, CPU, compiler, and operating system.
  Hashes:
14. SQLITE_SOURCE_ID: 2026-10-09 15:46:58 be8d059e9a49089ab2dce5ed26dd87aaf598fdc5fbe0b107c0dd758464bcd5e3
15. SHA3-256 for sqlite3.c: 8efd453d08a7cfc4c79de5923153036cdc4dcaa254d4f1e617be6a2a98828f9e
