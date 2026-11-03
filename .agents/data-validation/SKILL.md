---
name: data-validation
description: Validates daily project data by comparing an Oracle (ODBC) extract against an exported .dat file and generating a colour-coded xlsx report. Use when asked to create, configure, extend or troubleshoot DB-vs-DAT data validation, reconciliation, or the daily validation scripts and .env settings.
---

# Data Validation Skill

Oracle DB = source of truth. Compares all fields/rows to a `.dat` export. The script runs later on another machine **without an agent or LLM**, so everything is `.env`-driven and self-contained.

## Files
- `scripts/validate_data.py` - the validator. Black box: run `--help`, don't read the source unless changing it.
- `scripts/run_validation.ps1` - PowerShell wrapper (Windows, conda).
- `scripts/run_validation.sh` - bash wrapper (macOS/Linux; needs `brew install unixodbc` + Oracle Instant Client ODBC driver).
- `scripts/requirements.txt` - pip fallback.
- `resources/.env.example` - config template.

## Workflow
1. Copy `resources/.env.example` to the workspace root as `.env.example` (or `python scripts/validate_data.py --init-env`). Never create or fill `.env` with real credentials; ensure `.env` is in `.gitignore`.
2. Check deps: `python scripts/validate_data.py --check-deps`. If missing, `--install-deps` (tries `conda install` first, then `pip`).
3. Adapt `validate_data.py` only if the user needs new rules; keep all settings in `.env`.
4. Hand over: tell the user to copy `.env.example` to `.env`, fill values, then run `.\.agents\skills\data-validation\scripts\run_validation.ps1` from the workspace root (or `python ...\validate_data.py`).

## Decision tree
- `KEY_COLUMNS` set (comma-separated) -> match rows by key (duplicates paired by occurrence order). Empty -> match by row position (set `ORACLE_ORDER_BY`/ORDER BY for stable order).
- DAT has leading `exported_date` -> dropped via `DAT_IGNORE_COLUMNS` (only if not a DB column).
- Separator not `|` -> set `DAT_SEPARATOR` (`\t` supported).
- Column names differ -> structural failure, report still produced with `NOT_COMPARED`. Only order differs -> reordered, warning logged.

## Comparison rules (normalized)
Trim whitespace; NULL = empty; numeric DB columns compared as decimals (`1.0` = `1`); date DB columns parsed via `DATE_FORMATS`; text case-sensitive unless `CASE_INSENSITIVE=true`. String columns keep leading zeros.

## Output
`reports/<YYYY-MM-DD>/data_validation_<HHMMSS>.xlsx` + `validation.log`. Tabs: **DAT_Data** (1st), **DB_Data** (2nd), **Summary**.
Colours: red row + dark-red cells = value mismatch; orange = row in DB missing from DAT; yellow = extra row in DAT; grey = not compared.
Exit codes: `0` match, `1` differences, `2` error.

## Safety
- SELECT/WITH queries only. Never print or log credentials.
- Data stays local; no network calls besides the DB (and package install on request).
