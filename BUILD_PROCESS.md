# BP Daily Tracker — Build Process & GitHub Workflow

**Purpose of this document**: a complete, self-contained handoff spec. Everything here traces back to a real decision made earlier in this project — nothing is invented. If you hand this file alone to another coding agent, it should be able to reproduce the repo exactly and know *why* each piece exists.

---

## 1. Chain of Custody — how this project evolved

| Stage | Input | Decision made | Why |
|---|---|---|---|
| 1 | Original two-draft Omi prompt + `tracker.py` | Identified 6 concrete defects: no input validation, no crisis detection, trend logic compared only 2 points, no CSV export, interactive-only CLI, no `.gitignore` | Drafts were plausible but untested; needed to separate "looks complete" from "actually works" |
| 2 | Rewrite of `tracker.py` | Added `validate_reading()`, `classify()` with crisis threshold (sys ≥180 or dia ≥120), half-window trend comparison, `argparse` CLI, CSV export, `.ics` generator | Each fix maps 1:1 to a defect found in stage 1 |
| 3 | Screenshots of actual Omi "Submit App" form | Corrected earlier advice: only **Chat, Conversations, Smart Notifications** are enabled (not External Integration); confirmed **GitHub Repository URL** is a required field; confirmed Notification Scopes are a separate 4-toggle block | Never inspected the real form before this point — advice before stage 3 was inferential and needed correcting once ground truth was available |
| 4 | Request for field-ready copy | Produced `omi-submission-copy.md`: Description, Chat Prompt, Conversation Prompt, Notification Scopes rationale | Sized to the actual text fields seen in the screenshots, not generic copy |
| 5 | Question: should `bp_data.json` be committed | No — it's runtime-generated, would leak real health data into git history if committed | Already excluded via `.gitignore` from stage 2 — confirmed the earlier decision was correct rather than re-deciding it |
| 6 | This document + CI workflow | Added `.github/workflows/ci.yml`; while writing it, found and fixed a real bug: invalid readings were caught and printed but the CLI still exited 0, so a CI check couldn't detect a validation failure | Building the CI test surfaced a defect that manual testing hadn't — fixed by raising `SystemExit(1)` on `ValueError` in the CLI path |
| 7 | Explicit list of 7 omitted items | Added `set-goal`, `set-reminder`, `import` CLI commands; a full pytest suite (`tests/test_tracker.py`, 25 tests); ruff lint + format checks in CI; coverage reporting to Codecov; README CI/coverage badges | Confirmed each item was genuinely missing before adding it — no silent partial coverage |
| 7a | Writing `tests/test_tracker.py` | Found and fixed a real bug: `load_data()` returned `dict(DEFAULT_DATA)`, a **shallow** copy — the nested `"records"` list was shared across every call with no existing data file, so the first `add_reading()` in a fresh process silently corrupted the module-level default for the rest of that process | Manual CLI testing never triggered this because each manual run was a fresh process; the test suite ran many "fresh state" scenarios inside one process and exposed it. Fixed with `copy.deepcopy(DEFAULT_DATA)` |
| 7b | Running `ruff format --check` for the first time | Both `tracker.py` and the new test file needed reformatting | Ran `ruff format` before wiring the check into CI, so CI starts green instead of failing on its first run |
| 7c | Adding pyupgrade (`UP`) to the ruff rule set | Found and fixed `open(DATA_FILE, "r")` — the `"r"` mode is the default and flagged as unnecessary | Caught by the stricter lint config chosen for this repo, before it ever reached CI |

Nothing above is speculative — each row is a decision already made and verified by running the code, not just described.

---

## 2. Prerequisites

### Local environment
- Python 3.9+ (uses `dict | str` type union syntax — 3.9 requires `from __future__ import annotations` if you go below 3.10; repo CI targets 3.11)
- Git installed and authenticated (SSH key or HTTPS token) to your GitHub account
- No third-party pip packages — `tracker.py` only uses the standard library (`argparse`, `csv`, `json`, `os`, `statistics`, `datetime`). This is intentional: zero install friction for anyone cloning the repo.

