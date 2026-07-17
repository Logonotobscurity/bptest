"""
BP Daily Tracker — personal blood pressure logging tool.
Not a substitute for professional medical care.
"""

import argparse
import copy
import csv
import json
import os
import statistics
from datetime import datetime, timedelta

DATA_FILE = "bp_data.json"

DEFAULT_DATA = {
    "records": [],
    "goals": ["Keep average BP under 130/80"],
    "preferred_times": ["08:00", "20:00"],
}

# ---------- storage ----------


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return copy.deepcopy(DEFAULT_DATA)


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------- validation & classification ----------


def validate_reading(sys_: int, dia: int, pul: int) -> None:
    if not (60 <= sys_ <= 250):
        raise ValueError(f"Systolic {sys_} is outside a plausible range (60-250).")
    if not (30 <= dia <= 150):
        raise ValueError(f"Diastolic {dia} is outside a plausible range (30-150).")
    if not (30 <= pul <= 220):
        raise ValueError(f"Pulse {pul} is outside a plausible range (30-220).")
    if dia >= sys_:
        raise ValueError("Diastolic should not be greater than or equal to systolic.")


def classify(sys_: int, dia: int) -> str:
    """ACC/AHA categories, with a crisis flag."""
    if sys_ >= 180 or dia >= 120:
        return "HYPERTENSIVE CRISIS — seek immediate medical attention"
    if sys_ >= 140 or dia >= 90:
        return "Hypertension Stage 2"
    if sys_ >= 130 or dia >= 80:
        return "Hypertension Stage 1"
    if sys_ >= 120 and dia < 80:
        return "Elevated"
    return "Normal"


# ---------- core actions ----------


def add_reading(sys_: int, dia: int, pul: int, notes: str = "") -> dict:
    validate_reading(sys_, dia, pul)
    data = load_data()
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sys": sys_,
        "dia": dia,
        "pul": pul,
        "notes": notes,
        "classification": classify(sys_, dia),
    }
    data["records"].append(entry)
    save_data(data)
    return entry


def get_report(days: int = 7) -> dict | str:
    data = load_data()
    cutoff = datetime.now() - timedelta(days=days)
    window = [
        r for r in data["records"] if datetime.strptime(r["date"], "%Y-%m-%d %H:%M") >= cutoff
    ]
    if not window:
        return f"No readings in the last {days} day(s)."

    sys_vals = [r["sys"] for r in window]
    dia_vals = [r["dia"] for r in window]

    report = {
        "period_days": days,
        "readings_count": len(window),
        "average": {
            "sys": round(statistics.mean(sys_vals)),
            "dia": round(statistics.mean(dia_vals)),
        },
        "min": {"sys": min(sys_vals), "dia": min(dia_vals)},
        "max": {"sys": max(sys_vals), "dia": max(dia_vals)},
        "variability_sys": round(statistics.pstdev(sys_vals), 1) if len(sys_vals) > 1 else 0.0,
        "latest": window[-1],
        "goals": data["goals"],
    }

    if len(window) >= 4:
        midpoint = len(window) // 2
        first_half_avg = statistics.mean(sys_vals[:midpoint])
        second_half_avg = statistics.mean(sys_vals[midpoint:])
        diff = second_half_avg - first_half_avg
        if diff <= -3:
            report["trend"] = "Improving"
        elif diff >= 3:
            report["trend"] = "Rising — worth flagging to your doctor"
        else:
            report["trend"] = "Stable"
    else:
        report["trend"] = "Not enough data yet for a trend"

    return report


def export_csv(path: str = "bp_export.csv") -> str:
    data = load_data()
    if not data["records"]:
        return "No records to export."
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "sys", "dia", "pul", "classification", "notes"]
        )
        writer.writeheader()
        writer.writerows(data["records"])
    return f"Exported {len(data['records'])} records to {path}"


