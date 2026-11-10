---
source: https://sqlite.org/changes.html
fetched: 2026-11-10
published: 2026-01-09 to 2026-07-24
title: SQLite Release History — releases 3.51.2, 3.52.0, 3.51.3 and 3.53.0 to 3.53.4 (January to July 2026)
---

# Release History Of SQLite (releases dated January to July 2026)

### 2026-07-24 (3.53.4)

1. Fixes for problems in 3.53.0 (and 3.53.1, 3.53.2, and 3.53.3) mostly coming from AIs. See the check-in timeline for details.
  Hashes:
2. SQLITE_SOURCE_ID: 2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc
3. SHA3-256 for sqlite3.c: 67f423e9ebbbdc473cbc4772c872ee6b89f31fde4ed0279a5c25d5f65c043a16

### 2026-06-26 (3.53.3)

1. Fixes for problems in 3.53.0 (and 3.53.1 and 3.53.2) mostly coming from AIs. See the check-in timeline for details.
  Hashes:
2. SQLITE_SOURCE_ID: 2026-06-26 20:14:12 d4c0e51e4aeb96955b99185ab9cde75c339e2c29c3f3f12428d364a10d782c62
3. SHA3-256 for sqlite3.c: 28e484abdaa43630e34040ef6ed92be973a1ad54107803d8af5145b889c23ed7

### 2026-06-03 (3.53.2)

1. Fixes for problems in 3.53.0 reported by users. See the check-in timeline for details.
  Hashes:
2. SQLITE_SOURCE_ID: 2026-06-03 19:12:13 d6e03d8c777cfa2d35e3b60d8ec3e0187f3e9f99d8e2ee9cac695fd6fcdf1a24
3. SHA3-256 for sqlite3.c: 44fd61b9f93b4155105cb2d80c957ae6c64a8b5bd6ed51a4992f0dbd438e4e11

### 2026-05-05 (3.53.1)

1. Fixes for problems in 3.53.1 reported by users. See the check-in timeline for details.
  Hashes:
2. SQLITE_SOURCE_ID: 2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9
3. SHA3-256 for sqlite3.c: 414432ae5719f6cdc485f3927e12c7ad107e2b8c6b434e5df2eadb5312bfabb5

### 2026-04-09 (3.53.0)

1. Fix the WAL-reset database corruption bug.
2. Add the Query Result Formatter (QRF) library for formatting the results of SQL queries for human readability on a fixed-pitch font screen.
  a. Add the format method to the TCL Interface so that QRF is accessible from TCL.
  b. QRF is used for result formatting in the CLI, resulting in improved display capabilities.
3. New SQL language features:
  a. Enhance ALTER TABLE to permit adding and removing NOT NULL and CHECK constraints.
  b. The REINDEX EXPRESSIONS statement rebuilds expression indexes. (Useful to repair stale expression indexes.)
  c. The body of TEMP triggers may now modify and/or query tables in the main schema.
  d. Enhance VACUUM INTO so that if a URI filename is used as the target and that filename has a reserve=N query parameter with N between 0 and 255, then the reserve amount for the generated database copy is set to N.
4. New SQL functions:
  a. json_array_insert()
  b. jsonb_array_insert()
5. Renovations to the CLI:
  a. Major enhancements to the .mode command.
  b. Improved result formatting, due to the addition of the QRF extension. For example, numeric values are now right-justified by default in tabular output modes.
  c. The default output mode for interactive CLI sessions now uses QRF to display query results in boxes formed using Unicode box-drawing characters, for improved legibility. Batch CLI sessions use the legacy output format for compatibility.
  d. Bare (unquoted) semicolons at the end of dot-commands are silently ignored.  ← Potential incompatibility!
  e. Fix the .testcase and .check commands so that they actually work, and use those commands in scripts that are part of the standard SQLite test suite included with the source tree.
  f. Command-line arguments that match *.sql or *.txt and are the names of non-empty files are read and interpreted as scripts of SQL statements and/or dot-commands.
  g. The argument to the ".timer" command can now be "once", to run the timer on only the next SQL statement.
  h. The new "--timeout S" option to the ".progress" dot-command causes SQL statements to interrupt after S seconds.
  i. The ".indexes" command was changed so that the PATTERN argument matches the name of the index, not the name of the table being indexed (thus making the PATTERN argument actually useful). And, several new options were added to ".indexes".
