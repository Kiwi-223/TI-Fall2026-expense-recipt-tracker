"""The `receipts` command-line interface.

M0 only sets up the command structure. Each command is filled in by a later milestone:
`import` in M5, and `list` / `show` / `edit` / `export` in M6.
"""

from pathlib import Path
from typing import Annotated

import typer

from receipt_tracker import __version__

app = typer.Typer(
    help="Import receipts into a local expense ledger.",
    no_args_is_help=True,
)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"receipts {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Import receipts into a local expense ledger."""


@app.command("import")
def import_receipt(
    file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Receipt image (JPG/PNG) or PDF to import.",
        ),
    ],
) -> None:
    """Import a receipt file into the ledger."""
    typer.echo("`receipts import` is not implemented yet (milestone M5).", err=True)
    raise typer.Exit(code=1)
