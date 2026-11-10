import test from 'node:test'
import assert from 'node:assert/strict'
import { attendeeNames, descriptionWithAttendees } from '../src/attendeeDetails.js'

test('Teamwork nested attendees appear first; self and ID-only attendees are omitted', () => {
  const event = {
    title: 'Cross-Functional Discussion',
    description: 'Review product options.',
    attendees: [
      { user: { fullName: 'Heather King', email: 'heather@example.com' } },
      { user: { user: { id: 625680 }, email: null, fullName: null } },
      { user: { fullName: 'dmcase@example.com', email: 'dmcase@example.com' } },
      { user: { user: { id: 531538 } }, isSelf: true },
      { user: { fullName: 'Heather King', email: 'heather@example.com' } },
    ],
  }
  assert.deepEqual(attendeeNames(event.attendees), ['Heather King', 'dmcase@example.com'])
  assert.equal(descriptionWithAttendees(event, { id: 42, subject: 'Issue' }),
    'Meeting with:\n- Heather King\n- dmcase@example.com\n\nDesk #42 — Issue\n\nReview product options.')
})

test('Google flat attendees use displayName or email and exclude self', () => {
  const event = { title: 'Sync', attendees: [
    { displayName: 'Person One', email: 'one@example.com' },
    { email: 'two@example.com' },
    { displayName: 'Me', self: true },
  ] }
  assert.equal(descriptionWithAttendees(event),
    'Meeting with:\n- Person One\n- two@example.com\n\nEvent: Sync')
})

test('Events without attendee names retain their original description', () => {
  assert.equal(descriptionWithAttendees({ description: 'Work details', attendees: [{ user: { user: { id: 12 } } }] }), 'Work details')
  assert.equal(descriptionWithAttendees({ title: 'Standup' }), 'Event: Standup')
})

test('Attendee names cannot inject extra description lines', () => {
  assert.equal(descriptionWithAttendees({ description: 'Agenda', attendees: [{ displayName: 'Alice\n- Fake' }] }),
    'Meeting with:\n- Alice - Fake\n\nAgenda')
})
