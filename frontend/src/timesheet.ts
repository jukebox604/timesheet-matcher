export interface EventItem {
  id: string
  title?: string
  description?: string
  start?: string
  end?: string
  duration_minutes?: number
  _calendar_name?: string
  calendarId?: number
  type?: string
  mappedTaskIds?: number[] | null
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
  const res = await fetch(path)
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

export async function fetchEvents(start: string, end: string): Promise<{ events: EventItem[]; count: number }> {
  return get(`/api/teamwork/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`)
}

export async function fetchProjects(): Promise<TeamworkProject[]> {
  const data = await get<{ projects: TeamworkProject[] }>('/api/teamwork/projects')
  return data.projects || []
}

export async function fetchTasks(projectId: number): Promise<TeamworkTask[]> {
  const data = await get<{ tasks: TeamworkTask[] }>(`/api/teamwork/projects/${projectId}/tasks`)
  return data.tasks || []
}

export interface SubmitMatchedEntry {
  eventId: string
  calendarId?: number
  title?: string
  description?: string
  start?: string
  date?: string
  duration_minutes?: number
  minutes?: number
  projectId: number
  taskId: number
  mappedTaskIds?: number[] | null
}

export async function submitMatchedEntries(entries: SubmitMatchedEntry[]): Promise<{ status: string; created: unknown[]; skipped: unknown[]; errors: unknown[] }> {
  const res = await post('/api/teamwork/submit-matched', { entries })
  return res.json()
}

export async function runTimesheetFiller(start: string, end: string): Promise<{ status: string; created: unknown[]; skipped: unknown[]; dailyTotals: Record<string, number> }> {
  const res = await post('/api/teamwork/timesheet-filler', { start, end })
  return res.json()
}
