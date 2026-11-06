from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents" / "data-validation"))
import validate_data


def test_load_config_accepts_python_oracledb_connection(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ORACLE_CONNECTION_MODE=oracledb\n"
        "ORACLE_DBAPI_DSN=127.0.0.1:1521/FREEPDB1\n"
        "ORACLE_USER=local_app\n"
        "ORACLE_PASSWORD=local-test-password\n"
        "ORACLE_TABLE=GAS_BILLING_DETAIL\n"
        "DAT_FILE_PATH=sample.dat\n",
        encoding="utf-8",
    )

    cfg = validate_data.load_config(str(env_file))

    assert cfg["connection_mode"] == "oracledb"
    assert cfg["dbapi_dsn"] == "127.0.0.1:1521/FREEPDB1"
    assert cfg["user"] == "local_app"
    assert cfg["pwd"] == "local-test-password"


def test_kind_of_recognizes_oracledb_database_types() -> None:
    oracledb = pytest.importorskip("oracledb")

    assert validate_data.kind_of(oracledb.DB_TYPE_NUMBER) == "num"
    assert validate_data.kind_of(oracledb.DB_TYPE_DATE) == "date"
