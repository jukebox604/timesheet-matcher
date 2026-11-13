import pytest
from app.main import _clean_event_description, _normalize_google_calendar_event, _calendar_timelog_payload

TICKET_INVITE = """Hi Team,

Please join the meeting only if you have an open ticket to discuss.

If you have an open ticket but are unable to join, please make sure it is properly updated with the latest status in the notes (daily updates are required), ticket options, estimations, and ticket status.

Also, please let me know in advance if you are unable to join.

Thank you!"""
MONTHLY_INVITE = """Hello All,

This is our monthly check-in on our Managed Services & opportunity to discuss any other open items.

Topics to touch on:
• Utilization Report
• Monthly Volume Of Prod Issues.
• Activity Progress Status.
• Additional Considerations.

Regards
Anu K S
──────────
Anu K.S is inviting you to a scheduled Zoom meeting.

──────────"""
THREAD = """From: someone@example.com
Sent: Tuesday, November 10
To: colleague@example.com
Subject: Issue
Please investigate.
Regards
Someone"""

@pytest.mark.parametrize('text', [TICKET_INVITE, MONTHLY_INVITE, THREAD])
def test_email_body_is_removed(text):
    assert _clean_event_description(text) == ''
    assert _clean_event_description(text.replace('\n', '<br>')) == ''

@pytest.mark.parametrize('text', [
    'Meeting notes: Reviewed invoices.\n• Fix mapping\n• Retest export',
    'Contact someone@example.com about the invoice.',
    'Hi Team,\n\nInvestigated invoice mapping and fixed the export.',
    'Work performed: Updated template.\nThanks to QA for testing.',
])
def test_legitimate_notes_are_unchanged(text):
    assert _clean_event_description(text) == text

@pytest.mark.parametrize('body', [TICKET_INVITE, MONTHLY_INVITE, THREAD])
def test_independent_notes_above_email_are_preserved(body):
    assert _clean_event_description('Work performed: Fixed mappings.\n\n' + body) == 'Work performed: Fixed mappings.'

def test_labelled_notes_below_email_are_preserved():
    assert _clean_event_description(TICKET_INVITE + '\n\nMeeting notes: Agreed to retest.') == 'Meeting notes: Agreed to retest.'

def test_reply_history_is_removed_without_removing_notes_above():
    assert _clean_event_description('Meeting notes: Retested invoice.\n\nOn Tuesday, Someone wrote:\n> Original message') == 'Meeting notes: Retested invoice.'


def test_repeated_live_style_email_bodies_and_comma_signature_are_removed():
    text = 'Team,\n\nPushing this meeting to Monday.\n\nThanks!\n\nHi team,\n\nPlease review the scenarios.\n\nThanks,\nSomeone'
    assert _clean_event_description(text) == ''

def test_google_import_uses_same_cleaner_and_title_fallback_for_submission():
    event = _normalize_google_calendar_event({
        'id': 'email', 'summary': 'ASR weekly meeting', 'description': TICKET_INVITE,
        'start': {'dateTime': '2026-11-09T09:00:00-08:00'},
        'end': {'dateTime': '2026-11-09T09:30:00-08:00'},
    })
    assert event['description'] == ''
    entry = {**event, 'projectId': 1, 'taskId': 2, 'duration_minutes': 30}
    assert _calendar_timelog_payload(entry)['description'] == 'Event: ASR weekly meeting'
