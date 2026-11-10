import type { TeamworkProject } from './timesheet'

export type PrefixMatch =
  | { projectId: number; projectName: string; label: string; ambiguous?: never }
  | { ambiguous: true; label: string; projectId?: never; projectName?: never }
  | null

export function matchProjectPrefix(title: string | undefined, projects: TeamworkProject[]): PrefixMatch
