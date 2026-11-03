# AGENTS.md — Python data analysis

Order for every change: Make it Work, then Make it Right, then Practice.

## Token budget
- Never print or read whole DataFrames/files. Use `shape`, `dtypes`, `head(3)`, `describe()`, `nunique()`, `isna().sum()`.
- Load only needed columns/rows (`usecols`, `nrows`, SQL `LIMIT`). Prefer parquet over CSV.
- Run helper scripts with `--help`. Do not read their source.
- Send bulk output to a file; report only the path and a one-line result.
- Smallest diff. Do not rewrite files or restate unchanged code.
- Reply in short bullets. No preamble, no recap.

## 1. Make it Work
- Inspect schema and a sample first. State the grain: "one row = one X".
- Set dtypes at load. Parse once, at the boundary.
- One decision lives in one place. Remove unused columns, steps, imports before adding.
- Write a failing pytest on a 5-10 row fixture first. Confirm it fails for the expected reason, then make the smallest change to pass. If a test is impractical (plots, exploration), assert shape/invariants instead.
- After every join assert row count and key uniqueness (`validate=`).
- Check nulls, duplicates, units before aggregating. Never silently `dropna`/`fillna`; state the rule.
- Set seeds. Pin the data snapshot/date.
- Reconcile: aggregated totals must equal source totals.
- Structure: `load()` (I/O) -> `clean()` -> `transform()` -> `report()`. Keep logic pure and out of I/O.
- No hardcoded paths or credentials. Use config/env.
- Idempotent: rerun or rerun-after-crash gives the same output. Overwrite outputs; do not append blindly.
- Vectorize. No row loops or `apply` where a vector op exists.
- Keep metric definitions in `GLOSSARY.md`.

## 2. Make it Right
- Fix root causes: reproduce on a minimal sample, then fix. Guards that hide bad data are not fixes.
- Work in small units. Verify one before starting the next.
- Test behavior, not implementation. Delete a test that passes when the function returns nothing.
- If installed, run: `radon cc -nB .` (split functions above CC 10), `pylint --disable=all --enable=duplicate-code .`, `mutmut run` (kill survivors, delete dead code). Skip silently if missing; do not install without asking.
- Refactor: pin current output, change structure, prove output unchanged.

## 3. Practice
- Log each action with its reason in one line. Report the log at the end.
- Keep the main thread small: push bulk work to scripts or subagents; keep summaries.
- Notebooks: restart and run all before finishing; strip outputs before commit.
- Commit small and often. Message states why, what, how verified.
- Ask before deleting uncommitted or unknown files.

## Decision tree
- New analysis: schema -> fixture test -> implement -> reconcile totals.
- Wrong number: reproduce on sample -> check joins/nulls/dtypes -> fix cause -> add test.
- Slow code: profile -> filter early/vectorize/parquet -> compare output to old.
- Messy code: pin output -> split functions -> rerun tests.
