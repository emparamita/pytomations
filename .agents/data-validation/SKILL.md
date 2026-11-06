---
name: data-validation
description: Validates daily project data by comparing an Oracle (ODBC) extract against an exported .dat file and generating a colour-coded xlsx report. Use when asked to create, configure, extend or troubleshoot DB-vs-DAT data validation, reconciliation, or the daily validation scripts and .env settings.
---

# Data Validation Skill

Oracle DB = source of truth. This skill helps an agent create, configure, or
troubleshoot the user-facing Python project, which runs independently of any
agent or LLM. The validator and its dependencies live in the installable
`pytomations_data_validation` package, not in this skill directory.

## Files
- `pytomations_data_validation/validate_data.py` - user-facing validator.
- `pytomations_data_validation/.env.example` - user configuration template.
- `README.md` - installation, `.env`, and run instructions for users.
- `run_validation.ps1` / `run_validation.sh` - optional conda wrappers for the installed CLI.

## Workflow
1. Follow the root `README.md` to install the project and create `.env.example`; do not ask users to configure agent-only files.
2. Keep user connection values and input/output paths in the user's project `.env`. Never create or fill `.env` with real credentials; ensure it is git-ignored.
3. Use `data-validation --check-deps` to diagnose project dependencies. The project's `--install-deps` option remains available when explicitly requested.
4. If validation behavior must change, modify the installable package and its tests, not this skill or the local database tools.
5. Hand over the exact setup and CLI steps from the root `README.md`.

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
