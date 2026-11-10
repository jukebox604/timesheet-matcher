import type { DeskTicket, EventItem } from './timesheet'

export function attendeeNames(attendees: unknown): string[]
export function descriptionWithAttendees(event: EventItem, deskTicket?: DeskTicket): string
