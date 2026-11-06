import csv
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / ".agents" / "dumps-generator" / "generate_dumps.py"


@pytest.mark.parametrize("file_type", ["CSV", "JSON", "XML", "DAT"])
def test_generated_formats_have_reusable_125_column_schema(tmp_path: Path, file_type: str) -> None:
    output = tmp_path / f"sample.{file_type.lower()}"
    result = subprocess.run(
        [
            sys.executable, str(GENERATOR), file_type, "--rows", "7",
            "--columns", "125", "--seed", "19", "--output", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "7 rows and 125 columns" in result.stdout

    if file_type == "CSV":
        with output.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows[0]) == 125
        assert len(rows) == 7
        assert rows[0]["record_id"] == "1"
        assert len({row["record_id"] for row in rows}) == 7
    elif file_type == "DAT":
        with output.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="|"))
        assert len(rows[0]) == 125
        assert len(rows) == 7
        assert rows[0]["record_id"] == "1"
        assert len({row["record_id"] for row in rows}) == 7
    elif file_type == "JSON":
        rows = json.loads(output.read_text(encoding="utf-8"))
        assert len(rows) == 7
        assert len(rows[0]) == 125
        assert rows[0]["record_id"] == 1
        assert len({row["record_id"] for row in rows}) == 7
        assert any(value is None for value in rows[0].values())
    else:
        root = ET.parse(output).getroot()
        rows = root.findall("row")
        assert len(rows) == 7
        assert len(rows[0]) == 125
        assert rows[0].findtext("record_id") == "1"
        assert len({row.findtext("record_id") for row in rows}) == 7


def test_generator_is_reproducible(tmp_path: Path) -> None:
    outputs = [tmp_path / "first.json", tmp_path / "second.json"]
    for output in outputs:
        subprocess.run(
            [
                sys.executable, str(GENERATOR), "json", "--rows", "12",
                "--columns", "120", "--seed", "42", "--null-rate", "0",
                "--output", str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    assert outputs[0].read_bytes() == outputs[1].read_bytes()


def test_generator_rejects_columns_outside_supported_range(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "CSV", "--columns", "119", "--output", str(tmp_path / "bad.csv")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "--columns must be between 120 and 150" in result.stderr
    assert not (tmp_path / "bad.csv").exists()


def test_local_db_cli_describes_commands_without_starting_database() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / ".agents" / "local-db" / "local_db.py"), "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert all(command in result.stdout for command in ("start", "execute_script", "seed_data"))
