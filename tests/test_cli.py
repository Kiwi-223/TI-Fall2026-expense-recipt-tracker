from typer.testing import CliRunner

from receipt_tracker import __version__
from receipt_tracker.cli import app

runner = CliRunner()


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_import_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "import" in result.output


def test_import_rejects_missing_file(tmp_path):
    result = runner.invoke(app, ["import", str(tmp_path / "missing.jpg")])
    assert result.exit_code != 0


def test_import_is_a_placeholder_until_m5(tmp_path):
    receipt = tmp_path / "receipt.jpg"
    receipt.write_bytes(b"not really an image")
    result = runner.invoke(app, ["import", str(receipt)])
    assert result.exit_code == 1
