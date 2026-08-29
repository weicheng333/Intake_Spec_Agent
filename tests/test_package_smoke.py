from intake_spec_agent import __version__
from intake_spec_agent.__main__ import main


def test_package_exposes_version() -> None:
    assert __version__ == "1.0.0"


def test_cli_reports_version(capsys) -> None:
    assert main() == 0
    assert capsys.readouterr().out == "Intake & Spec Agent 1.0.0\n"
