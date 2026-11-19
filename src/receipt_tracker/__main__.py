"""Allows `python -m receipt_tracker` as an alternative to the `receipts` command."""

from receipt_tracker.cli import app

app(prog_name="receipts")
