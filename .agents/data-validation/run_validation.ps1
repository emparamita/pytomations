# Usage: .\run_validation.ps1 [-CondaEnv base] [-EnvFile .env]   (run from workspace root)
param([string]$CondaEnv = "base", [string]$EnvFile = ".env")
$ErrorActionPreference = "Stop"
conda run -n $CondaEnv --no-capture-output python "$PSScriptRoot\validate_data.py" --env $EnvFile
exit $LASTEXITCODE
