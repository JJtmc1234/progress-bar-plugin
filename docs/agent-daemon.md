# Agent daemon

Optional. Lets a collaborator on a secure channel hand work to your Claude agents from the chat.

One background daemon (`bin/agentd.py run`) watches the chat on one channel. A line from the channel peer is a command:

| Line | What happens |
|---|---|
| `/task <text>` | Starts work. A cheap Claude call picks small (one agent) or big (a coordinator that starts up to 4 workers). `--big` / `--small` force it. |
| `@<agent-id> <text>` | Talks to, or pivots, a running agent. The text arrives as its next user turn. |
| `/agents` | Lists agents. |
| `/stop <agent-id>` | Stops an agent and its workers. |

Every agent can post to the same chat (`agentd.py post <id> <text>`), tell another agent (`tell`), and a coordinator can `spawn` workers. A worker's final answer goes to its coordinator, and the coordinator's answer goes to the chat. Lines in the chat are prefixed `[<agent-id>]`.

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
