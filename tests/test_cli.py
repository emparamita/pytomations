import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_entrypoint_displays_help() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "data_validation.py"), "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Validate Oracle data against a .dat export" in result.stdout
    assert "--check-deps" in result.stdout


def test_init_env_writes_template_outside_repository(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / ".agents/data-validation/validate_data.py"), "--init-env"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    template = tmp_path / ".env.example"
    assert template.is_file()
    assert template.stat().st_size > 0
    assert ".env.example" in result.stdout