6. New C-language interfaces:
  a. sqlite3_str_truncate()
  b. sqlite3_str_free()
  c. sqlite3_carray_bind_v2()
  d. Add the SQLITE_PREPARE_FROM_DDL option to sqlite3_prepare_v3() which permits virtual table implementations to safely prepare SQL statements that are derived from the database schema.
  e. Added the SQLITE_UTF8_ZT constant which can be used as the encoding parameter to sqlite3_result_text64() or sqlite3_bind_text64() to indicate that the value is UTF-8 encoded and zero terminated.
  f. The SQLITE_LIMIT_PARSER_DEPTH option is added to sqlite3_limit().
  g. The SQLITE_DBCONFIG_FP_DIGITS option is added to sqlite3_db_config(). See also item 9b below.
7. Query planner improvements:
  a. Always use a sort-and-merge algorithm for EXCEPT, INTERSECT, and UNION, since this is almost always faster than using a hash table.
  b. Improvements to join order selection in large multi-way joins on a star schema.
  c. Enhance the EXISTS-to-JOIN optimization so that the inserted JOIN terms are not required to be on the inner-most loops, as long as all dependencies for the EXISTS-to-JOIN loops are in outer loops.
  d. Enhance the omit-noop-join optimization so that it is able to omit a chain of joins that do not affect the output.
  e. Allow queries that use "GROUP BY e1 ORDER BY e2" where e1 and e2 are identical apart from ASC/DESC sort-orders to be optimized using a single index.
  f. Allow virtual tables to optimize DISTINCT in cases where the result-set of a query does not exactly match the ORDER BY clause.
8. Add new interfaces to the session extension that enable an application to add changes one at a time to the sqlite3_changegroup object:
  a. sqlite3changegroup_change_begin()
  b. sqlite3changegroup_change_blob()
  c. sqlite3changegroup_change_double()
  d. sqlite3changegroup_change_int64()
  e. sqlite3changegroup_change_null()
  f. sqlite3changegroup_change_text()
  g. sqlite3changegroup_change_finish()
  h. sqlite3changegroup_config()
9. Improvements to floating-point ↔ text conversions.
  a. Reimplemented to improve performance.
  b. Rounding is now done by default to 17 significant digits, instead of 15, as was the case for all prior versions. The sqlite3_db_config(SQLITE_DBCONFIG_FP_DIGITS) API (item 6g above) can change this, if desired.
10. Added the self-healing index feature to deal with the stale expression index problem.
11. Add the "-p|--port" option to sqlite3_rsync.
12. Discontinue support for Windows RT.
13. JavaScript/WASM
  a. Add the "opfs-wl" VFS, functionally identical to the "opfs" VFS but using Web Locks for locking, which can promise fairer lock sharing than the "opfs" bespoke protocol can. "opfs-wl" requires `Atomics.waitAsync()`, so requires newer browsers than "opfs" does.
Hashes:
SQLITE_SOURCE_ID: 2026-04-09 11:41:38 4525003a53a7fc63ca75c59b22c79608659ca12f0131f52c18637f829977f20b
SHA3-256 for sqlite3.c: bb317fbbd2b3bc53233ddd5894bf4d2dc6f533445f350d4235dbcc86f65af4ec

### 2026-03-13 (3.51.3)

1. Fix the WAL-reset database corruption bug.
2. Other minor bug fixes.
3. SQLITE_SOURCE_ID: 2026-03-13 10:38:09 737ae4a34738ffa0c3ff7f9bb18df914dd1cad163f28fd6b6e114a344fe6d618
4. SHA3-256 for sqlite3.c: 32d5424f97e0a7fc5ed2f6335afbb58be4e0298bd7117a34e39d345ff13d859e

### 2026-03-06 (3.52.0)

Withdrawn
All of the features that were originally scheduled for the 3.52.0 release have been moved forward into version 3.53.0.

### 2026-01-09 (3.51.2)

1. Fix an obscure deadlock in the new broken-posix-lock detection logic in item 17 above.
2. Fix multiple problems in the EXISTS-to-JOIN optimization that was added as part of optimization item 6b above.
3. Other minor bug fixes.
4. SQLITE_SOURCE_ID: 2026-01-09 17:27:48 b270f8339eb13b504d0b2ba154ebca966b7dde08e40c3ed7d559749818cb2075
5. SHA3-256 for sqlite3.c: 733b3fcc6cccb1e334424b9b91a9d68b618385b76ebfcbb106690bd3a9e61367
