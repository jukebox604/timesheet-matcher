import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { fetchEvents, fetchProjects, fetchTasks, fetchTimesheetTotals, submitMatchedEntries, runTimesheetFiller, type EventItem, type TeamworkProject, type TeamworkTask } from './timesheet'

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
  confidence: number
}

const WORK_WEEK_TARGET_MINUTES = 40 * 60

interface MatchRule extends SuggestedMatch {
  titleKeywords?: string[]
  detailKeywords?: string[]
  taskKeywords?: string[]
  priority?: number
}

const KNOWN_TASKS: Record<number, SuggestedMatch> = {
  29936460: { projectId: 417162, projectName: 'DG | Internal Activities', taskId: 29936460, taskName: 'General Administrative Tasks', reason: 'Known Teamwork task mapping', confidence: 100 },
  32008552: { projectId: 861705, projectName: 'AHERN | Application Managed Services', taskId: 32008552, taskName: 'IDM', reason: 'Known Teamwork task mapping', confidence: 100 },
  31545410: { projectId: 861705, projectName: 'AHERN | Application Managed Services', taskId: 31545410, taskName: 'Meetings', reason: 'Known Teamwork task mapping', confidence: 100 },
  32043629: { projectId: 956015, projectName: 'ASR | Application Managed Services', taskId: 32043629, taskName: 'Daily/Weekly/Ad-hoc Meetings', reason: 'Known Teamwork task mapping', confidence: 100 },
  32676546: { projectId: 966753, projectName: 'ASR | Dispatch Advice & Invoicing at Suffix Level', taskId: 32676546, taskName: 'Enhanced 901 for vendor dropships', reason: 'Known Teamwork task mapping', confidence: 100 },
  32199685: { projectId: 390351, projectName: 'BKC | Application Managed Services', taskId: 32199685, taskName: 'IDM', reason: 'Known Teamwork task mapping', confidence: 100 },
  33020261: { projectId: 390351, projectName: 'BKC | Application Managed Services', taskId: 33020261, taskName: 'QMS601 Endotoxin Supplement Page', reason: 'Known Teamwork task mapping', confidence: 100 },
  32200244: { projectId: 502827, projectName: 'BROWN | Application Managed Services', taskId: 32200244, taskName: 'IDM', reason: 'Known Teamwork task mapping', confidence: 100 },
  32768933: { projectId: 861413, projectName: 'DG | Education and Learning', taskId: 32768933, taskName: 'Infor U training', reason: 'Known Teamwork task mapping', confidence: 100 },
  32835935: { projectId: 951450, projectName: 'HJ | ERP Transformation Project', taskId: 32835935, taskName: 'HJ Output documents', reason: 'Known Teamwork task mapping', confidence: 100 },
  32165881: { projectId: 463320, projectName: 'IPC | Application Managed Services', taskId: 32165881, taskName: 'IDM', reason: 'Known Teamwork task mapping', confidence: 100 },
}

