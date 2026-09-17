from pathlib import Path
import tomllib

from intake_spec_agent import __version__
from intake_spec_agent.__main__ import main
from package_manager import VERSION


def test_package_exposes_version() -> None:
    assert __version__ == "1.2.0"


def test_cli_reports_version(capsys) -> None:
    assert main() == 0
    assert capsys.readouterr().out == "Intake & Spec Agent 1.2.0\n"


def test_package_and_installer_versions_match() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert metadata["project"]["version"] == __version__ == VERSION