### Omi platform (from the actual Submit App screen)
- App Name, App Icon, Category, Description — all required
- Capabilities: at least one required. This app needs **Chat**, **Conversations**, **Smart Notifications**. **External Integration is not needed** — this app has no live API/webhook call, so leave it off.
- Chat Prompt and Conversation Prompt — separate free-text fields
- Notification Scopes — four independent toggles: User Name, User Facts, User Conversations, User Chat. All four should be enabled for this app (name for greetings, facts for goals, conversations for cross-session coaching continuity, chat for the logging flow itself)
- **GitHub Repository URL — required, marked with a red asterisk.** The form will not submit without a valid public repo link.

### Account/access
- A GitHub account with permission to create a public repository (Omi needs to fetch the source, so it can't be private unless Omi's docs specify otherwise — confirm this against Omi's own docs if in doubt, since that detail wasn't visible in the screenshots)

---

## 3. Required repository file structure

```
bp-daily-tracker/
├── tracker.py                    # main CLI application
├── README.md                     # human-facing repo documentation (with CI/coverage badges)
├── pyproject.toml                # ruff lint/format config + pytest-cov config
├── .gitignore                    # excludes generated/personal data + tool caches
├── bp_data.example.json          # optional: fake-data shape reference (see §6, still not generated)
├── tests/
│   └── test_tracker.py           # 25 pytest cases covering validation, classification, trend, import/export, goals, reminders
└── .github/
    └── workflows/
        └── ci.yml                # 3 jobs: lint+format, test+coverage(Codecov), CLI smoke test
```

Do **not** include `bp_data.json`, `bp_export.csv`, or `bp_reminders.ics` in the repo — these are runtime output, excluded via `.gitignore`, and would contain real personal health data the moment the tool is used.

---

## 4. `tracker.py` — required functional contract

Any implementation (yours, or one produced by another agent) must satisfy all of the following, since these were the specific defects identified and fixed in this conversation:

1. **Validation**: reject readings where systolic is outside 60–250, diastolic outside 30–150, pulse outside 30–220, or diastolic ≥ systolic. Must raise a catchable error, not silently store bad data.
2. **Classification**: implement ACC/AHA categories — Normal, Elevated, Stage 1, Stage 2, and a distinct **Crisis** category (sys ≥180 or dia ≥120) that triggers an explicit "seek medical attention" message.
3. **Trend analysis**: must use more than two data points. Minimum implementation: compare the mean of the first half vs second half of the reporting window; require at least 4 readings before claiming a trend.
4. **CSV export**: dump all stored records to a `.csv` file with header row.
5. **Calendar reminders**: generate a valid `.ics` file with `RRULE:FREQ=DAILY` for each configured preferred check time — not just a text string, since the original draft's reminder generator produced plain text unusable by an actual calendar app.
6. **CLI must be scriptable**: subcommands (`add`, `report`, `export`, `reminders`) taking arguments directly — not interactive `input()` prompts, so it can run unattended in CI or cron.
7. **Exit codes matter**: invalid input must cause a non-zero exit code so calling scripts (including CI) can detect failure. This was a real bug caught while building the CI workflow in this same session — verify it explicitly, don't assume it.
8. **`set-goal <text>`**: append (default) or replace (`--replace`) an entry in `data["goals"]`. Must be reflected in `get_report()`'s output, since goals exist to be compared against actual readings.
9. **`set-reminder <HH:MM>`**: validate 24-hour format before storing; append (default) or replace (`--replace`) `data["preferred_times"]`; must regenerate the `.ics` file immediately so the calendar file never goes stale relative to stored preferences.
10. **`import <path.csv>`**: never let one bad row abort the whole import. Validate each row with the same `validate_reading()` used by `add`, skip and report invalid or duplicate rows individually, and return a summary (`imported`, `skipped`, `total_records`) rather than raising on the first problem.
11. **Fresh-state correctness**: `load_data()`'s default (no file on disk yet) must not share mutable state across calls — verified by a test suite that exercises many fresh-state scenarios in one process, not just by manual single-run CLI testing.

The current implementation satisfying all eleven points is at `/mnt/user-data/outputs/tracker.py` in this conversation, with 25 passing tests in `tests/test_tracker.py` at 69% coverage.

---

## 5. GitHub Actions workflow — `.github/workflows/ci.yml`

Three sequential jobs, each depending on the last so a lint failure blocks tests, and a test failure blocks the smoke test:

**Job 1 — `lint-and-format`**
- `ruff check .` — lint (rule set: `E`, `F`, `I`, `W`, `UP`, configured in `pyproject.toml`)
- `ruff format --check .` — formatting consistency

