import { useState, useEffect, useCallback, useMemo } from 'react'
import { fetchEvents, fetchProjects, fetchTasks, type EventItem, type TeamworkProject, type TeamworkTask } from './timesheet'

interface MatchEntry {
  eventId: string
  projectId: number | null
  taskId: number | null
}

interface SuggestedMatch {
  projectId: number
  projectName: string
  taskId: number
  taskName: string
  reason: string
}

const WORK_WEEK_TARGET_MINUTES = 40 * 60

const SUGGESTIONS: Array<SuggestedMatch & { keywords: string[] }> = [
  {
    keywords: ['asr api', 'mass changes', 'kitting'],
    projectId: 962004,
    projectName: 'ASR | API Mass Changes & Kitting Updates',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'ASR API / mass changes / kitting keyword match',
  },
  {
    keywords: ['shipment advice', 'dispatch advice', 'vendor dropship', 'suffix level', 'enhanced 901'],
    projectId: 966753,
    projectName: 'ASR | Dispatch Advice & Invoicing at Suffix Level',
    taskId: 32676546,
    taskName: 'Enhanced 901 for vendor dropships',
    reason: 'ASR dispatch / 901 keyword match',
  },
  {
    keywords: ['asraymond', 'as raymond', 'asr weekly connect', 'asr scrum', 'asr connect'],
    projectId: 956015,
    projectName: 'ASR | Application Managed Services',
    taskId: 32043629,
    taskName: 'Daily/Weekly/Ad-hoc Meetings',
    reason: 'ASR meeting keyword match',
  },
  {
    keywords: ['brownells', 'brown'],
    projectId: 502827,
    projectName: 'BROWN | Application Managed Services',
    taskId: 32200244,
    taskName: 'IDM',
    reason: 'Brownells keyword match',
  },
  {
    keywords: ['berkshire corp', 'bkc', 'qms', 'endotoxin'],
    projectId: 390351,
    projectName: 'BKC | Application Managed Services',
    taskId: 32199685,
    taskName: 'IDM',
    reason: 'BKC / QMS keyword match',
  },
  {
    keywords: ['qms601', 'endotoxin supplement'],
    projectId: 390351,
    projectName: 'BKC | Application Managed Services',
    taskId: 33020261,
    taskName: 'QMS601 Endotoxin Supplement Page',
    reason: 'QMS601 / endotoxin supplement keyword match',
  },
  {
    keywords: ['berkshire blanket', 'bkb'],
    projectId: 388354,
    projectName: 'BKB | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'BKB keyword match',
  },
  {
    keywords: ['ipcorp', 'ip corp', 'factory track', 'ftk', 'mp printer', 'shoptraveler'],
    projectId: 463320,
    projectName: 'IPC | Application Managed Services',
    taskId: 32165881,
    taskName: 'IDM',
    reason: 'IPC / Factory Track keyword match',
  },
  {
    keywords: ['jpmc', 'phase ii'],
    projectId: 959894,
    projectName: 'IP Corp | JPMC Phase II SOW',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'JPMC / Phase II keyword match',
  },
  {
    keywords: ['herff jones', 'hj ', 'hj-', 'hj:', 'erp transformation', 'output documents'],
    projectId: 951450,
    projectName: 'HJ | ERP Transformation Project',
    taskId: 32835935,
    taskName: 'HJ Output documents',
    reason: 'Herff Jones / HJ keyword match',
  },
  {
    keywords: ['ahern', 'ahern family'],
    projectId: 861705,
    projectName: 'AHERN | Application Managed Services',
    taskId: 32008552,
    taskName: 'IDM',
    reason: 'Ahern keyword match',
  },
  {
    keywords: ['champion', 'cpf'],
    projectId: 390355,
    projectName: 'CPF | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Champion / CPF keyword match',
  },
  {
    keywords: ['custom truck', 'ctos'],
    projectId: 923416,
    projectName: 'CTOS | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Custom Truck / CTOS keyword match',
  },
  {
    keywords: ['grosfillex', 'gfx'],
    projectId: 422590,
    projectName: 'GFX | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Grosfillex / GFX keyword match',
  },
  {
    keywords: ['mac papers', 'mpp'],
    projectId: 898506,
    projectName: 'MPP | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Mac Papers / MPP keyword match',
  },
  {
    keywords: ['macarthur', 'macar'],
    projectId: 862689,
    projectName: 'MACAR | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'MacArthur keyword match',
  },
  {
    keywords: ['sani marc'],
    projectId: 882196,
    projectName: 'Sani Marc | Cloud Migration',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Sani Marc keyword match',
  },
  {
    keywords: ['teamwork', 'teamdesk', 'slack', 'jira', 'email', 'admin'],
    projectId: 417162,
    projectName: 'DG | Internal Activities',
    taskId: 29936460,
    taskName: 'General Administrative Tasks',
    reason: 'Doppio admin keyword match',
  },
  {
    keywords: ['mes training', 'infor u', 'training'],
    projectId: 861413,
    projectName: 'DG | Education and Learning',
    taskId: 32768933,
    taskName: 'Infor U training',
    reason: 'Training keyword match',
  },
]