const MATCH_RULES: MatchRule[] = [
  {
    titleKeywords: ['asr api'],
    detailKeywords: ['mass changes', 'kitting'],
    projectId: 962004,
    projectName: 'ASR | API Mass Changes & Kitting Updates',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'ASR API / mass changes / kitting found in event details',
    confidence: 0,
    priority: 12,
  },
  {
    titleKeywords: ['shipment advice', 'dispatch advice', 'vendor dropship', 'suffix level', 'enhanced 901'],
    detailKeywords: ['shipment advice', 'dispatch advice', 'vendor dropship', 'suffix level', 'enhanced 901', '901'],
    taskKeywords: ['enhanced 901', 'vendor dropship'],
    projectId: 966753,
    projectName: 'ASR | Dispatch Advice & Invoicing at Suffix Level',
    taskId: 32676546,
    taskName: 'Enhanced 901 for vendor dropships',
    reason: 'ASR dispatch / 901 details found',
    confidence: 0,
    priority: 11,
  },
  {
    titleKeywords: ['asraymond', 'as raymond', 'asr weekly connect', 'asr scrum', 'asr connect'],
    detailKeywords: ['asraymond', 'as raymond', 'asr', 'weekly connect', 'scrum'],
    taskKeywords: ['weekly connect', 'scrum', 'meeting'],
    projectId: 956015,
    projectName: 'ASR | Application Managed Services',
    taskId: 32043629,
    taskName: 'Daily/Weekly/Ad-hoc Meetings',
    reason: 'ASR meeting details found',
    confidence: 0,
    priority: 7,
  },
  {
    titleKeywords: ['qms601', 'endotoxin supplement'],
    detailKeywords: ['qms601', 'endotoxin supplement', 'template modifications', 'output testing'],
    taskKeywords: ['qms601', 'endotoxin supplement'],
    projectId: 390351,
    projectName: 'BKC | Application Managed Services',
    taskId: 33020261,
    taskName: 'QMS601 Endotoxin Supplement Page',
    reason: 'QMS601 / endotoxin details found',
    confidence: 0,
    priority: 12,
  },
  {
    titleKeywords: ['berkshire corp', 'bkc'],
    detailKeywords: ['berkshire corp', 'bkc', 'qms', 'endotoxin', 'idm'],
    projectId: 390351,
    projectName: 'BKC | Application Managed Services',
    taskId: 32199685,
    taskName: 'IDM',
    reason: 'BKC / Berkshire details found',
    confidence: 0,
    priority: 8,
  },
  {
    titleKeywords: ['brownells', 'brown'],
    detailKeywords: ['brownells', 'brown', 'flxpoint', 'infor document management', 'idm', 'invoice', 'sow'],
    projectId: 502827,
    projectName: 'BROWN | Application Managed Services',
    taskId: 32200244,
    taskName: 'IDM',
    reason: 'Brownells details found',
    confidence: 0,
    priority: 8,
  },
  {
    titleKeywords: ['jpmc', 'phase ii'],
    detailKeywords: ['jpmc', 'phase ii', 'phase 2'],
    projectId: 959894,
    projectName: 'IP Corp | JPMC Phase II SOW',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'JPMC / Phase II details found',
    confidence: 0,
    priority: 12,
  },
  {
    titleKeywords: ['ipcorp', 'ip corp', 'factory track', 'ftk'],
    detailKeywords: ['ipcorp', 'ip corp', 'factory track', 'ftk', 'pms241pf', 'mp printer', 'shoptraveler', 'label', 'labels'],
    taskKeywords: ['factory track', 'label', 'mp printer', 'shoptraveler'],
    projectId: 463320,
    projectName: 'IPC | Application Managed Services',
    taskId: 32165881,
    taskName: 'IDM',
    reason: 'IPC / Factory Track details found',
    confidence: 0,
    priority: 8,
  },
  {
    titleKeywords: ['herff jones', 'hj ', 'hj-', 'hj:', 'erp transformation'],
    detailKeywords: ['herff jones', 'erp transformation', 'output documents', 'idm output', 'finance', 'cx idm'],
    taskKeywords: ['output documents', 'idm output'],
    projectId: 951450,
    projectName: 'HJ | ERP Transformation Project',
    taskId: 32835935,
    taskName: 'HJ Output documents',
    reason: 'Herff Jones / output document details found',
    confidence: 0,
    priority: 8,
  },
  {
    titleKeywords: ['ahern'],
    detailKeywords: ['ahern', 'qps601pf'],
    projectId: 861705,
    projectName: 'AHERN | Application Managed Services',
    taskId: 32008552,
    taskName: 'IDM',
    reason: 'Ahern details found',
    confidence: 0,
    priority: 7,
  },
  {
    titleKeywords: ['berkshire blanket', 'bkb'],
    detailKeywords: ['berkshire blanket', 'bkb'],
    projectId: 388354,
    projectName: 'BKB | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'BKB details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['champion', 'cpf'],
    detailKeywords: ['champion', 'cpf'],
    projectId: 390355,
    projectName: 'CPF | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Champion / CPF details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['custom truck', 'ctos'],
    detailKeywords: ['custom truck', 'ctos'],
    projectId: 923416,
    projectName: 'CTOS | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Custom Truck / CTOS details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['grosfillex', 'gfx'],
    detailKeywords: ['grosfillex', 'gfx'],
    projectId: 422590,
    projectName: 'GFX | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Grosfillex / GFX details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['mac papers', 'mpp'],
    detailKeywords: ['mac papers', 'mac papers and packaging', 'mpp'],
    projectId: 898506,
    projectName: 'MPP | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Mac Papers / MPP details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['macarthur', 'macar'],
    detailKeywords: ['macarthur', 'macar'],
    projectId: 862689,
    projectName: 'MACAR | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'MacArthur details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['sani marc'],
    detailKeywords: ['sani marc'],
    projectId: 882196,
    projectName: 'Sani Marc | Cloud Migration',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'Sani Marc details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['stratas', 'stratasfoods'],
    detailKeywords: ['stratas', 'stratasfoods', 'sfcu', 'stratas foods'],
    projectId: 928509,
    projectName: 'STRATAS | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'STRATAS details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['wencor'],
    detailKeywords: ['wencor', 'sublot'],
    projectId: 914508,
    projectName: 'WENCOR | Application Managed Services',
    taskId: 0,
    taskName: 'Select task after loading project tasks',
    reason: 'WENCOR details found',
    confidence: 0,
    priority: 6,
  },
  {
    titleKeywords: ['mes training', 'infor u'],
    detailKeywords: ['mes training', 'infor u', 'training', 'manufacturing training'],
    projectId: 861413,
    projectName: 'DG | Education and Learning',
    taskId: 32768933,
    taskName: 'Infor U training',
    reason: 'Training details found',
    confidence: 0,
    priority: 5,
  },
  {
    titleKeywords: ['teamwork', 'teamdesk', 'slack', 'jira'],
    detailKeywords: ['teamwork', 'teamdesk', 'slack', 'jira', 'admin'],
    projectId: 417162,
    projectName: 'DG | Internal Activities',
    taskId: 29936460,
    taskName: 'General Administrative Tasks',
    reason: 'Doppio admin details found',
    confidence: 0,
    priority: 3,
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

function toWeekInputValue(date: Date) {
  const copy = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const day = copy.getUTCDay() || 7
  copy.setUTCDate(copy.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(copy.getUTCFullYear(), 0, 1))
  const week = Math.ceil((((copy.getTime() - yearStart.getTime()) / 86400000) + 1) / 7)
  return `${copy.getUTCFullYear()}-W${String(week).padStart(2, '0')}`
}

function workWeekFromWeekInput(value: string) {
  const match = value.match(/^(\d{4})-W(\d{2})$/)
  if (!match) return currentWorkWeek()
  const year = Number(match[1])
  const week = Number(match[2])
  const jan4 = new Date(Date.UTC(year, 0, 4))
  const jan4Day = jan4.getUTCDay() || 7
  const monday = new Date(jan4)
  monday.setUTCDate(jan4.getUTCDate() - jan4Day + 1 + (week - 1) * 7)
  const friday = new Date(monday)
  friday.setUTCDate(monday.getUTCDate() + 4)
  return { start: monday.toISOString().slice(0, 10), end: friday.toISOString().slice(0, 10) }
}

function normalizeText(value?: string) {
  return (value || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

function eventTitleText(ev: EventItem) {
  return normalizeText([ev.title, ev.type].filter(Boolean).join(' '))
}

function eventDetailText(ev: EventItem) {
  return normalizeText([ev.description, ev._calendar_name].filter(Boolean).join(' '))
}

function eventText(ev: EventItem) {
  return normalizeText([ev.title, ev.description, ev.type, ev._calendar_name].filter(Boolean).join(' '))
}

function cleanDescription(description?: string) {
  if (!description) return 'No description provided.'
  return description.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() || 'No description provided.'
}

function keywordHits(text: string, keywords: string[] = []) {
  return keywords.filter(keyword => text.includes(keyword.toLowerCase()))
}

function suggestedFromKnownMappedTask(ev: EventItem): SuggestedMatch | null {
  const maybe = ev as EventItem & { mappedTaskIds?: unknown }
  if (!Array.isArray(maybe.mappedTaskIds)) return null
  for (const rawId of maybe.mappedTaskIds) {
    const taskId = Number(rawId)
    if (KNOWN_TASKS[taskId]) {
      return {
        ...KNOWN_TASKS[taskId],
        reason: `Already linked in Teamwork calendar to ${KNOWN_TASKS[taskId].taskName}`,
        confidence: 100,
      }
    }
  }
  return null
}

function scoreRule(rule: MatchRule, ev: EventItem) {
  const title = eventTitleText(ev)
  const details = eventDetailText(ev)
  const combined = eventText(ev)
  const titleHits = keywordHits(title, rule.titleKeywords)
  const detailHits = keywordHits(details, rule.detailKeywords)
  const taskHits = keywordHits(combined, rule.taskKeywords)
  let score = rule.priority || 0
  score += titleHits.length * 60
  score += detailHits.length * 50
  score += taskHits.length * 40

  // Prefer rules that can pick a concrete task over project-only suggestions.
  if (rule.taskId) score += 15

  return {
    score,
    hits: [...titleHits.map(h => `title: ${h}`), ...detailHits.map(h => `description: ${h}`), ...taskHits.map(h => `task clue: ${h}`)],
  }
}

function suggestForEvent(ev: EventItem): SuggestedMatch | null {
  const mapped = suggestedFromKnownMappedTask(ev)
  if (mapped) return mapped

  const ranked = MATCH_RULES
    .map(rule => ({ rule, ...scoreRule(rule, ev) }))
    .filter(result => result.score >= 55)
    .sort((a, b) => b.score - a.score)

  const top = ranked[0]
  if (!top) return null
  const { rule, score, hits } = top
  const confidence = Math.min(Math.round(score), 99)
  const reason = hits.length
    ? `${rule.reason}: ${hits.slice(0, 3).join(', ')}`
    : rule.reason

  return {
    projectId: rule.projectId,
    projectName: rule.projectName,
    taskId: rule.taskId,
    taskName: rule.taskName,
    reason: `${reason} · ${confidence}% confidence`,
    confidence,
  }
}

const STOP_WORDS = new Set([
  'the', 'and', 'for', 'with', 'from', 'this', 'that', 'ticket', 'submission',
  'medium', 'high', 'low', 'update', 'review', 'meeting', 'does', 'not', 'include',
])

function taskDisplayName(task: TeamworkTask) {
  return task.name || task.content || ''
}

function normalizeCode(code: string) {
  return code.toUpperCase().replace(/[^A-Z0-9]/g, '')
}

function extractCodes(text: string) {
  const matches = text.match(/\b[A-Z]{2,}[\s_-]*\d+[A-Z]?\b/gi) || []
  return Array.from(new Set(matches.map(normalizeCode)))
}

function meaningfulWords(text: string) {
  return normalizeText(text)
    .split(/[^a-z0-9]+/)
    .filter(word => word.length >= 3 && !STOP_WORDS.has(word))
}

function scoreTaskAgainstEvent(task: TeamworkTask, ev: EventItem) {
  const taskName = taskDisplayName(task)
  const taskText = normalizeText(taskName)
  const combined = eventText(ev)
  const eventCodes = extractCodes([ev.title, ev.description].filter(Boolean).join(' '))
  const taskCodes = extractCodes(taskName)
  const hits: string[] = []
  let score = 0

  for (const code of eventCodes) {
    if (taskCodes.includes(code) || normalizeCode(taskName).includes(code)) {
      score += 150
      hits.push(`code ${code}`)
    }
  }

  if (taskText && combined.includes(taskText)) {
    score += 120
    hits.push('full task title in event details')
  }

  const words = meaningfulWords(taskName)
  if (words.length) {
    const matchedWords = words.filter(word => combined.includes(word))
    const coverage = matchedWords.length / words.length
    if (coverage >= 0.75) {
      score += 90
      hits.push(`strong phrase overlap: ${matchedWords.slice(0, 4).join(', ')}`)
    } else if (coverage >= 0.45) {
      score += 55
      hits.push(`partial phrase overlap: ${matchedWords.slice(0, 4).join(', ')}`)
    }
  }

  return { score, hits }
}

function bestTaskSuggestion(ev: EventItem, projectTasks: TeamworkTask[]) {
  const ranked = projectTasks
    .map(task => ({ task, ...scoreTaskAgainstEvent(task, ev) }))
    .filter(result => result.score >= 80)
    .sort((a, b) => b.score - a.score)
  return ranked[0] || null
}

function refineSuggestionWithTasks(ev: EventItem, suggestion: SuggestedMatch | null, projectTasks: TeamworkTask[] = []): SuggestedMatch | null {
  if (!suggestion) return null
  if (suggestion.taskId) return suggestion
  const best = bestTaskSuggestion(ev, projectTasks)
  if (!best) return suggestion
  const taskName = taskDisplayName(best.task)
  const taskReason = best.hits.length ? best.hits.slice(0, 2).join(', ') : 'best task title match'
  const confidence = Math.min(Math.max(suggestion.confidence, 80) + Math.min(best.score, 150) / 10, 99)
  return {
    ...suggestion,
    taskId: best.task.id,
    taskName,
    reason: `${suggestion.reason}; task matched from ${taskReason} · ${Math.round(confidence)}% confidence`,
    confidence: Math.round(confidence),
  }
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
  const [weeklyActualLoggedMinutes, setWeeklyActualLoggedMinutes] = useState(0)
  const [weeklyLoggedMinutes, setWeeklyLoggedMinutes] = useState(0)
  const [weeklyUnavailableMinutes, setWeeklyUnavailableMinutes] = useState(0)
  const [weeklyPersonalCommitmentMinutes, setWeeklyPersonalCommitmentMinutes] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<'all' | 'matched' | 'unmatched'>('all')
  const [matches, setMatches] = useState<Record<string, MatchEntry>>({})
  const [confirmedMatches, setConfirmedMatches] = useState<Record<string, MatchEntry>>({})
  const [taskSearches, setTaskSearches] = useState<Record<string, string>>({})
  const [projects, setProjects] = useState<TeamworkProject[]>([])
  const [tasks, setTasks] = useState<Record<number, TeamworkTask[]>>({})
  const [loadingTasks, setLoadingTasks] = useState<Record<number, boolean>>({})
  const [error, setError] = useState('')
  const [actionStatus, setActionStatus] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [runningFiller, setRunningFiller] = useState(false)
  const runningFillerRef = useRef(false)
  const autoLoadedRef = useRef(false)
  const selectedWeek = useMemo(() => toWeekInputValue(new Date(`${start}T12:00:00`)), [start])

  const loadTasksForProject = useCallback(async (projectId: number): Promise<TeamworkTask[]> => {
    if (tasks[projectId]) return tasks[projectId]
    if (loadingTasks[projectId]) return []
    setLoadingTasks(prev => ({ ...prev, [projectId]: true }))
    try {
      const taskList = await fetchTasks(projectId)
      setTasks(prev => ({ ...prev, [projectId]: taskList }))
      return taskList
    } catch {
      setTasks(prev => ({ ...prev, [projectId]: [] }))
      return []
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
      const [data, dailyTotals] = await Promise.all([
        fetchEvents(start, end),
        fetchTimesheetTotals(start, end),
      ])
      const loadedEvents = data.events || []
      const loadedLoggedMinutes = Object.values(dailyTotals.dailyTotals).reduce((total, minutes) => total + Number(minutes || 0), 0)
      const loadedUnavailableMinutes = Object.values(dailyTotals.unavailableDailyTotals).reduce((total, minutes) => total + Number(minutes || 0), 0)
      const loadedCreditedMinutes = Object.values(dailyTotals.creditedDailyTotals).reduce((total, minutes) => total + Number(minutes || 0), 0)
      const loadedPersonalCommitmentMinutes = Object.values(dailyTotals.personalCommitmentUnloggedDailyTotals).reduce((total, minutes) => total + Number(minutes || 0), 0)
      const initialMatches: Record<string, MatchEntry> = {}
      const suggestedProjectIds = new Set<number>()
      const baseSuggestions: Record<string, SuggestedMatch> = {}

      for (const ev of loadedEvents) {
        const suggestion = suggestForEvent(ev)
        if (suggestion) {
          baseSuggestions[ev.id] = suggestion
          suggestedProjectIds.add(suggestion.projectId)
        }
      }

      const loadedTaskEntries = await Promise.all(
        Array.from(suggestedProjectIds).map(async projectId => [projectId, await loadTasksForProject(projectId)] as const)
      )
      const loadedTaskMap = Object.fromEntries(loadedTaskEntries) as Record<number, TeamworkTask[]>

      for (const ev of loadedEvents) {
        const baseSuggestion = baseSuggestions[ev.id]
        const refinedSuggestion = refineSuggestionWithTasks(
          ev,
          baseSuggestion || null,
          baseSuggestion ? loadedTaskMap[baseSuggestion.projectId] || tasks[baseSuggestion.projectId] || [] : []
        )
        if (refinedSuggestion) {
          initialMatches[ev.id] = {
            eventId: ev.id,
            projectId: refinedSuggestion.projectId,
            taskId: refinedSuggestion.taskId || null,
          }
        }
      }

      setEvents(loadedEvents)
      setWeeklyActualLoggedMinutes(loadedLoggedMinutes)
      setWeeklyLoggedMinutes(loadedCreditedMinutes)
      setWeeklyUnavailableMinutes(loadedUnavailableMinutes)
      setWeeklyPersonalCommitmentMinutes(loadedPersonalCommitmentMinutes)
      setMatches(initialMatches)
      setConfirmedMatches({})
      setTaskSearches({})
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [end, loadTasksForProject, start])

  useEffect(() => {
    if (autoLoadedRef.current) return
    autoLoadedRef.current = true
    void handleLoad()
  }, [handleLoad])

  const handleWeekChange = (value: string) => {
    const range = workWeekFromWeekInput(value)
    setStart(range.start)
    setEnd(range.end)
  }

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
    setTaskSearches(prev => ({ ...prev, [eventId]: '' }))
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
    setTaskSearches(prev => {
      const next = { ...prev }
      delete next[eventId]
      return next
    })
  }

  const handleSubmitMatched = async () => {
    const entries = events
      .map(ev => ({ ev, match: confirmedMatches[ev.id] }))
      .filter(({ ev, match }) => match?.projectId && match?.taskId && !hasMappedTask(ev))
      .map(({ ev, match }) => ({
        eventId: ev.id,
        calendarId: ev.calendarId || 1306,
        title: ev.title,
        description: ev.description,
        start: ev.start,
        duration_minutes: ev.duration_minutes,
        projectId: Number(match!.projectId),
        taskId: Number(match!.taskId),
        mappedTaskIds: ev.mappedTaskIds,
      }))
    if (entries.length === 0) {
      setActionStatus('No newly matched entries to submit. Click Match on entries first.')
      return
    }
    setSubmitting(true)
    setActionStatus('Submitting matched entries…')
    try {
      const result = await submitMatchedEntries(entries)
      setActionStatus(`Submitted ${result.created.length}; skipped ${result.skipped.length}; errors ${result.errors.length}.`)
      await handleLoad()
    } catch (e) {
      setActionStatus((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleTimesheetFiller = async () => {
    if (runningFillerRef.current) {
      setActionStatus('Time Sheet Filler is already running. Ignoring duplicate click.')
      return
    }
    runningFillerRef.current = true
    setRunningFiller(true)
    setActionStatus('Creating timesheet filler entries…')
    try {
      const result = await runTimesheetFiller(start, end)
      setActionStatus(result.message || `Timesheet filler: created ${result.created.length}; skipped ${result.skipped.length}.`)
      await handleLoad()
    } catch (e) {
      setActionStatus((e as Error).message)
    } finally {
      runningFillerRef.current = false
      setRunningFiller(false)
    }
  }

  const isMatched = useCallback((ev: EventItem) => {
    return Boolean(confirmedMatches[ev.id]?.projectId && confirmedMatches[ev.id]?.taskId) || hasMappedTask(ev)
  }, [confirmedMatches])

  const matchedCount = events.filter(isMatched).length
  const importedEventMinutes = events.reduce((total, ev) => total + (ev.duration_minutes || 0), 0)
  const weeklyRemainingMinutes = Math.max(WORK_WEEK_TARGET_MINUTES - weeklyLoggedMinutes, 0)
  const weeklyOverageMinutes = Math.max(weeklyLoggedMinutes - WORK_WEEK_TARGET_MINUTES, 0)
  const weeklyProgressPercent = Math.min((weeklyLoggedMinutes / WORK_WEEK_TARGET_MINUTES) * 100, 100)

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
    return projects.find(p => p.id === projectId)?.name || MATCH_RULES.find(s => s.projectId === projectId)?.projectName || Object.values(KNOWN_TASKS).find(s => s.projectId === projectId)?.projectName || ''
  }

  const taskName = (projectId?: number | null, taskId?: number | null) => {
    if (!projectId || !taskId) return ''
    return tasks[projectId]?.find(t => t.id === taskId)?.name || tasks[projectId]?.find(t => t.id === taskId)?.content || KNOWN_TASKS[taskId]?.taskName || MATCH_RULES.find(s => s.taskId === taskId)?.taskName || ''
  }

  const filterTasks = (projectTasks: TeamworkTask[], search: string) => {
    const query = normalizeText(search)
    if (!query) return projectTasks
    const terms = query.split(/\s+/).filter(Boolean)
    return projectTasks.filter(task => {
      const haystack = normalizeText(`${task.id} ${taskDisplayName(task)}`)
      return terms.every(term => haystack.includes(term))
    })
  }

  return (
    <div className="card matching-card">
      <h1 className="card-header">Matching</h1>

      <div className="controls-row matching-controls">
        <div className="field-group week-field">
          <label>Week</label>
          <input type="week" value={selectedWeek} onChange={e => handleWeekChange(e.target.value)} />
          <span className="week-range-hint">{formatDate(start)} to {formatDate(end)}</span>
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
        <button className="btn btn-warning load-events-btn" onClick={handleTimesheetFiller} disabled={runningFiller || loading}>
          {runningFiller ? 'Running…' : 'Time Sheet Filler'}
        </button>
        <button className="btn btn-primary load-events-btn" onClick={handleSubmitMatched} disabled={submitting || loading}>
          {submitting ? 'Submitting…' : 'Submit Matched'}
        </button>
      </div>

      <div className="week-progress-card">
        <div className="week-progress-header">
          <div>
            <span className="week-progress-label">Logged + unavailable this week</span>
            <strong>{formatHours(weeklyLoggedMinutes)} / 40.0h</strong>
            <small className="week-progress-detail">{formatHours(weeklyActualLoggedMinutes)} logged + {formatHours(weeklyUnavailableMinutes)} unavailable · {formatHours(importedEventMinutes)} imported calendar time</small>
            {weeklyPersonalCommitmentMinutes > 0 && (
              <small className="week-progress-warning">
                {formatHours(weeklyPersonalCommitmentMinutes)} personal commitment not logged as unavailable yet
              </small>
            )}
          </div>
          <div className={weeklyRemainingMinutes > 0 ? 'week-progress-short' : weeklyOverageMinutes > 0 ? 'week-progress-over' : 'week-progress-complete'}>
            {weeklyRemainingMinutes > 0 ? `${formatHours(weeklyRemainingMinutes)} short` : weeklyOverageMinutes > 0 ? `${formatHours(weeklyOverageMinutes)} over 40h` : '40h met'}
          </div>
        </div>
        <div className="week-progress-track" aria-label="40 hour weekly progress">
          <div className={`week-progress-fill ${weeklyOverageMinutes > 0 ? 'week-progress-fill-over' : ''}`} style={{ width: `${weeklyProgressPercent}%` }} />
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}
      {actionStatus && <p className="action-status-text">{actionStatus}</p>}

      <div className="status-text">
        {events.length} events · {matchedCount} matched · {events.length - matchedCount} unmatched
      </div>

      {events.length === 0 && !loading && !error && (
        <div className="empty-state">
          <p>Current work week loads automatically. Use the <strong>Week</strong> picker above to switch weeks.</p>
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
          const baseSuggestion = suggestForEvent(ev)
          const suggestion = refineSuggestionWithTasks(
            ev,
            baseSuggestion,
            baseSuggestion ? tasks[baseSuggestion.projectId] || [] : []
          )
          const projectTasks = selectedProject ? tasks[selectedProject] || [] : []
          const taskSearch = taskSearches[ev.id] || ''
          const filteredProjectTasks = filterTasks(projectTasks, taskSearch)
          const isTasksLoading = selectedProject ? loadingTasks[selectedProject] : false
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
                <div className="task-picker">
                  <input
                    type="search"
                    value={taskSearch}
                    placeholder="Search tasks…"
                    disabled={!selectedProject || isTasksLoading}
                    onChange={e => setTaskSearches(prev => ({ ...prev, [ev.id]: e.target.value }))}
                  />
                  <select
                    value={selectedTask ?? ''}
                    onChange={e => handleSelectTask(ev.id, e.target.value ? Number(e.target.value) : null)}
                    disabled={!selectedProject || isTasksLoading}
                  >
                    <option value="">{isTasksLoading ? 'Loading tasks…' : taskSearch ? `— ${filteredProjectTasks.length} matching tasks —` : '— Select Task —'}</option>
                    {selectedTask && !filteredProjectTasks.some(t => t.id === selectedTask) && selectedTaskName && (
                      <option value={selectedTask}>{selectedTaskName}</option>
                    )}
                    {filteredProjectTasks.map(t => (
                      <option key={t.id} value={t.id}>{t.name || t.content}</option>
                    ))}
                  </select>
                </div>
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
