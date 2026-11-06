# Oracle data validation

This installable Python project compares an Oracle query or table with a
delimited `.dat` or CSV export and writes an Excel report. Configure it for
your own database and files; it does not require AI-agent skills, Docker, or a
local development database.

## Set up your workspace

Requires Python 3.10 or later. Create and activate a virtual environment, then
install the project:

```sh
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
```

`pyodbc` also requires an ODBC driver manager and an Oracle ODBC driver
installed for your platform.

Create a configuration template in your workspace and copy it to `.env`:

```sh
data-validation --init-env
cp .env.example .env
```

On Windows, copy `.env.example` to `.env` using File Explorer or PowerShell.
Set your Oracle connection, SELECT/WITH query or table, input path, and any
matching options in `.env`. For a comma-separated CSV, set `DAT_SEPARATOR=,`;
the default delimiter for DAT exports is `|`. Keep real credentials only in
your ignored local `.env` file and never commit it.

## Run a validation

```sh
data-validation --help
data-validation --check-deps
data-validation
```

The report workbook and `validation.log` are written under
`reports/<YYYY-MM-DD>/`. Exit codes are `0` for a match, `1` for differences,
and `2` for an error. The same CLI is available as
`python data_validation.py` when working from this source checkout.

## AI-agent development

Agent skills, synthetic data generation, and local Oracle Docker tooling are
development-only and are not part of the installed Python project. See the
[agent developer guide](.agents/README.md) for running and validating those
tools.
