# Data validation

Compare an Oracle query result with a pipe-delimited `.dat` export and produce
an Excel report. The validator and its runtime configuration remain in
`.agents/data-validation/`; the root project provides installation metadata
and a convenient command-line entry point.

## Setup

Requires Python 3.10 or later. Install the project and its dependencies:

```sh
python -m pip install -e .
```

The dependency list is maintained in `requirements.txt` and used by the
project metadata. `pyodbc` also requires the platform's ODBC driver manager and
an Oracle ODBC driver.

Create a local `.env` from the configuration template, then edit it for your
database and input files:

```sh
python -m data_validation --init-env
```

Alternatively, copy `.agents/data-validation/.env.example` to `.env`. Never
commit real credentials; `.env` is ignored by Git.

## Run

From the repository root:

```sh
data-validation --help
data-validation --check-deps
data-validation
```

The command is also available without installing the project:

```sh
python data_validation.py --help
python .agents/data-validation/validate_data.py --help
```

The validator compares the Oracle result against the `.dat` export configured
in `.env`. Reports are written under `reports/<YYYY-MM-DD>/` with a workbook
and validation log. Exit codes are `0` for a match, `1` for differences, and
`2` for an error.

## Tests

Run the CLI smoke tests with:

```sh
python -m pytest
```

## Workspace skills

- `/local-db start|execute_script|seed_data <table>` manages a loopback-only
  Oracle Database Free container for development. See
  `.agents/local-db/SKILL.md`; Docker and a private root `.local-db.env` are
  required. Seeding uses the optional `local-db` extra.
- `/dumps-generator <CSV|JSON|XML|DAT>` creates deterministic synthetic files
  with 120–150 columns for exercising validation. See
  `.agents/dumps-generator/SKILL.md`.