function toDateInputValue(date: Date) {
  const copy = new Date(date)
  copy.setMinutes(copy.getMinutes() - copy.getTimezoneOffset())
  return copy.toISOString().slice(0, 10)
}

function currentWorkWeek() {
  const today = new Date()
  const day = today.getDay() || 7
  const monday = new Date(today)
  monday.setDate(today.getDate() - day + 1)
  const friday = new Date(monday)
  friday.setDate(monday.getDate() + 4)
  return { start: toDateInputValue(monday), end: toDateInputValue(friday) }
}

function eventText(ev: EventItem) {
  return [ev.title, ev.description, ev.type, ev._calendar_name].filter(Boolean).join(' ').toLowerCase()
}

function cleanDescription(description?: string) {
  if (!description) return 'No description provided.'
  return description.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() || 'No description provided.'
}

function suggestForEvent(ev: EventItem): SuggestedMatch | null {
  const text = eventText(ev)
  const hit = SUGGESTIONS.find(s => s.keywords.some(k => text.includes(k)))
  if (!hit) return null
  const { keywords, ...suggestion } = hit
  return suggestion
}

function hasMappedTask(ev: EventItem) {
  const maybe = ev as EventItem & { mappedTaskIds?: unknown }
  return Array.isArray(maybe.mappedTaskIds) && maybe.mappedTaskIds.length > 0
}

