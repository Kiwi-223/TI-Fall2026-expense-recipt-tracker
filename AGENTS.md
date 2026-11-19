# AGENTS.md

> **Cold start: debugging a symptom?** Go straight to **"Debugging a symptom (start here)"**
> below. The rest of this file is reference. If you're a Claude Code session, `CLAUDE.md`
> already imports this whole file.

This is onboarding for anyone, human or AI agent, who opens this repo with no prior context.
**Keep it accurate:** every PR that changes setup, commands, layout, configuration or where
data lives updates this file in the same PR.

## What this is

**Expense & Receipt Tracker:** a local, offline-first Python CLI. It turns receipt photos
and PDFs into structured, de-duplicated rows in a local SQLite ledger. Parsing goes through
a pluggable OCR provider: an offline **mock** (the default, needs no keys) or **Azure AI
Document Intelligence** (`prebuilt-receipt`). Later milestones add historical exchange
rates, bank-feed matching and a desktop UI.

- **The plan:** [docs/implementation-plan.md](docs/implementation-plan.md) is the source of
  truth for architecture, schema, milestones (M0–M10) and the agent-readiness requirements
  (RQ0–RQ7, §13).
- **The brief:** [README.md](README.md) (TI Fall 2026 project prompt #3).
- **The acceptance test:** a fresh agent gets a planted bug and a one-line symptom. It must
  name the root cause, back it with **evidence the system recorded**, and write a failing
  test. This file exists to make that possible.

## Project status: what exists today

The repo is in the **planning phase**. Most of what this file describes is **planned**, and
each item is tagged with the milestone that builds it. When a milestone lands, its PR
removes the tag here.

| Piece | Status |
|---|---|
| Implementation plan, README, `.gitignore`, this file, `CLAUDE.md` | **Exists** |
| `main` protection (GitHub ruleset "Protect main") | **Exists** (see Workflow rules) |
| `pyproject.toml`, `Makefile`, `.env.example`, CI, `.claude/settings.json`, `AI_NOTES.md` | Planned, **M0** |
| `models.py`, `failures.py`, OCR interface + mock provider, first fixture | Planned, **M1** |
| SQLite migrations + `db.py` | Planned, **M2** |
| Azure adapter | Planned, **M3** |
| More fixtures, Tesseract adapter | Planned, **M4** |
| `receipts import` with dedup + audit log | Planned, **M5** |
| `list` / `show` / `edit` / `delete` / `export` | Planned, **M6** |
| Request records + `make records` | Planned, **M7** |
| Fault injection, invariants, `make scenario`, `make reset-local` | Planned, **M8** |
| MCP server (`receipts` tools) | Planned, **M9** |
| Cold-agent rehearsal | Planned, **M10** |

**If a command below fails with "No rule to make target" or "No module named …", check
this table before debugging: the piece may not exist yet.**

## Debugging a symptom (start here)

You've been handed a one-line symptom, and possibly a bug someone planted. For example:

- *"I imported the same receipt twice and now it shows up twice in my list."*
- *"My grocery receipt was $12.34 but the ledger says $1,234.00."*
- *"The import timed out, and now when I retry it says 'already imported' but the receipt
  isn't in my list."*

**Goal:** name the root cause, back it with evidence the system recorded, and write a
failing test. Follow these steps in order. Every command runs from the repo root.

**0. Set up** (once): `make install` (see Setup).

**1. Read the symptom.** Note the command involved (`import`, `edit`, `export`, …), the
file or receipt, and what was expected vs what was seen.

**2. Look for a planted change first.** The bug may be uncommitted.
```sh
git status --short && git diff --stat     # uncommitted changes (a planted bug often lives here)
git log --oneline -5                      # or a recent commit
```
Every request record also carries `git_sha` and `git_dirty_paths`: which files differed
from `HEAD` when that command ran. Note them, but **don't conclude from reading the diff
alone**. Steps 3–5 get the evidence.

**3. Run the test suite: the fastest signal.**
```sh
make test ARGS="-q"              # or the MCP tool run_tests (asks first)
```
Run it **without `-x`** and read the **whole list** of `FAILED …` lines. The most specific
failing test (`test_reimport_is_a_noop`, `test_failed_import_can_be_retried`, …) names the
cause, while broad ones (soaks, "every fault keeps the invariants") fail as a side effect
of almost any bug. A green suite doesn't clear the code, so carry on.

**4. Reproduce on an isolated ledger.** *(M8)* A fresh checkout has no records, so make
some:
```sh
make scenario                    # lists the scenarios
make scenario NAME=reimport      # import a fixture twice; expect one receipt
make scenario NAME=faults        # every OCR fault, then a clean retry of each file
make scenario NAME=all           # everything
```
- Each run uses the **working-tree code** against its own ledger and records in
  `data/scenarios/<name>/`. Your live `ledger.db` and `data/records.jsonl` are never
  touched. A previous run is moved to `data/scenarios/<name>.<timestamp>/`.
- Every step states what it expected and prints **`UNEXPECTED`** with expected vs actual
  when it didn't happen. It also prints invariant violations and the commands to query the
  evidence. It exits 1 if anything is off.
- Request ids in scenarios are stable (`scn-<name>-<n>`), so re-runs are comparable.
- Faults are forced per step, so a re-run makes the same failures happen again.

**5. Query the evidence.** Use the MCP tools first (pass `scenario="<name>"` to read a
scenario run, or omit it for live data). The CLI is the fallback.

| Question | MCP tool *(M9)* | CLI *(M7)* |
|---|---|---|
| What failed recently? | `recent_failures`, `failure_counts` | `make records ARGS="recent-failures"` / `ARGS="failure-counts --since 1h"` |
| Everything one command decided | `request_trace(request_id=…)` | `make records ARGS="request <id>"` |
| What happened to this receipt? | `receipt_history(receipt_id=…)` | `make records ARGS="receipt <id>"` |
| What happened to this file? | `receipt_history(sha256=…)` | `make records ARGS="file <sha256>"` (`shasum -a 256 <file>` gives the hash) |
| What's in the ledger now? | `receipt_state(receipt_id=…)` | `sqlite3 ledger.db "select * from receipts where id=…"` |
| Is the ledger consistent? | `check_invariants` | `python -m receipt_tracker.invariants --ledger ledger.db` |

Add `--file data/scenarios/<name>/records.jsonl` (and `--ledger data/scenarios/<name>/ledger.db`)
to the CLI to read a scenario run.

**6. Locate the bad code path** from the record's `decisions` (in order) and snapshots:

| What the record shows | Where to look |
|---|---|
| `dedup new` on a file whose `sha256` is already in `documents` | The dedup lookup in the import path (wrong column, hash of the path instead of the bytes, …) |
| `dedup duplicate`, but `receipts` has no row for that document | A `documents` row was written outside the success transaction, or a failed import didn't roll back (invariant: no document without a receipt) |
| `ocr ok`, and `parsed.total` is right but `receipt_after.total` is wrong | Normalisation or storage of money (`Decimal` → string, cents vs units) |
| `parsed.total` already wrong | The provider's mapping (`ocr/<provider>.py`) or the fixture |
| `db_write rolled_back` with an `exception` | The insert helpers in `db.py`; the message names the column |
| `failure_kind` is `null` on a failed outcome, or a raw SDK error | An adapter didn't translate an error into `OcrError(kind)` |
| An `audit_log` row with no matching `request_id` in the records | The command didn't write its record, or wrote a different id |

**7. Write a failing test** that reproduces it through the real command and checks the
persisted state *and* the record. Template (`tests/test_<symptom>.py`):
```python
def test_reimporting_the_same_file_is_a_noop(run_cli, ledger, read_records, fixture):
    first = run_cli("import", fixture("sample1.jpg"))
    second = run_cli("import", fixture("sample1.jpg"))
    assert first.exit_code == 0 and second.exit_code == 0
    assert ledger.count("receipts") == 1                     # what's on disk
    assert ledger.count("documents") == 1
    rec = read_records(request_id=second.request_id)         # what the system recorded
    assert rec["outcome"] == "skipped_duplicate"
```
The fixtures (`run_cli`, `ledger`, `read_records`, `fixture`) live in `tests/conftest.py`
*(M1/M5/M7)*. Every test gets its own temp ledger and records file. To force an OCR fault:
`monkeypatch.setenv("OCR_FAULT", "timeout")`. The test must **fail** on the buggy code, for
the reason you found.

**8. Fix it and confirm:** your test passes, then `make test` (everything), then
`make scenario NAME=all` (no `UNEXPECTED`, exit 0).

## Setup

Requires **Python 3.12+**, `git` and `make`. Windows contributors can use WSL or run the
`pip`/`pytest` commands that the Makefile wraps.

```sh
git clone https://github.com/Kiwi-223/TI-Fall2026-expense-recipt-tracker.git
cd TI-Fall2026-expense-recipt-tracker
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
make install                       # pip install -e ".[dev]"   (M0)
cp .env.example .env               # defaults to OCR_PROVIDER=mock
make test                          # all tests pass offline
make help                          # lists every target
```

- Dependencies live in `pyproject.toml`: runtime deps in `[project.dependencies]`, and
  `pytest`, `ruff` and `mcp` under the `dev` extra.
- `.venv/`, `.env`, `*.db`, `data/` and `receipts/` are git-ignored.
- **Don't trust memory for library APIs or versions** (the Azure SDK especially). Check
  `pip index versions <pkg>`, the installed package source, or `--help`.

## Run

The CLI is `receipts` (installed by `make install`). `make import FILE=…` is a shortcut.

```sh
receipts import tests/fixtures/receipts/sample1.jpg   # (M5) parse + store; prints the receipt
receipts import tests/fixtures/receipts/sample1.jpg   # again: "already imported", exit 0
receipts list                                         # (M6)
receipts show <receipt_id>                            # (M6)
receipts edit <receipt_id> --total 12.34              # (M6) writes audit_log + a record
receipts delete <receipt_id>                          # (M6)
receipts export --format csv > out.csv                # (M6) or --format json
receipts <command> --json                             # machine-readable output, incl. errors
```

Every command exits **0** on success (including "already imported") and **non-zero** on
failure. It prints the failure kind, and with `--json` the error is
`{"error": {"kind": "<id>", "message": "…"}, "request_id": "…"}`.

### Configuration (environment variables)

Read from `.env` (via `python-dotenv`) or the environment.

| Variable | Default | Meaning |
|---|---|---|
| `OCR_PROVIDER` | `mock` | `mock` \| `azure` (later `tesseract`) |
| `LEDGER_PATH` | `./ledger.db` | The SQLite ledger |
| `RECORDS_PATH` | `./data/records.jsonl` | Request records (append-only) |
| `OCR_FAULT` | empty | Mock only: `timeout` \| `auth_failed` \| `rate_limited` \| `unavailable` \| `bad_response` \| `low_confidence` \| `random` |
| `OCR_FAULT_SEED` | empty | With `OCR_FAULT=random`: the same seed gives the same sequence of faults |
| `IMPORT_FAULT` | empty | Tests/scenarios only: `crash_before_commit` |
| `AZURE_DOCINTEL_ENDPOINT`, `AZURE_DOCINTEL_KEY` | empty | Only for `OCR_PROVIDER=azure`. **Agents must never read or print these.** |

## Test

```sh
make test                         # the whole suite, offline, mock provider (M0)
make test ARGS="-k reimport -x"   # pass pytest options through ARGS
make lint                         # ruff check + format check
```

- Tests never hit the network. Real-provider tests map **recorded** responses
  (`tests/fixtures/receipts/<provider>_*_response.json`).
- Every test gets its own temp ledger and records file, so tests never touch your live data.
- The suite covers the failure paths: every `FailureKind` is triggered by a real command
  (`test_failure_kinds.py`), and every OCR fault leaves the ledger consistent
  (`test_faults.py`). See the plan's §11 for the must-have tests.

## CI

*(M0)* GitHub Actions (`.github/workflows/ci.yml`) runs `make lint` and `make test` with
`OCR_PROVIDER=mock` on every PR and every push to `main`. It needs no secrets, so it also
works on PRs from forks.

## Where data lives

| What | Where | Notes |
|---|---|---|
| **Ledger** | `ledger.db` (`LEDGER_PATH`) | SQLite. Holds receipts, so it is **personal financial data**. Git-ignored. Never commit it, paste it or send it anywhere. |
| **Request records** | `data/records.jsonl` (`RECORDS_PATH`) | One JSON line per command. Append-only, survives restarts. Git-ignored. |
| **Scenario runs** | `data/scenarios/<name>/` | Each run's own ledger + records, plus `steps.json` and `summary.json`. Earlier runs kept as `<name>.<timestamp>/`. |
| **Backups** | `local-backups/<timestamp>/` | Written by `make reset-local`. Git-ignored. |
| **Personal receipts** | `receipts/` | Git-ignored. **Agents must not read this folder.** Use `tests/fixtures/receipts/`. |
| **Test fixtures** | `tests/fixtures/receipts/` | Committed, scrubbed of personal data (card digits, names, addresses). |

**To reset local state:** `make reset-local` *(M8)* moves the ledger and `data/` into
`local-backups/<timestamp>/` and **deletes nothing**. `make reset-local DRY_RUN=1` shows
what it would move. Undo by moving the files back.

## Database schema

The full table is in the plan's §7. Summary:

- `schema_migrations(version, applied_at)`: which numbered SQL files in
  `src/receipt_tracker/migrations/` have run. **Never edit a merged migration**; add a new
  numbered file.
- `documents(id, sha256 UNIQUE, filename, imported_at)`: one row per **successfully**
  imported file. The SHA-256 of the file's bytes is the idempotency key.
- `receipts(id, document_id, merchant, transaction_date, total, subtotal, tax, currency,
  provider, confidence, raw_json)`.
- `line_items(id, receipt_id, description, quantity, unit_price, amount)`.
- `audit_log(id, request_id, entity, entity_id, action, before_json, after_json, at)`:
  every ledger change. `request_id` joins to the request records.

**Money** is `Decimal` in code and an exact decimal **string** in the DB (`"12.34"`),
never a float. **Dates** are ISO `YYYY-MM-DD`.

### Invariants *(M8, `invariants.py`)*

- **I1:** every `receipts` row has exactly one `documents` row, and the other way round.
- **I2:** no `documents` row exists for a file whose last import failed, so a retry is
  never wrongly skipped.
- **I3:** every ledger change has an `audit_log` row whose `request_id` matches a record.
- **I4:** money columns parse as exact decimals; no `line_items` row references a missing
  receipt.

## How an import works

`hash file (SHA-256)` → `dedup check` → `OcrProvider.parse()` → **one transaction**
(`documents` + `receipts` + `line_items` + `audit_log`) → **append the request record**.

- The OCR call happens **before** any write. A failure writes nothing to the ledger.
- The `documents` row is written **only** in the success transaction (invariant I2).
- The request record is written for **every** outcome: imported, skipped_duplicate or
  failed.

## OCR providers & fault injection

- `ocr/base.py` *(M1)*: the `OcrProvider` protocol (`parse(path) -> ParsedReceipt`) and
  `OcrError(kind)`. Adapters must translate every SDK/HTTP error into an `OcrError` with a
  `FailureKind`. A raw SDK exception escaping is a bug.
- `ocr/mock.py` *(M1)*: returns `tests/fixtures/receipts/<name>.json` for `<name>.jpg`, with
  no network. **Fault injection** *(M8)*: `OCR_FAULT=<fault>` forces one fault, and
  `OCR_FAULT=random` + `OCR_FAULT_SEED=<n>` gives a reproducible sequence. A fixture JSON can
  pin a fault to one file with `"fault": "timeout"`.
- `ocr/azure.py` *(M3)*: Azure AI Document Intelligence, `prebuilt-receipt`. Agents don't
  call it (the sandbox blocks its endpoint; see Agent boundaries).
- **Adding a provider:** see the plan's §5. You need a recorded response fixture, a
  mapping test and a `FailureKind` for each of its errors.

## Request records

*(M7)* `records.py` appends one JSON object per command to `RECORDS_PATH`:

| Field | Example / meaning |
|---|---|
| `request_id` | uuid, or `scn-<name>-<n>` in scenarios |
| `command`, `args` | `import`, `{"file": "…/sample1.jpg"}` |
| `started_at`, `ended_at` | ISO timestamps (UTC) |
| `git_sha`, `git_dirty_paths` | which code ran |
| `file` | `{"path", "sha256", "size"}` |
| `provider`, `fault` | `mock`, `timeout` (the injected fault, if any) |
| `decisions` | ordered `{step, outcome, details}`: `hash ok`, `dedup new`, `ocr failed(ocr_timeout)`, `db_write rolled_back`, … |
| `parsed` | the `ParsedReceipt` the provider returned (for imports) |
| `receipt_before`, `receipt_after` | snapshots for edits and deletes, plus `receipt_after` for imports |
| `outcome` | `imported` \| `skipped_duplicate` \| `updated` \| `deleted` \| `exported` \| `failed` |
| `failure_kind` | a stable id (below), or `null` |
| `exception` | `{type, message}` when something raised |
| `receipt_id`, `document_id` | to follow one receipt end-to-end |

The records CLI is `make records ARGS="<subcommand>"` (or `python -m
receipt_tracker.records_query`). Subcommands: `recent`, `recent-failures`,
`failure-counts --since 1h`, `request <id>`, `receipt <id>`, `file <sha256>`. Add `--json`
for machine-readable output, and `--file`/`--ledger` to read a scenario run.

## Failure kinds

*(M1)* `failures.py` defines `FailureKind`: the **fixed** set of ways a command can fail.
Each has a stable string id. **Once an id ships, it's never renamed or reused.** A new failure
mode gets a new id plus a test in `tests/test_failure_kinds.py` that triggers it through a
real command.

| Id | Meaning |
|---|---|
| `file_not_found` | The path doesn't exist |
| `unsupported_file_type` | Not JPG, PNG or PDF |
| `file_unreadable` | Exists but can't be read, or is corrupt |
| `ocr_not_configured` | The provider needs config that's missing (e.g. Azure endpoint/key) |
| `ocr_auth_failed` | The provider rejected the credentials |
| `ocr_timeout` | The provider didn't answer in time |
| `ocr_rate_limited` | The provider throttled us (HTTP 429) |
| `ocr_unavailable` | The provider had a server error (5xx) or the network failed |
| `ocr_bad_response` | The provider answered with something we can't map |
| `receipt_unparseable` | Parsed, but nothing usable (no total and no merchant) |
| `validation_failed` | Parsed values are invalid (negative total, bad currency code, …) |
| `receipt_not_found` | `show`/`edit`/`delete` with an unknown id |
| `db_error` | SQLite error during a write; the transaction rolled back |
| `migration_failed` | A migration couldn't be applied |
| `export_failed` | The export couldn't be written |

Later (exchange rates): `fx_rate_unavailable`, `fx_timeout`.

## Agent tools (MCP)

*(M9)* `src/receipt_tracker/mcp_server.py`, registered as the **`receipts`** server in
`.mcp.json`. It's a thin layer over the same functions the records CLI uses.

| Tool | Answers | Permission |
|---|---|---|
| `recent_failures(since?, limit?, scenario?)` | What failed recently? | allowed |
| `failure_counts(since?, scenario?)` | How many of each kind? | allowed |
| `request_trace(request_id, scenario?)` | Everything one command decided | allowed |
| `receipt_history(receipt_id? \| sha256?, scenario?)` | What happened to this receipt or file? | allowed |
| `receipt_state(receipt_id?, scenario?)` | What's in the ledger now? | allowed |
| `check_invariants(scenario?)` | Is the ledger consistent (I1–I4)? | allowed |
| `run_tests(args?)` | Runs pytest | **asks first** |

Read-only tools never write. An expected failure (bad argument, missing file) comes back
as a tool error with a message, not a crash.

## Agent boundaries

*(M0 starter config, finished in M10.)* These are enforced by the checked-in
`.claude/settings.json` and `.mcp.json`, not by good intentions. **Never run Claude Code
with `--dangerously-skip-permissions` here**; the settings set
`disableBypassPermissionsMode`. `make check-settings` validates the file.

### Blast radius: the worst a confused agent could do here

- **Destroy or corrupt a contributor's `ledger.db`:** that's their personal financial
  history, and there's no server copy.
- **Leak secrets or personal data:** `.env` (Azure keys), `receipts/`, the ledger, or
  unscrubbed fixtures, sent to a remote host or committed.
- **Spend money / quota** by calling the Azure endpoint in a loop.
- **Rewrite shared history or weaken protection:** push to `main`, force-push, or change
  the ruleset through the GitHub API.
- **Destroy uncommitted work** with `rm -rf`, `git reset --hard` or `git clean`.
- **Weaken its own guardrails** by editing `.claude/**`, `.mcp.json` or `.github/**`.

### Permissions, in short

| Rule | Commands |
|---|---|
| **Allow** | `make help/install/test/lint/records/scenario/check-settings`; read-only `git` (`status`, `diff`, `log`, `show`, `fetch`); `git push -u origin feat/…`, `fix/…`, `docs/…`; `gh pr view/list/diff/checks/create/comment`; `gh run list/view`; the read-only `receipts` MCP tools |
| **Ask** | MCP `run_tests`; editing `.claude/**`, `.github/**`, `.mcp.json`, `mcp_server.py` or an already-merged migration; `git reset --hard`, `git clean`, `git branch -D`; `gh pr merge`; any `gh api` write; any unsandboxed retry |
| **Deny** | reading `.env*`, `receipts/**`, `*.db` outside `data/scenarios/`, `~/.ssh`, `~/.aws`, `~/.config/gh`; `rm -rf`; `git push` with `--force`/`--delete`/`--mirror`/`--all` or naming `main`; `gh pr merge --admin`; `gh api` touching `rulesets`/`protection` or using `DELETE`; `gh auth *`; `gh repo delete` |

### Isolation

- **Sandbox on** (`failIfUnavailable: true`). Writes are limited to this checkout, and the
  network is limited to PyPI and GitHub. **The Azure endpoint is not allowlisted**, so
  agents work with the mock provider.
- **Branches:** every change happens on `feat/…`, `fix/…` or `docs/…` and lands through a PR.
  Long or risky agent tasks run in a git worktree (`.claude/worktrees/<name>`, git-ignored).
- **No container.** Claude Code's own file tools and the MCP server run with your user's
  access, which is why their entry points are ask rules.

### Reversibility

| What went wrong | How to undo it |
|---|---|
| A bad change on a branch | Push a fix commit. Never force-push. |
| A bad merge on `main` | `git revert <sha>` in a new PR (squash merges make it one commit). |
| A mutated local ledger or records | `make reset-local` backed them up first; move the files back from `local-backups/`. |
| A wrong ledger edit through the CLI | `audit_log` has `before_json`; restore from it. |
| A broken venv | Delete `.venv` yourself, then re-run Setup. Agents can't `rm -rf`. |

Can't be undone from here: a leaked key (rotate it in the Azure portal), personal data
pushed to GitHub (rewrite history plus contact GitHub support), and money already spent.

### Budget

- Headless runs go through `make agent TASK="…"` *(M10)*, with caps
  `BUDGET_USD=2 MAX_TURNS=40 TIMEOUT_MIN=20` by default.
- The Azure **F0** tier is free and throttles instead of billing. Contributors should not
  upgrade the resource they use for development.
- Interactive sessions have no cap from this repo; watch your own usage.

### Escalation

Agents open PRs; **a human merges** (the `gh pr merge` ask rule). Escalate to a human when
this file or the plan doesn't settle a decision, when a change touches shared contracts
(schema, `OcrProvider`, `FailureKind` ids, record fields), or before anything in the
blast-radius list.

## Repo map

Planned paths are tagged with their milestone.

| Path | What it is |
|---|---|
| `README.md` | Project brief and link to the plan |
| `docs/implementation-plan.md` | The plan: scope, requirements, schema, milestones, RQ0–RQ7 |
| `AGENTS.md` | This file. `CLAUDE.md` imports it. |
| `AI_NOTES.md` *(M0)* | Where an AI was confidently wrong and how it was caught (RQ7) |
| `pyproject.toml`, `Makefile`, `.env.example` *(M0)* | Packaging, task runner, config template |
| `.claude/settings.json`, `.mcp.json` *(M0, M9)* | Agent permissions/sandbox and MCP registration |
| `.github/workflows/ci.yml` *(M0)* | CI |
| `src/receipt_tracker/cli.py` *(M5, M6)* | The `receipts` command |
| `src/receipt_tracker/models.py` *(M1)* | `ParsedReceipt`, `LineItem` |
| `src/receipt_tracker/failures.py` *(M1)* | `FailureKind` |
| `src/receipt_tracker/ocr/` *(M1, M3, M4)* | Provider protocol, factory, mock, Azure, Tesseract |
| `src/receipt_tracker/db.py`, `migrations/` *(M2)* | Connection, migration runner, insert helpers |
| `src/receipt_tracker/records.py`, `records_query.py` *(M7)* | Request records and their CLI |
| `src/receipt_tracker/invariants.py` *(M8)* | Ledger consistency checks I1–I4 |
| `src/receipt_tracker/mcp_server.py` *(M9)* | Agent tools |
| `scripts/scenarios.py`, `scripts/reset_local.py` *(M8)* | `make scenario`, `make reset-local` |
| `tests/`, `tests/fixtures/receipts/` | Test suite and scrubbed fixtures |
| `data/`, `local-backups/`, `receipts/`, `ledger.db`, `.env` | Local only, git-ignored |

## Known behaviour worth knowing before debugging

- **OCR is imperfect by design.** Any `ParsedReceipt` field can be `None`; that's not a bug
  on its own. Fixing gaps is what `receipts edit` is for.
- **Dedup is by file bytes, not content.** A re-scan or re-saved photo of the same receipt
  has a different SHA-256 and imports as a new receipt. Content-level dedup is a possible
  later feature, not a bug.
- **`low_confidence` isn't a failure.** The receipt is imported with its `confidence`. Whether
  to flag it is an open question (plan §12).
- **Currency** is whatever the provider reports. There's no conversion until the
  exchange-rate milestone.

## Workflow rules

- **The plan is the plan.** Work on one milestone task per PR, with exactly that scope. If
  you find something else, open an issue; don't fix it on the side. If the plan changes,
  edit `docs/implementation-plan.md` in the same PR.
- **Branch** from a fresh `main`: `git checkout main && git pull`, then
  `git checkout -b feat/<slug>` (or `fix/…`, `docs/…`).
- **`main` is protected** by the "Protect main" ruleset: PRs only, no force-push, no
  deletion. One approval is requested; Write+ contributors can bypass it, but agents don't
  merge (see Escalation).
- **In each PR:** link the issue (`Closes #N`), keep this file accurate (and remove the
  milestone tag from anything that now exists), and log any confident AI mistake in
  `AI_NOTES.md`.
- **Commits** use conventional style (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- **Never commit** `.env`, `*.db`, `data/`, `receipts/` or unscrubbed receipts.
- After a failed `gh pr create`, run `gh pr list --head <branch>` before retrying, to avoid
  duplicate PRs.
