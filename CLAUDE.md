# Git-Claw v4 — Cocapn Git-Agent TUI

## What This Is
A terminal-based coding agent forked from CheetahClaws, rebuilt as a Cocapn fleet vessel.
Commands its own build, talks to GitHub Copilot and MCP extensions, the human watches.

## Quick Start
```bash
pip install rich httpx openai anthropic
python gitclaw.py                          # Interactive REPL
python gitclaw.py -p "analyze this repo"   # One-shot
python gitclaw.py --accept-all -p "fix the bug in main.py"  # Auto-approve
```

## Architecture
- **gitclaw.py** — Main entry point, TUI REPL, captain system prompt, permission gates
- **agent.py** — Core agent loop (from CheetahClaws) — provider-agnostic streaming
- **providers.py** — Multi-provider support (DeepSeek, OpenAI, Anthropic, Ollama, etc.)
- **tools.py** — Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
- **tool_registry.py** — Tool schema registration for function calling
- **compaction.py** — Auto-summarize when approaching token limits
- **memory/** — Keeper memory system (JSONL with keyword search)
- **mcp/** — MCP client for extension commanding

## Captain/Admiral Paradigm
- **Captain** (this agent) auto-approves reads, executes safe bash
- **Admiral** (human) approves writes, edits, and dangerous commands
- `/approve on` — give Captain full control (Admiral watches)
- `/approve off` — back to asking on writes
- `--accept-all` — CLI flag for unattended mode

## Key Commands
| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/status` | Tokens, turns, memory count |
| `/memory [query]` | Search keeper memory |
| `/memory save` | Save insight with tags |
| `/equipment` | Show loaded equipment |
| `/mcp add <name> <cmd>` | Connect MCP server |
| `/plan <file>` | Enter plan mode (writes blocked) |
| `/plan done` | Exit plan mode |
| `/git status/diff/log` | Quick git info |
| `/approve on/off` | Toggle approval mode |
| `/cost` | Show API cost estimate |

## Equipment
Loaded from `vessel.json` in the working directory. Equipment modules change
what the Captain can perceive — the way glasses change what you see.

## Config
Stored at `~/.git-claw/config.json`. Set model, permissions, MCP servers.
Set API keys via environment: `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`.

## Memory
Keeper memory at `~/.git-claw/memory/keeper.jsonl`. Each entry has:
- `ts` — timestamp
- `insight` — the remembered thing
- `tags` — searchable keywords

## Codespaces
This repo has a `.devcontainer/devcontainer.json`. Fork → Codespaces → agent is alive.
GitHub Copilot Chat extension included for dual-agent workflows.

## Provider Support
- DeepSeek (deepseek-chat, deepseek-reasoner)
- OpenAI (gpt-4o, gpt-4o-mini)
- Anthropic (claude-sonnet-4, claude-opus-4)
- Ollama (local models)
- Any OpenAI-compatible endpoint via `custom/` prefix

## Permission Modes
| Mode | Reads | Writes |
|------|-------|--------|
| `auto` | Auto-approve | Ask Admiral |
| `manual` | Ask | Ask |
| `accept-all` | Auto | Auto |
| `plan` | Auto | Blocked (plan file only) |

## Brand
- Emoji: 🦁 (Cheetah → Claw → Lion)
- Color: #22d3ee (cyan)
- Based on CheetahClaws v3.05 by SafeRL-Lab
- Rebuilt as Cocapn vessel by Superinstance & Lucineer (DiGennaro et al.)
