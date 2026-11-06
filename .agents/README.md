# Agent tooling and local validation

This directory contains development-only agent skills and scripts. It is not
part of the installable `pytomations_data_validation` Python project. Users
install and configure the validator using the root [README](../README.md);
they do not need agent skills, Docker, or this directory.

## Validate the user-facing project

Install the project in a Python environment using the root README instructions.
The installed `data-validation` CLI is the same command used by the agent skill.
For automated checks that do not need a database or Oracle driver, run:

```sh
python -m pytest
```

The CLI/package tests are under `tests/`. Tests for the agent-only dump
generator and local database helper are under `.agents/tests/`.

## Test against a local Oracle database

This is an optional agent-developer workflow for validating Oracle behavior
against synthetic local data. It never uses the user's or production
credentials. Install Docker with Compose, then make a private local database
configuration:

```sh
cp .agents/local-db/.local-db.env.example .local-db.env
```

Change both password values in `.local-db.env` before starting the container.
The file is git-ignored; do not commit it. The container publishes only
`127.0.0.1:1521` and uses the `FREEPDB1` service.

```sh
python .agents/local-db/local_db.py start
python .agents/local-db/local_db.py status
```

Apply the synthetic gas-billing schema once and seed it with synthetic rows:

```sh
python .agents/local-db/local_db.py execute_script .agents/local-db/gas_billing_schema.sql
python .agents/local-db/local_db.py seed_data GAS_BILLING_DETAIL --rows 15000
```

The schema has 146 columns, including an Oracle-generated identity key. Seeding
appends rows; rerun only when you intend to add more rows. The schema script is
for a fresh local database and should be applied once.

The local database helper's Oracle driver is deliberately separate from the
user-facing project dependencies:

```sh
python -m pip install -r .agents/local-db/requirements.txt
```

To run the validator against this database, configure the user's `.env`
separately from `.local-db.env`. The validator supports ODBC mode (which
requires an Oracle ODBC driver on the host) and the optional `oracledb` thin
driver, which can be installed with `python -m pip install -e
'.[oracle-dbapi]'`. For either mode, use the local app username, password, and
`127.0.0.1:1521/FREEPDB1`. Never use production credentials or data in these
checks.

For an end-to-end comparison, the DAT/CSV export must contain the same selected
columns, values, and row snapshot returned by the Oracle query. The dump
generator below creates generic data for testing the file-reading workflow; it
does not export or generate rows matching `GAS_BILLING_DETAIL`.

## Agent skills and synthetic exports

- `data-validation/SKILL.md` describes how agents work with the installed
  user-facing validator.
- `dumps-generator/SKILL.md` documents the deterministic test-data generator:

  ```sh
  python .agents/dumps-generator/generate_dumps.py DAT --rows 10
  ```

  The generator defaults to 10,000 rows and 135 columns (supported range:
  120-150). It writes generic synthetic records and does not create a matching
  export of the local Oracle schema.

- `local-db/SKILL.md` documents local Oracle lifecycle, SQL script execution,
  and optional synthetic table seeding.
- `py-analyst-mode/SKILL.md` provides general Python data-analysis guidance.

Generated test files default to `test-data/generated.*`, which is ignored by
Git. Do not commit generated data, local database files, or credentials.

Run the Docker-free unit and CLI checks with `python -m pytest`. Local Oracle
integration is optional; use helper `--dry-run` flags to inspect commands
without contacting Docker or Oracle.
