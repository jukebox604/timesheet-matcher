import { useState, useEffect, useCallback } from 'react'
import { fetchEvents, fetchProjects, fetchTasks, type EventItem, type TeamworkProject, type TeamworkTask } from './timesheet'

interface MatchEntry {
  eventId: string
  projectId: number | null
  taskId: number | null
}

export default function Events() {
  const today = new Date().toISOString().slice(0, 10)
  const threeDaysAgo = new Date(Date.now() - 3 * 86400000).toISOString().slice(0, 10)
  const sixDaysOut = new Date(Date.now() + 6 * 86400000).toISOString().slice(0, 10)

  const [start, setStart] = useState(threeDaysAgo)
  const [end, setEnd] = useState(sixDaysOut)
  const [events, setEvents] = useState<EventItem[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<'all' | 'matched' | 'unmatched'>('all')
  const [matches, setMatches] = useState<Record<string, MatchEntry>>({})
  const [projects, setProjects] = useState<TeamworkProject[]>([])
  const [tasks, setTasks] = useState<Record<number, TeamworkTask[]>>({})
  const [loadingTasks, setLoadingTasks] = useState<Record<number, boolean>>({})
  const [error, setError] = useState('')

  useEffect(() => {
    fetchProjects()
      .then(setProjects)
      .catch(() => {})
  }, [])

  const handleLoad = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchEvents(start, end)
      setEvents(data.events || [])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [start, end])

  const handleSelectProject = async (eventId: string, projectId: number | null) => {
    setMatches(prev => ({
      ...prev,
      [eventId]: { eventId, projectId, taskId: projectId ? null : null },
    }))
    if (projectId && !tasks[projectId]) {
      setLoadingTasks(prev => ({ ...prev, [projectId]: true }))
      try {
        const taskList = await fetchTasks(projectId)
        setTasks(prev => ({ ...prev, [projectId]: taskList }))
      } catch {
        setTasks(prev => ({ ...prev, [projectId]: [] }))
      } finally {
        setLoadingTasks(prev => ({ ...prev, [projectId]: false }))
      }
    }
  }

  const handleSelectTask = (eventId: string, taskId: number | null) => {
    setMatches(prev => {
      const existing = prev[eventId]
      if (!existing) return prev
      return { ...prev, [eventId]: { ...existing, taskId } }
    })
  }

  const handleClear = (eventId: string) => {
    setMatches(prev => {
      const next = { ...prev }
      delete next[eventId]
      return next
    })
  }

  const matchedCount = events.filter(e => matches[e.id]?.projectId && matches[e.id]?.taskId).length

  const filtered = events.filter(e => {
    if (filter === 'matched') return matches[e.id]?.projectId && matches[e.id]?.taskId
    if (filter === 'unmatched') return !matches[e.id]?.projectId || !matches[e.id]?.taskId
    return true
  })

  const formatDuration = (minutes?: number) => {
    if (!minutes) return '0h'
    const h = minutes / 60
    return `${h.toFixed(1)}h`
  }

  const formatDate = (startStr?: string) => {
    if (!startStr) return ''
    return startStr.slice(0, 10)
  }

  const getTitle = (ev: EventItem) => {
    return ev.title || ev.type || ev._calendar_name || 'Unavailable'
  }

  return (
    <div className="card">
      <h1 className="card-header">Events</h1>

      <div className="controls-row">
        <div className="field-group">
          <label>Start</label>
          <input type="date" value={start} onChange={e => setStart(e.target.value)} />
        </div>
        <div className="field-group">
          <label>End</label>
          <input type="date" value={end} onChange={e => setEnd(e.target.value)} />
        </div>
        <button className="btn btn-primary" onClick={handleLoad} disabled={loading}>
          {loading ? 'Loading…' : 'Load Events'}
        </button>
        <div className="field-group">
          <select value={filter} onChange={e => setFilter(e.target.value as typeof filter)}>
            <option value="all">All ({events.length})</option>
            <option value="matched">Matched ({matchedCount})</option>
            <option value="unmatched">Unmatched ({events.length - matchedCount})</option>
          </select>
        </div>
      </div>

      {error && <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 12 }}>{error}</p>}

      {events.length > 0 && (
        <div className="status-text">
          {events.length} events · {matchedCount} matched
        </div>
      )}

      {events.length === 0 && !loading && !error && (
        <div className="empty-state">
          <p>Select a date range and click <strong>Load Events</strong> to see calendar events.</p>
        </div>
      )}

      {loading && events.length === 0 && (
        <div className="empty-state">
          <p>Loading events<span className="loading-dots" /></p>
        </div>
      )}

      <div className="event-list">
        {filtered.map(ev => {
          const match = matches[ev.id]
          const selectedProject = match?.projectId
          const selectedTask = match?.taskId
          const projectTasks = selectedProject ? tasks[selectedProject] : []
          const isTasksLoading = selectedProject ? loadingTasks[selectedProject] : false

          return (
            <div key={ev.id} className="event-card">
              <div className="event-info">
                <div className="event-title-row">
                  <span className="event-title">{getTitle(ev)}</span>
                  <span className="badge badge-unmatched">Unmatched</span>
                </div>
                <div className="event-time">
                  {formatDate(ev.start)} {formatDuration(ev.duration_minutes)}
                </div>
              </div>
              <div className="event-actions">
                <select
                  value={selectedProject ?? ''}
                  onChange={e => handleSelectProject(ev.id, e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">— Select Project —</option>
                  {projects.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                <select
                  value={selectedTask ?? ''}
                  onChange={e => handleSelectTask(ev.id, e.target.value ? Number(e.target.value) : null)}
                  disabled={!selectedProject || isTasksLoading}
                >
                  <option value="">— Select Task —</option>
                  {projectTasks.map(t => (
                    <option key={t.id} value={t.id}>{t.name || t.content}</option>
                  ))}
                </select>
                <button
                  className="btn btn-primary btn-small"
                  disabled={!selectedProject || !selectedTask}
                  onClick={() => alert(`Match saved for event ${ev.id}`)}
                >
                  Match
                </button>
                <button className="btn btn-secondary btn-small" onClick={() => handleClear(ev.id)}>
                  Clear
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
