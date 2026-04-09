# Spec: Team Domains (Bounded Context Sessions)

**Branch:** `feature/team-domains`
**Author:** gosmonso
**Status:** Draft

---

## Problem

CAO sessions are context-free. When you `cao launch --agents code_supervisor`, the agent starts with no domain awareness — it doesn't know which project it's working on, which steering docs apply, or which agents are relevant. Users manually provide this context every time.

In multi-domain setups (e.g., OctopusAnalytics, BidWorkspace, BlockSimulator), this means:
- Repeated context-setting at session start
- Wrong agents loaded for the domain
- No working directory scoping
- No domain-specific steering/memory isolation

## Solution: Teams

A **team** is a named bounded context that bundles:

| Property | Description |
|----------|-------------|
| `name` | Unique identifier (e.g., `octopus`) |
| `display_name` | Human-readable (e.g., "Octopus Analytics") |
| `home` | Working directory for all sessions (e.g., `~/OctopusContactAnalytics`) |
| `agents` | Default agent profiles to load (e.g., `[code_supervisor, developer]`) |
| `steering` | Paths to domain-specific steering docs to inject |
| `provider` | Default provider override (optional) |
| `env` | Extra environment variables for all terminals in this team |

### Team Definition File

Teams are defined as markdown files with YAML frontmatter (same pattern as agent profiles and flows):

```markdown
---
name: octopus
display_name: Octopus Analytics
home: ~/OctopusContactAnalytics
agents:
  - code_supervisor
  - developer
steering:
  - ~/.kiro/steering/domains/octopus.md
  - ~/.kiro/steering/domains/analytics.md
provider: kiro_cli
env:
  OCTOPUS_ENV: beta
---

Contact analytics for Amazon Freight support. Ingests Contact Lens data,
enriches with order/VRID context, classifies threads via LLM.

Key packages: OctopusContactAnalytics, TrailblazerAIApi (octopus lambdas),
TrailblazerAI (octopus pages).
```

The body text becomes the **team context** — injected into the supervisor's system prompt so every agent in the team starts with domain awareness.

### Storage

```
~/.cao/teams/
├── octopus.md
├── bid-workspace.md
└── block-simulator.md
```

Follows the same pattern as `~/.cao/agent-store/` for agent profiles.

## CLI Changes

### `cao team` subcommand

```bash
# Manage teams
cao team add octopus.md          # Install a team definition
cao team list                     # List all teams
cao team show octopus             # Show team details
cao team remove octopus           # Remove a team
```

### `cao launch --team`

```bash
cao launch --team octopus
# Equivalent to:
#   cd ~/OctopusContactAnalytics
#   cao launch --agents code_supervisor --provider kiro_cli
#   + injects steering docs + team context into supervisor prompt
#   + tags session with team name
```

### Interactive team picker

When `cao launch` is called without `--agents` or `--team`:

```
$ cao launch

Select a team:
  1. octopus        — Octopus Analytics (~/OctopusContactAnalytics)
  2. bid-workspace  — Bid Workspace (~/Documents/.../TrailblazerAI)
  3. block-sim      — Block Simulator (~/Documents/.../TrailblazerAI)
  4. (none)         — Launch without a team

Team [1-4]:
```

This is the "which team am I spawning?" prompt.

## API Changes

### Session model

Add `team` field to `Session`:

```python
class Session(BaseModel):
    id: str
    name: str
    status: SessionStatus
    team: Optional[str] = None  # NEW — team name, None for unscoped sessions
```

### Create session endpoint

`POST /sessions` gains optional `team` query param. When provided:
1. Load team definition from `~/.cao/teams/{team}.md`
2. Set `working_directory` to team's `home`
3. Resolve `agent_profile` from team's `agents[0]` (supervisor)
4. Inject team steering + context into the agent's prompt
5. Set `team` on the session for filtering/display

### List sessions

`GET /sessions` gains optional `?team=octopus` filter.

### Handoff/Assign

When a supervisor in a team-scoped session calls `handoff` or `assign`, the spawned worker:
- Inherits the team context (steering docs, env vars, working directory)
- Gets the team's body text prepended to its task message
- Is tagged with the same team name

## MCP Server Changes

The `handoff` and `assign` tools gain an optional `team` parameter. When omitted, they inherit from the calling terminal's session team (the common case).

## Web UI Changes

- Session list shows team badge/tag
- Team filter dropdown in session list
- Team management page (add/edit/remove team definitions)

## Data Flow

```
cao launch --team octopus
    │
    ▼
Load ~/.cao/teams/octopus.md
    │
    ├─ home: ~/OctopusContactAnalytics  →  working_directory
    ├─ agents: [code_supervisor]         →  agent_profile
    ├─ steering: [octopus.md, ...]       →  prepend to agent prompt
    ├─ body text                         →  prepend to agent prompt
    ├─ provider: kiro_cli                →  provider
    └─ env: {OCTOPUS_ENV: beta}          →  terminal env vars
    │
    ▼
POST /sessions?team=octopus&agent_profile=code_supervisor&...
    │
    ▼
Session created with team=octopus
    │
    ▼
Supervisor calls handoff(agent_profile="developer", ...)
    │
    ▼
Worker inherits team context automatically
```

## Implementation Plan

### Phase 1: Core (MVP)
1. Team model + YAML parsing (reuse frontmatter pattern from agent profiles)
2. `~/.cao/teams/` storage directory
3. `cao team add|list|show|remove` CLI commands
4. `cao launch --team` with working directory + agent resolution
5. Session model `team` field + API filter
6. Team context injection into supervisor prompt

### Phase 2: Inheritance
7. Handoff/assign team inheritance (workers get team context)
8. Team env var injection into terminals
9. Steering doc injection (read files, prepend to prompt)

### Phase 3: UX Polish
10. Interactive team picker on bare `cao launch`
11. Web UI team badges + filter
12. `cao team init` — scaffold a team definition interactively

## Non-Goals (v1)

- Team-scoped memory isolation (kiro-mem already has domain tags)
- Team-level permissions/RBAC
- Remote team definitions (URL-based, like agent profiles support)
- Multi-team sessions (one session = one team)

## Open Questions

1. Should `cao launch --team` auto-start `cao-server` if not running?
2. Should teams support a `flows` key to auto-register team-specific flows?
3. Should the team picker remember the last-used team?
