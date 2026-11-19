# TI-Fall2026-expense-recipt-tracker
OCR/receipt-parsing API with local database

This is a community project based off of this project prompt:
3. Expense & Receipt Matcher with Local Ledger
APIs: Exchange-rate API, OCR/document-parsing API, or banking/transaction feed API (or mock/sandbox feed).

Client Architecture: A local desktop client writing to a local SQLite or DuckDB ledger with an import/reconciliation workflow.

What You Practice:

Idempotency keys and deduplication when re-importing transactions or retrying failed API calls.

Currency conversion with historical exchange rates tied to transaction dates.

Schema migrations, audit logs, and exportable reports (CSV/JSON) generated locally.

## Getting started

See the [implementation plan](docs/implementation-plan.md) for the architecture, contributor setup, and milestones you can pick up.

Using an AI agent, or new to the repo? Read [AGENTS.md](AGENTS.md): setup, commands, where data lives, how to debug, and the agent's boundaries.
