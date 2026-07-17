# BP Daily Tracker

[![CI](https://github.com/YOUR-USERNAME/bp-daily-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR-USERNAME/bp-daily-tracker/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YOUR-USERNAME/bp-daily-tracker/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR-USERNAME/bp-daily-tracker)

> Replace `YOUR-USERNAME` in both badge URLs above with your actual GitHub username once the repo is pushed — badges won't resolve until then.

Personal blood pressure logging tool with validation, trend analysis, and calendar reminders. Built to pair with an Omi prompt-based app, but works standalone.

**Not medical advice — consult a doctor for personalized care.**

## Features
- Input validation (rejects physiologically implausible readings)
- ACC/AHA classification, including a hypertensive crisis flag
- Real trend analysis: first-half vs second-half average over a window, not just point-to-point
- CSV export and safe CSV import (validates, dedupes, and reports skipped rows — never crashes on a bad row)
- `.ics` calendar file generation for daily check reminders, regenerated automatically when reminder times change
- Goal tracking (`set-goal`), reflected in every trend report
- Scriptable CLI (no interactive prompts required — works in cron jobs, CI, etc.)
- CI: ruff lint + format checks, pytest with coverage reporting to Codecov, and a full CLI smoke test on every push

## Usage

```bash
# Add a reading
python tracker.py add 122 89 82 --notes "after walking"

# 7-day trend report (default)
python tracker.py report --days 30

# Export all records to CSV
python tracker.py export

# Import readings from a CSV file (validates + dedupes automatically)
python tracker.py import readings.csv

# Set or add a goal (use --replace to overwrite instead of append)
python tracker.py set-goal "Keep average BP under 125/80"

# Add or update a preferred daily check-in time (regenerates the .ics file)
python tracker.py set-reminder 07:30

# Generate calendar reminder file directly
python tracker.py reminders
```

## Development

```bash
pip install ruff pytest pytest-cov

ruff check .            # lint
ruff format --check .   # formatting
pytest                  # tests + coverage (config in pyproject.toml)
```

## Data
Stored in `bp_data.json` in the working directory. Back this file up or gitignore it if the repo is public — it's personal health data.

## Omi Integration
Use this as the backend memory source; feed the `report` JSON output into the Omi conversation prompt so it can reference real averages/trends instead of hallucinating them.
