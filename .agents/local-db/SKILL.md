---
name: local-db
description: Start a local Oracle Database Free container, execute a SQL script against it, or seed a table for data-validation project tests.
---

# Local Oracle database

This project uses Oracle Database Free in Docker for local Oracle SQL and schema
compatibility. These commands target only the local container and loopback
address. They do not connect to production, read production credentials, or
change the validation project's `.env`.

## One-time setup

Install Docker Desktop or Docker Engine with Compose. Copy
`.agents/local-db/.local-db.env.example` to `.local-db.env` at the repository
root, then set a strong local-only password. Keep `.local-db.env` private; it is
ignored by Git. The first start downloads the Oracle Free image and initializes
a persistent Docker volume.

The local app user defaults to `local_app`; both the System and app passwords
must be changed from the example placeholders before starting.

The validator's Oracle connection is controlled independently by `.env`.
Configure its ODBC DSN or connection string with the local app username,
password, and `127.0.0.1:1521/FREEPDB1`; this may require Oracle Instant Client
and an Oracle ODBC driver on the host. To use a production database later, the
user must deliberately replace the `ORACLE_*` settings in `.env`; neither
skill edits or discovers production URLs.

## `/local-db start`

After creating `.local-db.env`, optionally inspect the start action without
touching Docker:

```sh
python .agents/local-db/local_db.py start --dry-run
```

Then start the database:

```sh
python .agents/local-db/local_db.py start
```

This starts the `oracle` Compose service in the background. Its host port is
bound only to `127.0.0.1:1521`; the PDB service is `FREEPDB1`. Check readiness
with `python .agents/local-db/local_db.py status`. Stop it with
`docker compose --env-file .local-db.env --file .agents/local-db/compose.yaml stop oracle`.
Database files remain in the named volume across stops and restarts.

## `/local-db execute_script`

Pass a workspace SQL file explicitly:

```sh
python .agents/local-db/local_db.py execute_script path/to/schema.sql
```

The helper feeds the script to SQL*Plus inside the local container, connects
to the `FREEPDB1` PDB using the local app account, and returns a nonzero
exit code on SQL errors. Review scripts before execution. This is for local
development SQL only; never supply a production schema or credentials.

## `/local-db seed_data <table>`

For an existing table in the local app user's schema:

```sh
python .agents/local-db/local_db.py seed_data CUSTOMER --rows 1000
```

Seeding uses `LOCAL_DB_USER` / `LOCAL_DB_PASSWORD` from `.local-db.env` and
the local `LOCAL_DB_DSN` only. Install the agent-only driver with
`python -m pip install -r .agents/local-db/requirements.txt`. The helper
inspects the table's columns, skips identity/defaulted columns, inserts
generated values according to supported Oracle column types in one
transaction, and rolls back on error.
Unsupported types or constraints that reject the generated values are reported;
the helper does not disable constraints or silently skip rows. Use a disposable
test table and review the row count before running.

See `python .agents/local-db/local_db.py --help` and each subcommand's `--help` for
options. Use `--dry-run` to inspect start, script, and seed operations without
accessing Docker or Oracle. No database is started or seeded unless the
matching subcommand is invoked explicitly.
