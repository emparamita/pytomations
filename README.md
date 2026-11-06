# Data validation

Compare an Oracle query result with a pipe-delimited `.dat` export and produce
an Excel report. The repository also includes a local Oracle Free setup and a
deterministic synthetic-file generator for testing.

## Requirements

- Python 3.10 or later.
- Docker Desktop (macOS/Windows) or Docker Engine with Compose (Linux). Start
  Docker and confirm `docker info` works before starting the database.
- For ODBC validation, an Oracle ODBC driver and its platform ODBC manager.
  The Oracle container does not install an ODBC driver on your host. For a
  local Oracle Free database, the optional `oracledb` thin-driver mode avoids
  the need to install an Oracle ODBC driver.

Create and activate a virtual environment, then install the project:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[local-db]"
```

In PowerShell, activate with `.venv\Scripts\Activate.ps1`. The `local-db` extra
installs the Oracle Python driver used by the local seeding helper. To install
only the validator dependencies, use `python -m pip install -e .`.

## Start the local Oracle database

The local database is for synthetic development data only. Its listener is
bound to `127.0.0.1:1521`; it does not connect to production. Keep the database
credentials separate from `.env` and never use production passwords here.

1. Copy the local database settings template and replace both password
   placeholders with strong, unique passwords. The helper accepts only
   letters, digits, `.`, `_`, `#`, and `-`; a password manager can generate
   values using those characters. Restrict the file permissions on macOS/Linux.

   ```sh
   cp .agents/local-db/.local-db.env.example .local-db.env
   chmod 600 .local-db.env
   ```

   Edit `.local-db.env` and set `LOCAL_ORACLE_PASSWORD` and
   `LOCAL_DB_PASSWORD`. This file is ignored by Git. `LOCAL_DB_DSN` should
   remain `127.0.0.1:1521/FREEPDB1`, and the default app username is `local_app`.

2. Make sure Docker Desktop/Engine is running, then start the Oracle Free
   container. The initial start downloads the image and initializes its
   persistent volume; it can take several minutes.

   ```sh
   docker info
   python scripts/local_db.py start
   python scripts/local_db.py status
   ```

   The status command shows container state; wait for Oracle initialization to
   finish before connecting.

3. Apply the gas billing schema and seed the table once:

   ```sh
   python scripts/local_db.py execute_script .agents/local-db/gas_billing_schema.sql
   python scripts/local_db.py seed_data GAS_BILLING_DETAIL --rows 15000
   ```

   The schema defines 146 columns, including an Oracle-generated identity key.
   The seed helper generates synthetic values and inserts 15,000 rows. Seeding
   appends rows; do not repeat the seed command on an already seeded table
   unless you intend to add another 15,000 rows. The schema script creates the
   table and is intended to be applied once to a fresh local database.

   To stop the container without deleting its data:

   ```sh
   docker compose --env-file .local-db.env --file .agents/local-db/compose.yaml stop oracle
   ```

## Configure and run validation

The validator reads `.env`, which is independent from `.local-db.env`. Copy its
template and edit the connection, query, and DAT settings:

```sh
cp .agents/data-validation/.env.example .env
```

For ODBC mode, configure `ORACLE_CONNECTION_MODE=odbc`,
`ORACLE_ODBC_DSN`, `ORACLE_USER`, and `ORACLE_PASSWORD` for a host ODBC DSN
that reaches `127.0.0.1:1521/FREEPDB1` using the `local_app` user and the
`LOCAL_DB_PASSWORD` from `.local-db.env`. Alternatively, configure
`ORACLE_ODBC_CONN_STR` with your installed Oracle ODBC driver; its `Dbq` must
point to the same local service.

For local Oracle Free without installing an ODBC driver, select the Python
thin driver instead:

```dotenv
ORACLE_CONNECTION_MODE=oracledb
ORACLE_DBAPI_DSN=127.0.0.1:1521/FREEPDB1
ORACLE_USER=local_app
ORACLE_PASSWORD=<same local-only password as LOCAL_DB_PASSWORD>
```

Install `python-oracledb` through `python -m pip install -e ".[local-db]"`.
Both modes use the same SELECT/WITH validation query and DAT comparison.
Never commit `.env` or real credentials.

Choose one `SELECT`/`WITH` query or `ORACLE_TABLE`. For example, to read the
seeded table, set `ORACLE_TABLE=GAS_BILLING_DETAIL`,
`ORACLE_ORDER_BY=BILLING_DETAIL_ID`, and `KEY_COLUMNS=BILLING_DETAIL_ID`.
`ORACLE_ORDER_BY` ensures stable ordering; the key lets the validator match
rows independent of file order.

The configured DAT file must contain the same selected columns and values as
the Oracle result. `scripts/generate_dumps.py` creates deterministic synthetic
files in CSV, JSON, XML, or pipe-delimited DAT format, but it does not insert
those records into Oracle or export the gas billing table. For example:

```sh
python scripts/generate_dumps.py DAT --rows 15000 --columns 135 --seed 42
```

This creates `test-data/generated.dat` with 135 generic columns. It is useful
for exercising the generator and file-reading behavior, but it does **not**
match the gas billing table's 146-column schema and therefore is not a valid
comparison file for `GAS_BILLING_DETAIL`. For an end-to-end comparison, point
`DAT_FILE_PATH` at a pipe-delimited export of the exact selected Oracle query,
with matching headers, values, and row snapshot. Set `DAT_SEPARATOR` to the
export's delimiter; the default is `|`.

Check dependencies and run the validator from the repository root:

```sh
data-validation --help
data-validation --check-deps
data-validation
```

Equivalent commands that do not depend on the installed entry point are:

```sh
python data_validation.py --help
python .agents/data-validation/validate_data.py --help
python .agents/data-validation/validate_data.py --check-deps
python .agents/data-validation/validate_data.py
```

Reports are written under `reports/<YYYY-MM-DD>/` with an Excel workbook and
`validation.log`. Exit code `0` means the data matched, `1` means differences
were found, and `2` means a configuration or runtime error occurred. If
`KEY_COLUMNS` is empty, comparison is by row position; ensure the Oracle query
uses a stable `ORDER BY`.

## Generate test files and run tests

The dump generator defaults to 10,000 rows and 135 columns; column counts must
be between 120 and 150. It overwrites the selected output file. Use
`--help` for all format, seed, row-count, null-rate, and delimiter options.

```sh
python scripts/generate_dumps.py --help
python scripts/generate_dumps.py DAT --rows 1000 --columns 135 --seed 42
```

Run the local unit and CLI tests with:

```sh
python -m pytest
```

These tests do not require Docker or an Oracle connection. The local database
helper's `--dry-run` options are also available for inspecting commands
without contacting Docker or Oracle. Its seed operation supports standard
Oracle character, numeric, and date types; unsupported types or violated
constraints cause an error rather than silently dropping rows.
