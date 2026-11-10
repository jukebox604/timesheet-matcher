from app.main import _calendar_timelog_payload, _clean_event_description, _normalize_google_calendar_event

ZOOM = """Join Zoom Meeting
https://us02web.zoom.us/j/123456789?pwd=test

Meeting ID: 123 4567 89
Passcode: example
One tap mobile
+16468769923,,123456789# US (New York)

Dial by your location
        +1 646 876 9923 US (New York)
Meeting ID: 123 4567 89
Find your local number: https://us02web.zoom.us/u/example"""

TEAMS = """________________________________________________________________________________
Microsoft Teams meeting
Join: https://teams.microsoft.com/meet/example
Meeting ID: 123 456 789
Passcode: example
________________________________
Need help? | System reference
Dial in by phone
+1 317-762-2696,,547383905# United States, Indianapolis
Find a local number
Phone conference ID: 547 383 905#
Join on a video conferencing device
Tenant key: example@teams.bjn.vc
Video ID: 113 248 354 0
More info
For organizers: Meeting options | Reset dial-in PIN
________________________________________________________________________________"""


def test_zoom_invitation_is_removed_but_agenda_before_and_notes_after_remain():
    desc = f"Agenda: Product review.\n\n{ZOOM}\n\nDecision: approve the change."
    assert _clean_event_description(desc) == "Agenda: Product review.\n\nDecision: approve the change."
    assert _clean_event_description(ZOOM) == ""


def test_teams_invitation_is_removed_including_inner_phone_section():
    desc = f"Meeting notes: Discuss release plan.\n\n{TEAMS}\n\nNext: follow up with QA."
    assert _clean_event_description(desc) == "Meeting notes: Discuss release plan.\n\nNext: follow up with QA."
    assert _clean_event_description(TEAMS) == ""


def test_teams_without_outer_separator_is_removed_through_organizer_footer():
    desc = "Agenda: Review.\n\n" + TEAMS.split("\n", 1)[1].rsplit("\n", 1)[0]
    assert _clean_event_description(desc) == "Agenda: Review."


def test_html_conferencing_block_is_removed_after_tag_normalization():
    desc = "<p>Agenda: Check status.</p><p>Join Zoom Meeting<br>https://us02web.zoom.us/j/123<br>Meeting ID: 123<br>Find your local number: https://us02web.zoom.us/u/abc</p>"
    assert _clean_event_description(desc) == "Agenda: Check status."


def test_zoom_unicode_rule_variant_is_removed_without_dropping_surrounding_notes():
    desc = (
        "Agenda: Infor MES check-in.\n\n"
        "──────────\n\nSomeone is inviting you to a scheduled Zoom meeting.\n\n"
        "Join Zoom Meeting\nhttps://us02web.zoom.us/j/example\n\n"
        "Join and take notes\nhttps://zoom.us/notes\n\n"
        "Meeting ID: 123 456\n\nOne tap mobile\n+15551234567#\n\n"
        "Join instructions\nhttps://zoom.us/instructions\n\n──────────\n\n"
        "Decision: follow up tomorrow."
    )
    assert _clean_event_description(desc) == "Agenda: Infor MES check-in.\n\nDecision: follow up tomorrow."


def test_reclaim_tilde_divider_removes_completion_reminder_and_anything_below():
    desc = "Task notes: Prepare the mapping.\n~~~~~~~~\nThis Task event is now considered complete in Reclaim.\nPrivate reminder."
    assert _clean_event_description(desc) == "Task notes: Prepare the mapping."
    assert _clean_event_description("~~~~~~~~\nThis Task event is now considered complete in Reclaim.") == ""


def test_tilde_inline_in_actual_notes_is_not_a_divider():
    assert _clean_event_description("Estimate ~~~~4 hours for the task.") == "Estimate ~~~~4 hours for the task."


def test_cleaned_google_description_reaches_time_payload_without_invite():
    event = _normalize_google_calendar_event({
        "id": "zoom", "summary": "Project review", "description": "Agenda: Review.\n\n" + ZOOM,
        "start": {"dateTime": "2026-11-02T09:00:00-08:00"},
        "end": {"dateTime": "2026-11-02T09:30:00-08:00"},
    })
    assert event["description"] == "Agenda: Review."
    entry = {"title": event["title"], "description": event["description"],
             "start": event["start"], "duration_minutes": 30, "projectId": 1, "taskId": 2}
    assert _calendar_timelog_payload(entry)["description"] == "Agenda: Review."