export default function Events() {
  const defaults = useMemo(() => currentWorkWeek(), [])
  const [start, setStart] = useState(defaults.start)
  const [end, setEnd] = useState(defaults.end)
  const [events, setEvents] = useState<EventItem[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<'all' | 'matched' | 'unmatched'>('all')
  const [matches, setMatches] = useState<Record<string, MatchEntry>>({})
  const [confirmedMatches, setConfirmedMatches] = useState<Record<string, MatchEntry>>({})
  const [projects, setProjects] = useState<TeamworkProject[]>([])
  const [tasks, setTasks] = useState<Record<number, TeamworkTask[]>>({})
  const [loadingTasks, setLoadingTasks] = useState<Record<number, boolean>>({})
  const [error, setError] = useState('')

  const loadTasksForProject = useCallback(async (projectId: number) => {
    if (tasks[projectId] || loadingTasks[projectId]) return
    setLoadingTasks(prev => ({ ...prev, [projectId]: true }))
    try {
      const taskList = await fetchTasks(projectId)
      setTasks(prev => ({ ...prev, [projectId]: taskList }))
    } catch {
      setTasks(prev => ({ ...prev, [projectId]: [] }))
    } finally {
      setLoadingTasks(prev => ({ ...prev, [projectId]: false }))
    }
  }, [loadingTasks, tasks])

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
      const loadedEvents = data.events || []
      const initialMatches: Record<string, MatchEntry> = {}
      const suggestedProjectIds = new Set<number>()

      for (const ev of loadedEvents) {
        const suggestion = suggestForEvent(ev)
        if (suggestion) {
          initialMatches[ev.id] = {
            eventId: ev.id,
            projectId: suggestion.projectId,
            taskId: suggestion.taskId || null,
          }
          suggestedProjectIds.add(suggestion.projectId)
        }
      }

      setEvents(loadedEvents)
      setMatches(initialMatches)
      setConfirmedMatches({})
      await Promise.all(Array.from(suggestedProjectIds).map(projectId => loadTasksForProject(projectId)))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [end, loadTasksForProject, start])

  const handleSelectProject = async (eventId: string, projectId: number | null) => {
    setMatches(prev => ({
      ...prev,
      [eventId]: { eventId, projectId, taskId: null },
    }))
    setConfirmedMatches(prev => {
      const next = { ...prev }
      delete next[eventId]
      return next
    })
    if (projectId) await loadTasksForProject(projectId)
  }

  const handleSelectTask = (eventId: string, taskId: number | null) => {
    setMatches(prev => {
      const existing = prev[eventId] || { eventId, projectId: null, taskId: null }
      return { ...prev, [eventId]: { ...existing, taskId } }
    })
    setConfirmedMatches(prev => {
      const next = { ...prev }
      delete next[eventId]
      return next
    })
  }

  const handleMatch = (eventId: string) => {
    const match = matches[eventId]
    if (!match?.projectId || !match?.taskId) return
    setConfirmedMatches(prev => ({ ...prev, [eventId]: match }))
  }

  const handleClear = (eventId: string) => {
    setMatches(prev => {
      const next = { ...prev }
      delete next[eventId]
      return next
    })
    setConfirmedMatches(prev => {
      const next = { ...prev }
      delete next[eventId]
      return next
    })
  }

  const isMatched = useCallback((ev: EventItem) => {
    return Boolean(confirmedMatches[ev.id]?.projectId && confirmedMatches[ev.id]?.taskId) || hasMappedTask(ev)
  }, [confirmedMatches])

  const matchedCount = events.filter(isMatched).length
  const weeklyTotalMinutes = events.reduce((total, ev) => total + (ev.duration_minutes || 0), 0)
  const weeklyRemainingMinutes = Math.max(WORK_WEEK_TARGET_MINUTES - weeklyTotalMinutes, 0)
  const weeklyProgressPercent = Math.min((weeklyTotalMinutes / WORK_WEEK_TARGET_MINUTES) * 100, 100)

  const filtered = events.filter(e => {
    if (filter === 'matched') return isMatched(e)
    if (filter === 'unmatched') return !isMatched(e)
    return true
  })

  const formatDuration = (minutes?: number) => {
    if (!minutes) return '0h'
    const h = minutes / 60
    return `${h.toFixed(1)}h`
  }

  const formatHours = (minutes: number) => `${(minutes / 60).toFixed(1)}h`

  const formatDate = (startStr?: string) => {
    if (!startStr) return ''
    return String(startStr).slice(0, 10)
  }

  const getTitle = (ev: EventItem) => {
    return ev.title || ev.type || ev._calendar_name || 'Untitled event'
  }

  const projectName = (projectId?: number | null) => {
    if (!projectId) return ''
    return projects.find(p => p.id === projectId)?.name || SUGGESTIONS.find(s => s.projectId === projectId)?.projectName || ''
  }

  const taskName = (projectId?: number | null, taskId?: number | null) => {
    if (!projectId || !taskId) return ''
    return tasks[projectId]?.find(t => t.id === taskId)?.name || tasks[projectId]?.find(t => t.id === taskId)?.content || SUGGESTIONS.find(s => s.taskId === taskId)?.taskName || ''
  }

  return (
    <div className="card matching-card">
      <h1 className="card-header">Matching</h1>

      <div className="controls-row matching-controls">
        <div className="field-group">
          <label>Start</label>
          <input type="date" value={start} onChange={e => setStart(e.target.value)} />
        </div>
        <div className="field-group">
          <label>End</label>
          <input type="date" value={end} onChange={e => setEnd(e.target.value)} />
        </div>
        <button className="btn btn-primary load-events-btn" onClick={handleLoad} disabled={loading}>
          {loading ? 'Loading…' : 'Load Events'}
        </button>
        <div className="field-group filter-field">
          <label>View</label>
          <select value={filter} onChange={e => setFilter(e.target.value as typeof filter)}>
            <option value="all">All ({events.length})</option>
            <option value="matched">Matched ({matchedCount})</option>
            <option value="unmatched">Unmatched ({events.length - matchedCount})</option>
          </select>
        </div>
      </div>

      <div className="week-progress-card">
        <div className="week-progress-header">
          <div>
            <span className="week-progress-label">Weekly target</span>
            <strong>{formatHours(weeklyTotalMinutes)} / 40.0h</strong>
          </div>
          <div className={weeklyRemainingMinutes > 0 ? 'week-progress-short' : 'week-progress-complete'}>
            {weeklyRemainingMinutes > 0 ? `${formatHours(weeklyRemainingMinutes)} short` : '40h met'}
          </div>
        </div>
        <div className="week-progress-track" aria-label="40 hour weekly progress">
          <div className="week-progress-fill" style={{ width: `${weeklyProgressPercent}%` }} />
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="status-text">
        {events.length} events · {matchedCount} matched · {events.length - matchedCount} unmatched
      </div>

      {events.length === 0 && !loading && !error && (
        <div className="empty-state">
          <p>Current work week is selected by default. Click <strong>Load Events</strong> to import calendar events.</p>
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
          const projectTasks = selectedProject ? tasks[selectedProject] || [] : []
          const isTasksLoading = selectedProject ? loadingTasks[selectedProject] : false
          const suggestion = suggestForEvent(ev)
          const matched = isMatched(ev)
          const selectedProjectName = projectName(selectedProject)
          const selectedTaskName = taskName(selectedProject, selectedTask)

          return (
            <div key={ev.id} className={`event-card ${matched ? 'event-card-matched' : ''}`}>
              <div className="event-summary">
                <div className="event-title-row">
                  <span className="event-title">{getTitle(ev)}</span>
                  <span className={`badge ${matched ? 'badge-matched' : 'badge-unmatched'}`}>
                    {matched ? 'Matched' : 'Unmatched'}
                  </span>
                </div>
                <div className="event-time">
                  {formatDate(ev.start || (ev as EventItem & { start_at?: string }).start_at)} · {formatDuration(ev.duration_minutes)}
                  {ev._calendar_name ? ` · ${ev._calendar_name}` : ''}
                </div>
                <p className="event-description">{cleanDescription(ev.description)}</p>
                <div className="suggestion-box">
                  <span className="suggestion-label">Suggested match</span>
                  {suggestion ? (
                    <div className="suggestion-copy">
                      <strong>{selectedProjectName || suggestion.projectName}</strong>
                      <span>{selectedTaskName || suggestion.taskName}</span>
                      <small>{suggestion.reason}</small>
                    </div>
                  ) : (
                    <div className="suggestion-copy muted">
                      <strong>No suggestion yet</strong>
                      <span>Select the project and task manually.</span>
                    </div>
                  )}
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
                  <option value="">{isTasksLoading ? 'Loading tasks…' : '— Select Task —'}</option>
                  {selectedTask && !projectTasks.some(t => t.id === selectedTask) && selectedTaskName && (
                    <option value={selectedTask}>{selectedTaskName}</option>
                  )}
                  {projectTasks.map(t => (
                    <option key={t.id} value={t.id}>{t.name || t.content}</option>
                  ))}
                </select>
                <button
                  className="btn btn-primary btn-small"
                  disabled={!selectedProject || !selectedTask}
                  onClick={() => handleMatch(ev.id)}
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
