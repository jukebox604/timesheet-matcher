from app.main import _calendar_timelog_payload, _plain_task_time_entry_payload


def test_google_entry_keeps_attendees_at_start_before_title():
    entry = {
        "title": "Client meeting",
        "description": "Meeting with:\n- Heather King\n- Betsy Sullivan\n\nAgenda and notes",
        "start": "2026-11-02T09:00:00-08:00",
        "duration_minutes": 30,
        "projectId": 1,
        "taskId": 2,
    }
    payload = _plain_task_time_entry_payload(entry, "531538")
    assert payload["description"] == "Meeting with:\n- Heather King\n- Betsy Sullivan\n\nClient meeting\n\nAgenda and notes"
    assert _calendar_timelog_payload(entry)["description"].startswith("Meeting with:\n")


def test_google_entry_without_attendees_keeps_existing_format():
    entry = {
        "title": "Client meeting",
        "description": "Agenda and notes",
        "start": "2026-11-02T09:00:00-08:00",
        "duration_minutes": 30,
        "projectId": 1,
        "taskId": 2,
    }
    payload = _plain_task_time_entry_payload(entry, "531538")
    assert payload["description"] == "Client meeting\n\nAgenda and notes"
