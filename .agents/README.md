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

Seeding synthetic data is optional. Its Oracle driver is deliberately separate
from the user's project dependencies:

```sh
python -m pip install -r .agents/local-db/requirements.txt
python .agents/local-db/local_db.py seed_data CUSTOMER --rows 1000
```

To run the validator against this database, install an Oracle ODBC driver on
the host and configure the user's `.env` with the local app username,
password, and `127.0.0.1:1521/FREEPDB1`. This is a separate configuration from
`.local-db.env`, which is used only by the local database tooling. Use
synthetic input files and never production credentials or data in these checks.

## Agent skills and synthetic exports

- `data-validation/SKILL.md` describes how agents work with the installed
  user-facing validator.
- `dumps-generator/SKILL.md` documents the deterministic test-data generator:

  ```sh
  python .agents/dumps-generator/generate_dumps.py DAT --rows 10
  ```

- `local-db/SKILL.md` documents local Oracle lifecycle, SQL script execution,
  and optional synthetic table seeding.
- `py-analyst-mode/SKILL.md` provides general Python data-analysis guidance.

Generated test files default to `test-data/generated.*`, which is ignored by
Git. Do not commit generated data, local database files, or credentials.
