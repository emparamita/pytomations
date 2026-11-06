import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from local_db import _row_value


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DB = ROOT / "scripts/local_db.py"


def run_local_db(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LOCAL_DB), *args],
        cwd=ROOT,
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
    )


def test_start_dry_run_is_local_only_and_does_not_need_docker(tmp_path: Path) -> None:
    env_file = tmp_path / ".local-db.env"
    env_file.write_text(
        "LOCAL_ORACLE_PASSWORD=local-only-password\n"
        "LOCAL_DB_USER=local_app\n"
        "LOCAL_DB_PASSWORD=local-only-password\n",
        encoding="utf-8",
    )
    result = run_local_db("--env-file", str(env_file), "start", "--dry-run")

    assert result.returncode == 0
    assert "docker compose" in result.stdout.lower()
    assert "127.0.0.1" in result.stdout
    assert "local-only-password" not in result.stdout


def test_execute_script_dry_run_requires_existing_script(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sql"
    env_file = tmp_path / ".local-db.env"
    env_file.write_text(
        "LOCAL_ORACLE_PASSWORD=local-only-password\nLOCAL_DB_PASSWORD=local-only-password\n",
        encoding="utf-8",
    )
    result = run_local_db("--env-file", str(env_file), "execute_script", str(missing), "--dry-run")

    assert result.returncode != 0
    assert "not found" in result.stderr.lower()


def test_seed_data_rejects_unsafe_table_name_without_docker(tmp_path: Path) -> None:
    env_file = tmp_path / ".local-db.env"
    env_file.write_text(
        "LOCAL_ORACLE_PASSWORD=local-only-password\nLOCAL_DB_PASSWORD=local-only-password\n",
        encoding="utf-8",
    )
    result = run_local_db(
        "--env-file", str(env_file), "seed_data", "T; DROP TABLE USERS", "--dry-run",
    )

    assert result.returncode != 0
    assert "table" in result.stderr.lower()


def test_seed_data_refuses_non_loopback_dsn(tmp_path: Path) -> None:
    env_file = tmp_path / ".local-db.env"
    env_file.write_text(
        "LOCAL_ORACLE_PASSWORD=local-only-password\n"
        "LOCAL_DB_PASSWORD=local-only-password\n"
        "LOCAL_DB_DSN=production.example.com:1521/PROD\n",
        encoding="utf-8",
    )
    result = run_local_db(
        "--env-file", str(env_file), "seed_data", "CUSTOMER", "--dry-run",
    )
    assert result.returncode != 0
    assert "local-only" in result.stderr


def test_seed_numeric_values_fit_declared_oracle_precision() -> None:
    latitude = _row_value("NUMBER", 22, 10, 7, 15000, 50)
    bill_sequence = _row_value("NUMBER", 22, 6, 0, 15000, 8)

    assert latitude.as_tuple().exponent == -7
    assert len(latitude.as_tuple().digits) <= 10
    assert bill_sequence < 1_000_000
