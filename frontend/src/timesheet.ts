export interface EventItem {
  id: string
  title?: string
  description?: string
  start?: string
  end?: string
  duration_minutes?: number
  _calendar_name?: string
  calendarId?: number | string
  type?: string
  mappedTaskIds?: number[] | null
  staleMappedTaskIds?: number[] | null
  liveLoggedTaskIds?: number[] | null
  source?: string
  attendees?: unknown[]
}

export interface DeskTicket {
  id: number
  subject: string
  preview?: string
  status?: string
  state?: string
  priority?: string
  type?: string
  source?: string
  createdAt?: string
  updatedAt?: string
  companyName?: string
  deskCompanyId?: number
  customerName?: string
  customerEmail?: string
  assignedToName?: string
  assignedToEmail?: string
  projectIds?: number[]
}

export interface TeamworkProject {
  id: number
  name: string
}

export interface TeamworkTask {
  id: number
  name: string
  content?: string
}

export async function get<T>(path: string): Promise<T> {
  const separator = path.includes('?') ? '&' : '?'
  const cacheBustedPath = `${path}${separator}_=${Date.now()}`
  const res = await fetch(cacheBustedPath, { cache: 'no-store' })
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json() as Promise<T>
}

export async function post(path: string, body?: unknown): Promise<Response> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res
}

export type EventSource = 'teamwork' | 'google'

export interface EventsResponse {
  events: EventItem[]
  count: number
  query?: {
    source?: string
    requestedSource?: string
    fallbackFrom?: string
    googleCalendarError?: string
  }
}

export async function fetchEvents(start: string, end: string, source: EventSource = 'teamwork'): Promise<EventsResponse> {
  return get(`/api/teamwork/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&source=${encodeURIComponent(source)}`)
}

export interface TimesheetTotals {
  dailyTotals: Record<string, number>
  unavailableDailyTotals: Record<string, number>
  creditedDailyTotals: Record<string, number>
  personalCommitmentDailyTotals: Record<string, number>
  personalCommitmentUnloggedDailyTotals: Record<string, number>
}

export async function fetchTimesheetTotals(start: string, end: string): Promise<TimesheetTotals> {
  const data = await get<Partial<TimesheetTotals>>(`/api/teamwork/timesheets?startDate=${encodeURIComponent(start)}&endDate=${encodeURIComponent(end)}`)
  return {
    dailyTotals: data.dailyTotals || {},
    unavailableDailyTotals: data.unavailableDailyTotals || {},
    creditedDailyTotals: data.creditedDailyTotals || data.dailyTotals || {},
    personalCommitmentDailyTotals: data.personalCommitmentDailyTotals || {},
    personalCommitmentUnloggedDailyTotals: data.personalCommitmentUnloggedDailyTotals || data.personalCommitmentDailyTotals || {},
  }
}

export async function fetchProjects(): Promise<TeamworkProject[]> {
  const data = await get<{ projects: TeamworkProject[] }>('/api/teamwork/projects')
  return data.projects || []
}

export async function fetchTasks(projectId: number): Promise<TeamworkTask[]> {
  const data = await get<{ tasks: TeamworkTask[] }>(`/api/teamwork/projects/${projectId}/tasks`)
  return data.tasks || []
}

export async function fetchDeskTickets(params: { projectId?: number; ticketId?: number; query?: string; limit?: number }): Promise<DeskTicket[]> {
  const query = new URLSearchParams()
  if (params.projectId) query.set('projectId', String(params.projectId))
  if (params.ticketId) query.set('ticketId', String(params.ticketId))
  if (params.query) query.set('query', params.query)
  if (params.limit) query.set('limit', String(params.limit))
  const data = await get<{ tickets: DeskTicket[] }>(`/api/teamwork/desk-tickets?${query.toString()}`)
  return data.tickets || []
}

export interface SubmitMatchedEntry {
  eventId: string
  calendarId?: number | string
  title?: string
  description?: string
  start?: string
  date?: string
  duration_minutes?: number
  minutes?: number
  projectId: number
  taskId: number
  mappedTaskIds?: number[] | null
  source?: string
  deskTicketId?: number
  deskTicketSubject?: string
}

export async function submitMatchedEntries(entries: SubmitMatchedEntry[]): Promise<{ status: string; created: unknown[]; skipped: unknown[]; errors: unknown[] }> {
  const res = await post('/api/teamwork/submit-matched', { entries })
  return res.json()
}

export interface FillerPlanItem {
  date: string
  description: string
  minutes: number
  startTime: string
  taskId: number
}

export interface FillerPlanResponse {
  status: string
  message?: string
  plan: FillerPlanItem[]
  skipped: Array<{ date?: string; description?: string; reason?: string }>
  existingDates?: string[]
  dailyTotals: Record<string, number>
  weeklyCurrentMinutes: number
  weeklyTargetMinutes: number
  weeklyRemainingMinutes: number
  plannedMinutes: number
  projectedWeeklyMinutes: number
  fillerTaskId: number
}

export interface FillerCreateResponse {
  status: string
  message?: string
  created: unknown[]
  skipped: unknown[]
  dailyTotals: Record<string, number>
  weeklyTargetMinutes: number
  weeklyRemainingMinutes: number
  fillerTaskId: number
}

export async function planTimesheetFiller(start: string, end: string): Promise<FillerPlanResponse> {
  const res = await post('/api/teamwork/timesheet-filler/plan', { start, end })
  return res.json()
}

export async function createTimesheetFiller(start: string, end: string, plan: FillerPlanItem[]): Promise<FillerCreateResponse> {
  const res = await post('/api/teamwork/timesheet-filler/create', { start, end, plan })
  return res.json()
}
