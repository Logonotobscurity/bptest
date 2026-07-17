import csv
import json

import pytest

import tracker


@pytest.fixture(autouse=True)
def isolated_data_file(tmp_path, monkeypatch):
    """Point tracker at a throwaway data file for every test."""
    data_file = tmp_path / "bp_data.json"
    monkeypatch.setattr(tracker, "DATA_FILE", str(data_file))
    yield data_file


def test_validate_reading_accepts_normal_values():
    tracker.validate_reading(120, 80, 70)  # should not raise


def test_validate_reading_rejects_impossible_systolic():
    with pytest.raises(ValueError):
        tracker.validate_reading(999, 80, 70)


def test_validate_reading_rejects_diastolic_gte_systolic():
    with pytest.raises(ValueError):
        tracker.validate_reading(100, 110, 70)


@pytest.mark.parametrize(
    "sys_,dia,expected",
    [
        (110, 70, "Normal"),
        (125, 75, "Elevated"),
        (135, 85, "Hypertension Stage 1"),
        (145, 95, "Hypertension Stage 2"),
        (185, 100, "HYPERTENSIVE CRISIS — seek immediate medical attention"),
        (150, 121, "HYPERTENSIVE CRISIS — seek immediate medical attention"),
    ],
)
def test_classify(sys_, dia, expected):
    assert tracker.classify(sys_, dia) == expected


def test_add_reading_persists_to_disk(isolated_data_file):
    tracker.add_reading(122, 89, 82, "after walking")
    data = json.loads(isolated_data_file.read_text())
    assert len(data["records"]) == 1
    assert data["records"][0]["sys"] == 122


def test_add_reading_rejects_invalid():
    with pytest.raises(ValueError):
        tracker.add_reading(999, 999, 999)


def test_report_with_no_data_returns_message():
    result = tracker.get_report(days=7)
    assert isinstance(result, str)


def test_report_insufficient_data_for_trend():
    tracker.add_reading(120, 80, 70)
    tracker.add_reading(122, 81, 71)
    report = tracker.get_report(days=7)
    assert report["trend"] == "Not enough data yet for a trend"


def test_report_detects_rising_trend():
    for sys_ in [118, 119, 138, 140]:
        tracker.add_reading(sys_, 80, 70)
    report = tracker.get_report(days=7)
    assert "Rising" in report["trend"]


def test_export_csv_writes_file(tmp_path):
    tracker.add_reading(120, 80, 70)
    out = tmp_path / "out.csv"
    msg = tracker.export_csv(str(out))
    assert out.exists()
    assert "Exported 1 records" in msg


def test_export_csv_no_records():
    assert tracker.export_csv() == "No records to export."


def test_generate_ical_reminders(tmp_path):
    out = tmp_path / "reminders.ics"
    tracker.generate_ical_reminders(str(out))
    content = out.read_text()
    assert "BEGIN:VCALENDAR" in content
    assert "RRULE:FREQ=DAILY" in content


def test_set_goal_appends():
    goals = tracker.set_goal("Walk 30 minutes daily")
    assert "Walk 30 minutes daily" in goals
    assert "Keep average BP under 130/80" in goals  # default retained


def test_set_goal_replace():
    goals = tracker.set_goal("Only goal now", replace=True)
    assert goals == ["Only goal now"]


def test_set_reminder_valid_time():
    result = tracker.set_reminder("07:30")
    assert "07:30" in result["preferred_times"]


def test_set_reminder_invalid_time_raises():
    with pytest.raises(ValueError):
        tracker.set_reminder("25:99")


def test_import_csv_valid_rows(tmp_path):
    csv_path = tmp_path / "import.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "sys", "dia", "pul", "notes"])
        writer.writerow(["2026-01-01 08:00", "120", "80", "70", "morning"])
        writer.writerow(["2026-01-02 08:00", "125", "82", "72", ""])
    result = tracker.import_csv(str(csv_path))
    assert result["imported"] == 2
    assert result["skipped"] == []


def test_import_csv_skips_invalid_rows(tmp_path):
    csv_path = tmp_path / "import.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "sys", "dia", "pul"])
        writer.writerow(["2026-01-01 08:00", "999", "80", "70"])  # invalid
        writer.writerow(["2026-01-02 08:00", "120", "80", "70"])  # valid
    result = tracker.import_csv(str(csv_path))
    assert result["imported"] == 1
    assert len(result["skipped"]) == 1


def test_import_csv_dedupes_by_default(tmp_path):
    csv_path = tmp_path / "import.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "sys", "dia", "pul"])
        writer.writerow(["2026-01-01 08:00", "120", "80", "70"])
    tracker.import_csv(str(csv_path))
    result = tracker.import_csv(str(csv_path))  # import same file again
    assert result["imported"] == 0
    assert result["skipped"][0]["reason"] == "duplicate"


def test_import_csv_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        tracker.import_csv("does_not_exist.csv")
