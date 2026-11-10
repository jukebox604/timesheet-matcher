// An explicit client label at the beginning of an event title is stronger
// evidence than generic words (such as "invoice") in existing keyword rules.
const CLIENT_ALIASES = {
  ASRAYMOND: 'ASR',
  HERFFJONES: 'HJ',
  BERKSHIRECORP: 'BKC',
  BROWNELLS: 'BROWN',
  MACPAPERS: 'MPP',
  CUSTOMTRUCK: 'CTOS',
}

function normalize(value) {
  return String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
}

function projectLabel(name) {
  return String(name || '').replace(/^\*+\s*/, '').split('|')[0].trim()
}

/** Return a project, an ambiguous marker, or null when no explicit label exists. */
export function matchProjectPrefix(title, projects) {
  const label = String(title || '').match(/^\s*([A-Za-z][A-Za-z0-9 .&'/-]{1,49})\s*:\s*\S/)
  if (!label || !Array.isArray(projects)) return null
  const rawCode = normalize(label[1])
  const code = CLIENT_ALIASES[rawCode] || rawCode
  const candidates = projects.filter(project => normalize(projectLabel(project.name)) === code)
  if (!candidates.length) return null

  let project = candidates[0]
  if (candidates.length > 1) {
    const subject = normalize(String(title).slice(label[0].indexOf(':') + label.index + 1))
    const explicit = candidates.filter(candidate => {
      const suffix = normalize(String(candidate.name).split('|').slice(1).join('|'))
      return suffix.length >= 5 && subject.includes(suffix)
    })
    if (explicit.length === 1) project = explicit[0]
    else {
      const managed = candidates.filter(candidate => normalize(candidate.name).includes('APPLICATIONMANAGEDSERVICES'))
      if (managed.length !== 1) return { ambiguous: true, label: label[1].trim() }
      project = managed[0]
    }
  }
  return { projectId: project.id, projectName: project.name, label: label[1].trim() }
}
