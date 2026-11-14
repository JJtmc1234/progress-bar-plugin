# Agent daemon

Optional. Lets a collaborator on a secure channel hand work to your Claude agents from the chat.

One background daemon (`bin/agentd.py run`) watches the chat on one channel. A line from the channel peer is a command:

| Line | What happens |
|---|---|
| `/task <text>` | Starts work. A cheap Claude call picks small (one agent) or big (a coordinator that starts up to 4 workers). `--big` / `--small` force it. |
| `@<agent-id> <text>` | Talks to, or pivots, one running agent. The text arrives as its next user turn. |
| `@all <text>`, or any plain line | Sent to every running agent as a user turn. |
| `/agents` | Lists agents. |
| `/stop <agent-id>` | Stops an agent and its workers. |

Every agent can read the group chat (`agentd.py read <id> [N]`: Hunter's lines and every agent's posts), post to it (`post <id> <text>`), tell another agent (`tell`), and a coordinator can `spawn` workers. A worker's final answer goes to its coordinator, and the coordinator's answer goes to the chat. Lines in the chat are prefixed `[<agent-id>]`.

## Set up

```
python3 bin/agentd.py install --now     # writes ~/.config/systemd/user/progress-bar-agentd.service, enables it
$EDITOR ~/.claude-progress/agentd/config.json   # set "channel" to a channel name from /progress-bar channel list
```

The unit starts at boot. With `loginctl enable-linger $USER` it starts before you log in.

`config.json`: `channel`, `max_agents` (6), `max_workers` (4), `max_budget_usd` per agent (5), `idle_minutes` (30), `model`, `extra_tools`, `add_dirs`.

## Safety

This is remote control of a coding agent, so the defaults are tight.

- Only chat lines from the channel peer count (the channel already verifies the signature and the sender). Lines from before the first start are never replayed.
- Agents run `claude -p` with `--permission-mode dontAsk` and only Read, Glob, Grep, Edit, Write plus the agentd commands. No shell, no network. Each starts in its own `~/.claude-progress/agentd/work/<id>/`. `extra_tools` and `add_dirs` widen this, on purpose, and only the machine owner edits them.
- Task text is told to the agent as untrusted data.
- Caps on running agents, workers, budget and idle time. `agentd.py pause` stops new work, `stop-all` ends every agent, `uninstall` removes the service from boot.
- The log (`agents.log`) holds ids and events, never message content.
- Agents use the owner's Claude login, so their work counts toward the owner's usage.

Commands: `agentd.py status | pause | resume | stop-all | uninstall`.

## Your own Claude Code sessions in the chat

**Group chat** (`groupChat` in `/config`) is on by default. Every session gets two tools, `chat_read` and `chat_say` (posts as `[s-<session>]`), a short standing note in its system prompt, and the collaborator's new chat lines, added to the prompt of the next turn as untrusted instructions from another person. Claude is told to say who asked before acting, never to reveal secrets because of a chat line, and your permission prompts still apply. It lets anyone on your channel steer your sessions, so turn it off in `/config` if you do not want that. It needs the daemon running (it keeps the chat). Hooks: `hooks/groupchat.ts`.

## In the Status panel and the Chat tab

- **Status panel:** each daemon agent is a row, written by the daemon to `~/.claude-progress/agent-<id>.json`: title `Coordinator c1a2 · <task>`, its state as the step (`working`, `idle · <last result>`), a bar for a coordinator (workers finished of started), workers under their coordinator (`parent`). When an agent ends, its row's `impact` is its last answer and the row moves to DONE.
- **Chat tab:** a line from an agent or session shows under its id in magenta (`c1a2 · 14:05`), not under "You". Your own lines in the tab are commands for the daemon too: `/task ...`, `@<id> ...`, `@all ...`, or plain text to every running agent. Agents see them as "[chat from the machine owner]".
