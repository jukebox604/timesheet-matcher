// Format names from either Teamwork's nested attendee.user records or Google's
// flat Calendar attendee records. Never invent names for ID-only records.
export function attendeeNames(attendees) {
  if (!Array.isArray(attendees)) return []
  const seen = new Set()
  const names = []
  for (const attendee of attendees) {
    if (!attendee || typeof attendee !== 'object' || attendee.isSelf || attendee.self) continue
    const person = attendee.user && typeof attendee.user === 'object' ? attendee.user : attendee
    const name = [person.fullName, person.displayName, person.name, person.email]
      .find(value => typeof value === 'string' && value.trim())
    if (!name) continue
    // Keep one line per person even when upstream names contain newlines.
    const safeName = name.replace(/[\r\n\t]+/g, ' ').trim()
    const key = (typeof person.email === 'string' && person.email.trim()
      ? person.email.trim() : safeName).toLowerCase()
    if (!safeName || seen.has(key)) continue
    seen.add(key)
    names.push(safeName)
  }
  return names
}

export function descriptionWithAttendees(event, deskTicket) {
  const base = event.description || `Event: ${event.title || ''}`
  const deskDescription = deskTicket
    ? `Desk #${deskTicket.id} — ${deskTicket.subject}\n\n${base}` : base
  const names = attendeeNames(event.attendees)
  return names.length
    ? `Meeting with:\n${names.map(name => `- ${name}`).join('\n')}\n\n${deskDescription}`
    : deskDescription
}
