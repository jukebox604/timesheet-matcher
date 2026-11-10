from app.main import _calendar_timelog_payload, _clean_event_description, _normalize_google_calendar_event


BOOKING_DESCRIPTION = (
    "Join meeting now\n"
    "Passcode: 794581 Event name: Booking Page\n"
    "Meeting notes: Marc,\n\n"
    "We will continue with Proper Case of the City and Country.\n"
    "Want to make changes to this event? You can edit the event directly or use the links below to cancel or reschedule.\n"
    "Cancel: https://app.reclaim.ai/meeting/example?action=cancel\n"
    "Reschedule: https://app.reclaim.ai/meeting/example/reschedule"
)
EXPECTED = "Meeting notes: Marc,\n\nWe will continue with Proper Case of the City and Country."


def test_reclaim_booking_page_keeps_only_meeting_notes():
    assert _clean_event_description(BOOKING_DESCRIPTION) == EXPECTED


def test_html_booking_page_and_multiline_footer():
    html = (
        "<div>Join meeting now<br>Passcode: 123 Event name: Booking Page</div>"
        "<p>Meeting notes: Marc,<br><br>Discuss the plan &amp; next steps.</p>"
        "<p>Want to make changes to this event? You can edit the event directly "
        "or use the links below to cancel or reschedule.</p>"
        "<p>Cancel: https://app.reclaim.ai/meeting/example</p>"
    )
    assert _clean_event_description(html) == "Meeting notes: Marc,\n\nDiscuss the plan & next steps."


def test_booking_page_meeting_details_and_wrapped_footer():
    description = (
        "Join meeting now\nMeeting details: Review specifications.\n"
        "Want to make changes to this event? You can edit the event directly\n"
        "or use the links below to cancel or reschedule.\nReschedule: https://example.com"
    )
    assert _clean_event_description(description) == "Meeting details: Review specifications."


def test_regular_meeting_without_reclaim_footer_is_untouched():
    description = "Join meeting now\nMeeting notes: Agenda\nKeep this line of details."
    assert _clean_event_description(description) == description


def test_footer_without_notes_does_not_remove_other_description():
    description = "Project update\nWant to make changes to this event? You can edit the event directly or use the links below to cancel or reschedule."
    assert _clean_event_description(description) == description


def test_google_import_and_teamwork_submission_keep_only_notes():
    event = _normalize_google_calendar_event({
        "id": "booking", "summary": "Project meeting", "description": BOOKING_DESCRIPTION,
        "start": {"dateTime": "2026-11-02T09:00:00-08:00"},
        "end": {"dateTime": "2026-11-02T09:30:00-08:00"},
    })
    assert event["description"] == EXPECTED
    entry = {"title": "Project meeting", "description": event["description"],
             "start": event["start"], "duration_minutes": 30, "projectId": 1, "taskId": 2}
    assert _calendar_timelog_payload(entry)["description"] == EXPECTED
