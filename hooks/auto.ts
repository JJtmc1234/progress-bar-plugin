import type { EngineInterface } from 'claude-code'

import { slug } from './render'
import { ownerOf, reportBody } from './report'
import { sessionKeyOf } from './route'
import { oneLine } from './waiting'

// Works with no setup (autoReport, on by default):
// 1. A short standing instruction in the system prompt, so Claude reports multi-step work with progress_report
//    without being asked. It is one constant section after the cache boundary, sent once per conversation.
// 2. A zero-model fallback: a main-session turn that runs 30 s or more with 3 or more tool calls shows as a working
//    row titled from the prompt, until the turn ends. A turn that calls progress_report, or keeps a task list (its
//    own bar), shows no fallback row. A quick edit shows nothing.

export const REPORT_SECTION_ID = 'progress-bar:auto-report'

export const REPORT_SECTION = [
  '# Progress bar',
  'The person watches a live Status panel. For any task with 3 or more steps, or likely to run over a minute, call the progress_report tool (mcp__progress-bar__progress_report, load it with ToolSearch if it is deferred) without being asked:',
  '- At the start: a plain title naming the outcome, done 0, total, and steps (a few words each).',
  '- After each step: done and step.',
  '- At the end: finished true with impact (what changed, with the key number).',
  'When you launch a subagent, give it a slug (the slug of its description) in its brief and ask it to report under that slug. Skip this for quick answers and one-step edits.',
].join('\n')

type Section = { id: string; text: string; scope: 'shared' | 'session' }

/** The system prompt's sections with the standing instruction added at the end, once. `bare` prompts get none. */
export function withReportSection<S extends Section>(sections: readonly S[], traits: readonly string[] = []): S[] {
  if (traits.includes('bare') || sections.some(s => s.id === REPORT_SECTION_ID)) return [...sections]
  return [...sections, { id: REPORT_SECTION_ID, text: REPORT_SECTION, scope: 'session' } as S]
}

/** How long a turn runs, and how many tool calls it makes, before it shows as a row. */
export const TURN_MIN_MS = 30_000
export const TURN_MIN_TOOLS = 3

/** The main session's current turn: its title, start, tool calls and whether something else already shows it. */
export type Turn = { title: string; startedAt: number; tools: number; lastTool: string; lastWhat: string; reported: boolean; taskBar: boolean; shown: boolean }

export const turn: Turn = { title: '', startedAt: 0, tools: 0, lastTool: '', lastWhat: '', reported: false, taskBar: false, shown: false }

/** A row title from the person's prompt: its first line, one space between words, at most 60 characters. */
export function turnTitle(text: string): string {
  const first = text.split('\n').map(l => l.trim()).find(Boolean) ?? ''
  return oneLine(first, 60)
}

/** Whether the turn should show as a row: long enough, busy enough, and shown by nothing else. */
export function turnDue(t: Turn, now: number): boolean {
  return t.startedAt > 0 && !t.reported && !t.taskBar && t.tools >= TURN_MIN_TOOLS && now - t.startedAt >= TURN_MIN_MS
}

/** The row's step: the last tool call and how many the turn made. */
export function turnStep(t: Turn): string {
  const last = [t.lastTool, t.lastWhat].filter(Boolean).join(' ')
  return `${last ? `${last}, ` : ''}${t.tools} tool call${t.tools === 1 ? '' : 's'}`
}

/** The row's file name: the project folder's name, then this session's key, so two sessions never share one. */
export function turnSlug(cwd: string, session: string): string {
  const base = slug(cwd.replace(/\/+$/, '').split('/').pop() ?? '') || 'session'
  return `working-${base}-${sessionKeyOf(session).slice(0, 4) || 'main'}`
}

/** Rows the plugin writes for the session itself (a turn, a shell): never a subagent's own progress file. */
export const sessionRow = (name: string) => name.startsWith('working-') || name.startsWith('shell-')

let on = true
export const setAutoReport = (v: boolean) => { on = v }
export const autoReportOn = () => on

async function pathOf($: EngineInterface, h: string): Promise<string> {
  const o = await ownerOf($)
  return `${h}/.claude-progress/${turnSlug(o.cwd, o.session)}.json`
}

/** A new main-session turn: its title from the prompt (a turn with no prompt keeps the last one). */
export async function startTurn($: EngineInterface, h: string, text: string) {
  if (turn.shown && h) await $.process.run(['rm', '-f', await pathOf($, h)]).catch(() => undefined)
  Object.assign(turn, { title: turnTitle(text) || turn.title || 'Working', startedAt: await $.clock.now(), tools: 0, lastTool: '', lastWhat: '', reported: false, taskBar: turn.taskBar, shown: false })
}

/** A main-session tool call. */
export function countTool(tool: string, what: string) {
  if (!turn.startedAt) return
  turn.tools += 1
  turn.lastTool = tool.startsWith('mcp__') ? tool.split('__').pop() ?? tool : tool
  turn.lastWhat = what
}

/** Writes the turn's row when it is due (rewritten each poll, so it stays fresh), or removes it when it is not. */
export async function tickTurn($: EngineInterface, h: string) {
  if (!on || !h || !turn.startedAt) return
  const due = turnDue(turn, await $.clock.now())
  if (!due && !turn.shown) return
  const path = await pathOf($, h)
  if (!due) { turn.shown = false; await $.process.run(['rm', '-f', path]).catch(() => undefined); return }
  turn.shown = true
  await $.fs.write(path, JSON.stringify(reportBody({ title: turn.title, step: turnStep(turn) }, await ownerOf($), turn.startedAt))).catch(() => undefined)
}

/** The turn ended: its row goes. */
export async function endTurn($: EngineInterface, h: string) {
  const shown = turn.shown
  Object.assign(turn, { startedAt: 0, tools: 0, reported: false, shown: false })
  if (shown && h) await $.process.run(['rm', '-f', await pathOf($, h)]).catch(() => undefined)
}
