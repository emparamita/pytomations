---
name: dumps-generator
description: Generate deterministic, large synthetic CSV, JSON, XML, and pipe-delimited DAT files with 120–150 columns for exercising the data-validation project.
---

# Dumps generator

Use the repository's dependency-free `scripts/generate_dumps.py` script. It
streams rows to disk, overwrites the selected output file, and never accesses a
database or external service.

## Command

```sh
python scripts/generate_dumps.py CSV
python scripts/generate_dumps.py JSON --rows 100000 --columns 140 --seed 23
python scripts/generate_dumps.py XML --output test-data/sample.xml
python scripts/generate_dumps.py DAT --output data/export_20261103.dat
```

The positional file type is case-insensitive: `CSV`, `JSON`, `XML`, or `DAT`.
Defaults are 10,000 rows, 135 columns, seed 42, and `test-data/generated.<type>`
in the current workspace. Columns must be between 120 and 150 inclusive.
The output directory is created if needed; an existing output file is
overwritten. Set `--rows` deliberately to control disk use.

All formats contain the same generated schema and values. `record_id` is the
first, unique, non-null column; `customer_code`, `event_date`, `amount`, and
`status` provide representative string, date, decimal, and categorical fields.
Remaining columns are named `attribute_NNN` and cycle through those types.
Nullable values are empty CSV/DAT fields, JSON `null`, and empty XML elements.
The default 2% null rate applies to non-key fields. A fixed seed and options
produce identical contents.

DAT output uses the pipe (`|`) delimiter and includes a header, matching the
validation project's `.env.example` defaults. For a validator configuration
with a different DAT separator, pass `--dat-separator` (or `TAB`) and set the
same `DAT_SEPARATOR` value in the validator's `.env`. DAT output always
includes the header.

Run `python scripts/generate_dumps.py --help` for the complete option list.
One row represents one synthetic validation record.