def generate_ical_reminders(out_path: str = "bp_reminders.ics") -> str:
    """Generate a simple daily-recurring .ics file for the preferred check times."""
    data = load_data()
    times = data.get("preferred_times", ["08:00", "20:00"])
    today = datetime.now().strftime("%Y%m%d")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//BP Daily Tracker//EN"]
    for i, t in enumerate(times):
        hh, mm = t.split(":")
        lines += [
            "BEGIN:VEVENT",
            f"UID:bp-reminder-{i}-{today}@bp-tracker",
            f"DTSTART:{today}T{hh}{mm}00",
            "DURATION:PT10M",
            "RRULE:FREQ=DAILY",
            "SUMMARY:BP Check",
            "DESCRIPTION:Log your blood pressure reading.",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    return f"Wrote {out_path} — import this into Google/Apple Calendar."


def set_goal(text: str, replace: bool = False) -> list:
    data = load_data()
    if replace:
        data["goals"] = [text]
    elif text not in data["goals"]:
        data["goals"].append(text)
    save_data(data)
    return data["goals"]


def set_reminder(time_str: str, replace: bool = False) -> dict:
    import re as _re

    if not _re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", time_str):
        raise ValueError(f"'{time_str}' is not a valid 24-hour HH:MM time.")
    data = load_data()
    if replace:
        data["preferred_times"] = [time_str]
    elif time_str not in data["preferred_times"]:
        data["preferred_times"].append(time_str)
    save_data(data)
    ics_result = generate_ical_reminders()
    return {"preferred_times": data["preferred_times"], "ics": ics_result}


def import_csv(path: str, dedupe: bool = True) -> dict:
    """Import readings from a CSV file. Expects columns: sys, dia, pul,
    and optionally date, notes. Invalid or duplicate rows are skipped,
    not fatal, and reported back to the caller."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    data = load_data()
    existing_keys = {(r["date"], r["sys"], r["dia"], r["pul"]) for r in data["records"]}
    imported, skipped = 0, []

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):  # header is line 1
            try:
                sys_ = int(row["sys"])
                dia = int(row["dia"])
                pul = int(row["pul"])
                validate_reading(sys_, dia, pul)
                date = row.get("date") or datetime.now().strftime("%Y-%m-%d %H:%M")
                notes = row.get("notes", "") or ""
                key = (date, sys_, dia, pul)
                if dedupe and key in existing_keys:
                    skipped.append({"line": line_num, "reason": "duplicate"})
                    continue
                data["records"].append(
                    {
                        "date": date,
                        "sys": sys_,
                        "dia": dia,
                        "pul": pul,
                        "notes": notes,
                        "classification": classify(sys_, dia),
                    }
                )
                existing_keys.add(key)
                imported += 1
            except (ValueError, KeyError) as e:
                skipped.append({"line": line_num, "reason": str(e)})

    save_data(data)
    return {
        "imported": imported,
        "skipped": skipped,
        "total_records": len(data["records"]),
    }


# ---------- CLI ----------


def main():
    parser = argparse.ArgumentParser(description="BP Daily Tracker")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="Add a reading")
    p_add.add_argument("sys", type=int)
    p_add.add_argument("dia", type=int)
    p_add.add_argument("pul", type=int)
    p_add.add_argument("--notes", default="")

    p_report = sub.add_parser("report", help="Show trend report")
    p_report.add_argument("--days", type=int, default=7)

    sub.add_parser("export", help="Export all records to CSV")
    sub.add_parser("reminders", help="Generate .ics calendar reminders")

    p_goal = sub.add_parser("set-goal", help="Add or replace a goal")
    p_goal.add_argument("text")
    p_goal.add_argument(
        "--replace", action="store_true", help="Replace all goals instead of appending"
    )

    p_reminder = sub.add_parser(
        "set-reminder", help="Add or replace a preferred check-in time (HH:MM)"
    )
    p_reminder.add_argument("time")
    p_reminder.add_argument(
        "--replace", action="store_true", help="Replace all times instead of appending"
    )

    p_import = sub.add_parser("import", help="Import readings from a CSV file")
    p_import.add_argument("path")
    p_import.add_argument(
        "--no-dedupe", action="store_true", help="Allow importing exact-duplicate rows"
    )

    args = parser.parse_args()

    if args.command == "add":
        try:
            entry = add_reading(args.sys, args.dia, args.pul, args.notes)
            print(json.dumps(entry, indent=2))
            if "CRISIS" in entry["classification"]:
                print("\n⚠️  This reading is in a dangerous range. Seek medical attention now.")
        except ValueError as e:
            print(f"Invalid reading: {e}")
            raise SystemExit(1)
    elif args.command == "report":
        print(json.dumps(get_report(args.days), indent=2, default=str))
    elif args.command == "export":
        print(export_csv())
    elif args.command == "reminders":
        print(generate_ical_reminders())
    elif args.command == "set-goal":
        print(json.dumps(set_goal(args.text, args.replace), indent=2))
    elif args.command == "set-reminder":
        try:
            print(json.dumps(set_reminder(args.time, args.replace), indent=2))
        except ValueError as e:
            print(f"Invalid time: {e}")
            raise SystemExit(1)
    elif args.command == "import":
        try:
            result = import_csv(args.path, dedupe=not args.no_dedupe)
            print(json.dumps(result, indent=2))
        except FileNotFoundError as e:
            print(str(e))
            raise SystemExit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
