# git-claw

![Cocapn Vessel](https://img.shields.io/badge/cocapn-vessel-purple) ![License](https://img.shields.io/badge/license-MIT-blue)

**The terminal git-agent — Captain/Admiral paradigm, 18 tools, TUI.**

Forked from CheetahClaws (22.5K lines), rebuilt with Cocapn fleet protocol.

Part of the [Cocapn fleet](https://github.com/Lucineer).

## Features
- 18 tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, and more
- Captain/Admiral paradigm — agent is Captain, human is Admiral
- Keeper memory system (hot/warm/cold tiers, KV-backed)
- Plan mode for complex multi-step tasks
- Equipment loading from vessel.json
- MCP bridge for external tool integration
- Codespaces-ready with devcontainer
- Multi-provider streaming (DeepSeek, OpenAI, Anthropic, SiliconFlow, DeepInfra, Moonshot)

## Quick Start

Git clone, install deps, add your API key, run the TUI.

## Architecture

5,413 lines Python. Core from CheetahClaws agent loop + providers + tools.
New: gitclaw.py TUI, Captain paradigm, Keeper memory, git slash commands.

---

<i>Built with [Cocapn](https://github.com/Lucineer/cocapn-ai).</i>
<i>Part of the [Lucineer fleet](https://github.com/Lucineer).</i>

Superinstance & Lucineer (DiGennaro et al.)
