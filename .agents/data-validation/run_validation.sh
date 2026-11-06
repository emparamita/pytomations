#!/usr/bin/env bash
# macOS/Linux equivalent of run_validation.ps1
# Usage (from workspace root): ./run_validation.sh [conda_env=base] [env_file=.env]
# Prereqs (macOS): brew install unixodbc ; Oracle Instant Client + ODBC driver registered in odbcinst.ini / odbc.ini
set -euo pipefail
CONDA_ENV="${1:-base}"
ENV_FILE="${2:-.env}"
exec conda run -n "$CONDA_ENV" --no-capture-output data-validation --env "$ENV_FILE"
