"""Entrypoint for the data-validation utility kept with its agent skill."""

from pathlib import Path
import runpy


def main() -> None:
    """Run the existing self-contained validator."""
    validator = Path(__file__).parent / ".agents" / "data-validation" / "validate_data.py"
    if validator.is_file():
        runpy.run_path(str(validator), run_name="__main__")
        return

    from pytomations_data_validation.validate_data import main as validate

    validate()


if __name__ == "__main__":
    main()
