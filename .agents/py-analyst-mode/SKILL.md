---
name: py-analyst-mode
description: Guides writing and changing Python analysis code (pandas, SQL, notebooks, scripts) for data analysts with correct results and minimal token use. Use when the user runs /py-analyst-mode, or asks to build, fix, refactor, or review data analysis code.
---

# py-analyst-mode

Every change follows: Make it Work, then Make it Right, then Practice.

## Token Budget (always)

- Never print or read whole DataFrames or files. Use `df.shape`, `df.dtypes`, `df.head(3)`, `df.describe()`, `nunique()`, `isna().sum()`.
- Read only needed columns/rows (`usecols`, `nrows`, SQL `LIMIT`). Prefer parquet over CSV.
- Run helper scripts with `--help` first. Do not read their source.
- Output summaries, not raw data. Send bulk output to a file; keep only the path and a 1-line result.
- Edit in place with the smallest diff. Do not rewrite files or restate unchanged code.
- Reply in short bullets. No preamble, no recap.

## 1. Make it Work

### Data shape first
- Inspect schema and sample before writing logic.
- State grain in one line: "one row = one X".
- Fix dtypes at load (dates, categoricals, ints). Parse once, at the boundary.

### Smallest edit
- One decision lives in one place (one constant, one function).
- Subtract before you add: delete unused columns, steps, and imports first.

### Test first (pytest)
- Write a failing test on a tiny fixture (5-10 rows), confirm it fails for the expected reason.
- Make the smallest change to pass.
- If an honest test is impractical (plots, exploration), assert shape/invariants instead. Do not write a fake test.

### Accuracy guards
- Assert after every join: row count, key uniqueness (`validate="one_to_one"` etc.).
- Check nulls, duplicates, and units before aggregating.
- Never silently `dropna`/`fillna`. State the rule used.
- Set seeds for sampling and models. Pin the data snapshot/date.
- Reconcile totals: aggregate result must equal source total.

### Structure
- Pure functions: `load()` (I/O) -> `clean()` -> `transform()` -> `report()`. Keep logic out of I/O.
- No hardcoded paths or credentials. Use config/env.
- Idempotent: rerunning, or rerunning after a crash, gives the same output (overwrite outputs, never append blindly).
- Prefer vectorized ops. No row loops or `apply` where a vector op exists.
- Keep a short glossary of domain terms (metric definitions) in `GLOSSARY.md`.

## 2. Make it Right

- Fix root causes: reproduce on a minimal sample, fix the cause. A `try/except` or `fillna` that hides the bad data is not a fix.
- Work in small verifiable units. Finish and check one before the next.
- Test behavior, not implementation: call the function as a user would and check the output. If it passes when the function returns nothing, delete it.
- Complexity: if available, `radon cc -nB .`; split functions rated above B (CC > 10).
- Duplication: if available, `pylint --disable=all --enable=duplicate-code .`; merge repeated logic.
- Mutation: if available, `mutmut run`; kill survivors, delete dead code.
- Skip a tool silently if not installed. Do not install without asking.
- Refactor: pin current output (snapshot/test), change structure, prove output unchanged.

## 3. Practice

- Keep a log: one line per action with reason. Report it at the end.
- Keep the main thread small: delegate bulk work to scripts or subagents, keep only summaries.
- Notebooks: restart and run all before finishing. Strip outputs before commit.
- Commit often and small. Message: why, what, how verified.
- Uncommitted or unknown files: ask before deleting.

## Decision Tree

- New analysis -> inspect schema -> write test on fixture -> implement -> reconcile totals.
- Wrong number -> reproduce on sample -> check joins/nulls/dtypes -> fix cause -> add test.
- Slow code -> profile first -> vectorize/filter early/use parquet -> compare output to old.
- Messy code -> pin output -> split functions -> rerun tests.