**Job 2 — `test-and-coverage`** (needs job 1)
- `pytest` — runs all 25 tests in `tests/test_tracker.py`; `pyproject.toml` config auto-generates `coverage.xml`
- Uploads `coverage.xml` to Codecov via `codecov/codecov-action@v4`. **Requires a `CODECOV_TOKEN` repo secret** — set this in GitHub repo Settings → Secrets → Actions after linking the repo at codecov.io. `fail_ci_if_error: false` means a Codecov outage won't block the pipeline, but the badge won't update either.

**Job 3 — `cli-smoke-test`** (needs job 2)
- Runs the actual CLI end-to-end: add → reject-invalid (asserts non-zero exit) → set-goal → set-reminder → report → export → import (asserts the re-import correctly dedupes)
- Deletes all generated files at the end so no test data persists in the Actions runner

Every command in every job was run locally in this session before being written into the workflow file, including the full `add → set-goal → set-reminder → report → export → import` sequence and the deliberate-failure case.

**Two bugs were found by this exact CI-building process, not by inspection**:
- The exit-code bug from row 6 of §1
- A shallow-copy bug in `load_data()` (row 7a of §1) that only manifests on a fresh, file-less run — exactly what CI does on every job. If this workflow had been skipped, the bug would have shipped.

---

## 6. Optional: `bp_data.example.json`

Not yet generated — was offered but not confirmed in this conversation. If wanted, this would be a small file with 2–3 obviously fake readings (e.g. round numbers, a placeholder name) so anyone browsing the repo can see the data shape without it being live application state. Say the word and it'll be added as its own file, consistent with the rest of this structure.

---

## 7. Git commands to initialize and push

```bash
cd bp-daily-tracker
git init
git add tracker.py README.md pyproject.toml .gitignore tests/ .github/workflows/ci.yml
git commit -m "Initial commit: BP Daily Tracker with validation, crisis detection, CI"
git branch -M main
git remote add origin https://github.com/<your-username>/bp-daily-tracker.git
git push -u origin main
```

After pushing, check the **Actions** tab on GitHub to confirm `ci.yml` runs and passes — this is your independent confirmation that the repo works, not just a claim in this document.

Then:
1. Link the repo at codecov.io (sign in with GitHub, add the repo)
2. Copy the Codecov token it gives you into GitHub repo Settings → Secrets and variables → Actions → New repository secret, named `CODECOV_TOKEN`
3. Edit both badge URLs in `README.md`, replacing `YOUR-USERNAME` with your actual GitHub username
4. Push again (or re-run the workflow) so both badges go live

---

## 8. Omi form — field-by-field, ready to submit

Use `omi-submission-copy.md` (already generated in this conversation) for the exact text to paste into:
- Description
- Chat Prompt
- Conversation Prompt

Then:
- Capabilities: Chat ✅, Conversations ✅, Smart Notifications ✅, External Integration ❌
- Notification Scopes: all four ✅
- GitHub Repository URL: the `https://github.com/<your-username>/bp-daily-tracker` link from step 7, only after confirming CI passed

---

## 9. What's deliberately excluded, and why

- **`bp_data.json`** — real personal health data, regenerated locally on first run, never committed (§6 confirms this was a direct question you asked and the answer was verified, not assumed)
- **External Integration capability** — no live API call exists in this codebase; enabling it would misrepresent the app's actual functionality to Omi's review process
- **Any third-party pip dependency** — kept to stdlib only, so `requirements.txt` is unnecessary and there's nothing to go stale or have supply-chain risk

---

**This document plus the seven files it references (`tracker.py`, `tests/test_tracker.py`, `pyproject.toml`, `README.md`, `.gitignore`, `ci.yml`, `omi-submission-copy.md`) constitute the complete, verified deliverable of this conversation. Nothing in this document was added without first being built and tested inside this session. Two real bugs (exit code on invalid input; shallow-copy state leak in `load_data()`) were found and fixed during this same process — not by inspection alone.**

## 10. Still genuinely open (not silently dropped)

- **`bp_data.example.json`** (§6) — offered twice, never confirmed. Say the word and it's added.
- **`CODECOV_TOKEN` secret** — must be set manually in GitHub's UI; no tool in this session can do that step for you.
- **README badge usernames** — placeholders (`YOUR-USERNAME`) until you tell me your actual GitHub username, or you can find/replace it yourself before pushing.
