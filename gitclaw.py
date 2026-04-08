#!/usr/bin/env python3
"""
Git-Claw v4 — Cocapn Git-Agent TUI
Fork of CheetahClaws, rebuilt as a cocapn fleet vessel.

A terminal-based coding agent that:
- Commands its own build from a Codespaces terminal
- Sends commands to GitHub Copilot and any MCP extension
- Cocapn acts as approver, human watches and can stop anytime
- Captain/Admiral paradigm: agent = Captain, human = Admiral

Usage:
  python gitclaw.py [options] [prompt]

Options:
  -p, --print          Non-interactive: run prompt and exit
  -m, --model MODEL    Override model (default: deepseek-chat)
  --accept-all         Never ask permission (auto-approve)
  --verbose            Show thinking + token counts
  --approve-mode       Captain approves reads, Admiral approves writes
  --equipment PATH     Load equipment from vessel.json path

Slash commands:
  /help          Show help
  /clear         Clear conversation
  /model [m]     Show or set model
  /status        Captain status (tokens, turns, memory)
  /memory [q]    Search persistent memories
  /memory save   Save insight to keeper memory
  /equipment     List loaded equipment
  /mcp           List MCP servers and tools
  /mcp add <name> <cmd> [args]  Add MCP server
  /tasks         List tasks
  /plan [file]   Enter plan mode (writes blocked)
  /plan done     Exit plan mode
  /git status    Show git status
  /git diff      Show staged diff
  /git log       Show recent commits
  /approve on|off  Toggle captain approval mode
  /cost          Show API cost this session
  /exit          Exit
"""
from __future__ import annotations

import os
import re
import sys
import json
import shutil
import subprocess
import atexit
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.panel import Panel
    from rich import print as rprint
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False
    console = None

VERSION = "4.0.0"

# ── ANSI ───────────────────────────────────────────────────────────────────
C = {k: f"\033[{v}m" for k, v in {
    "cyan": "36", "green": "32", "yellow": "33", "red": "31",
    "blue": "34", "magenta": "35", "bold": "1", "dim": "2", "reset": "0"
}.items()}

def clr(text, *keys): return "".join(C[k] for k in keys) + str(text) + C["reset"]
def info(m):  print(clr(m, "cyan"))
def ok(m):    print(clr(m, "green"))
def warn(m):  print(clr(f"Warning: {m}", "yellow"))
def err(m):   print(clr(f"Error: {m}", "red"), file=sys.stderr)

# ── Config ─────────────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".git-claw"
CONFIG_FILE = CONFIG_DIR / "config.json"
MEMORY_DIR = CONFIG_DIR / "memory"
EQUIPMENT_DIR = Path.cwd() / ".claw"  # project-local equipment

DEFAULT_CONFIG = {
    "model": "deepseek-chat",
    "max_tokens": 8192,
    "permission_mode": "auto",  # auto | manual | accept-all | plan
    "approve_mode": True,       # captain auto-approves reads
    "temperature": 0.7,
    "verbose": False,
    "thinking": False,
    "rich_live": True,
    "mcp_servers": {},
    "equipment": [],
    "vessel_id": None,
    "vessel_name": None,
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    return {**DEFAULT_CONFIG}

def save_config(cfg: dict):
    CONFIG_DIR.mkdir(exist_ok=True)
    data = {k: v for k, v in cfg.items() if not k.startswith("_")}
    CONFIG_FILE.write_text(json.dumps(data, indent=2))

# ── Memory (Keeper) ────────────────────────────────────────────────────────
MEMORY_FILE = MEMORY_DIR / "keeper.jsonl"

def memory_init():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def memory_save(insight: str, tags: list[str] = None):
    """Save an insight to keeper memory."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(),
        "insight": insight,
        "tags": tags or [],
    }
    with open(MEMORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def memory_search(query: str, limit: int = 10) -> list[dict]:
    """Simple keyword search across keeper memory."""
    if not MEMORY_FILE.exists():
        return []
    results = []
    keywords = query.lower().split()
    with open(MEMORY_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                text = (entry.get("insight", "") + " " + " ".join(entry.get("tags", []))).lower()
                score = sum(1 for k in keywords if k in text)
                if score > 0:
                    results.append((score, entry))
            except Exception:
                continue
    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:limit]]

def memory_recent(limit: int = 10) -> list[dict]:
    if not MEMORY_FILE.exists():
        return []
    entries = []
    with open(MEMORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    return entries[-limit:]

# ── Equipment ──────────────────────────────────────────────────────────────
def load_equipment(path: Path = None) -> list[dict]:
    """Load equipment from vessel.json."""
    p = path or Path.cwd() / "vessel.json"
    if p.exists():
        try:
            vj = json.loads(p.read_text())
            return vj.get("equipment", [])
        except Exception:
            pass
    return []

# ── Git helpers ────────────────────────────────────────────────────────────
def git_cmd(*args) -> str:
    try:
        r = subprocess.run(["git"] + list(args), capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return str(e)

# ── System prompt ──────────────────────────────────────────────────────────
CAPTAIN_PROMPT = """You are a Cocapn Captain — a git-agent that commands its own build.

## Identity
- You are a Captain. The human watching is the Admiral.
- You think in git: branch = attempt, commit = checkpoint, PR = proposal, fork = independence.
- Equipment changes what you perceive. The Admiral equips you.

## Capabilities
- Read/write/edit files in the working directory
- Run shell commands (bash)
- Use git for version control
- Connect to MCP servers for extended tools (Copilot, linters, etc.)
- Search the web for documentation

## Behavior Rules
1. **Think before acting** — always plan before executing multi-step changes
2. **Commit often** — every logical unit of work gets a commit
3. **Never destroy** — use `git checkout` not `rm` for reverts, prefer `git stash`
4. **Stay in scope** — if asked to do something destructive, warn the Admiral first
5. **Report progress** — tell the Admiral what you're doing and why
6. **Use equipment** — if you have search/web tools, use them. If not, say so.
7. **Be concise** — the Admiral is watching. Don't narrate every line, summarize intent.

## Working Directory
The Admiral's project is in the current working directory. All file operations are relative to it.

## Approval Modes
- Reads (glob, grep, read, web) are auto-approved by the Captain
- Writes (write, edit, bash with side effects) require Admiral approval
- The Admiral can toggle --accept-all to let the Captain run freely

Respond in plain text. Use markdown formatting for code blocks and lists. Be direct and competent.
"""

def get_system_prompt(cfg: dict) -> str:
    prompt = CAPTAIN_PROMPT
    # Add equipment context
    eq = cfg.get("equipment", [])
    if eq:
        prompt += "\n## Your Equipment\n"
        for e in eq:
            prompt += f"- **{e.get('name', 'Unknown')}**: {e.get('desc', '')}\n"
    # Add vessel context
    if cfg.get("vessel_name"):
        prompt += f"\n## Vessel\nYou are vessel: {cfg['vessel_name']}\n"
    # Add memory context
    recent = memory_recent(3)
    if recent:
        prompt += "\n## Recent Memories\n"
        for m in recent:
            prompt += f"- [{m.get('ts', '')[:10]}] {m.get('insight', '')}\n"
    return prompt

# ── Streaming helpers (from CheetahClaws) ─────────────────────────────────
_accumulated_text: list[str] = []
_current_live: "Live | None" = None

def _make_renderable(text: str):
    if any(c in text for c in ("#", "*", "`", "_", "[")):
        return Markdown(text)
    return text

def _start_live():
    global _current_live
    if _RICH and _current_live is None:
        _current_live = Live(console=console, auto_refresh=False, vertical_overflow="visible")
        _current_live.start()

def stream_text(chunk: str):
    global _current_live
    _accumulated_text.append(chunk)
    if _RICH:
        if _current_live is None:
            _start_live()
        _current_live.update(_make_renderable("".join(_accumulated_text)), refresh=True)
    else:
        print(chunk, end="", flush=True)

def stream_thinking(chunk: str, verbose: bool):
    if verbose:
        clean = chunk.replace("\n", " ")
        if clean:
            print(f"{C['dim']}{clean}", end="", flush=True)

def flush_response():
    global _current_live
    full = "".join(_accumulated_text)
    _accumulated_text.clear()
    if _current_live is not None:
        _current_live.stop()
        _current_live = None
    elif _RICH and full.strip():
        console.print(_make_renderable(full))
    else:
        print()

# ── Tool execution (uses CheetahClaws tools.py) ──────────────────────────
# Import the core tools from CheetahClaws
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tool_registry import get_tool_schemas, register_tool
from tools import execute_tool, _bash, _is_safe_bash

def _check_permission(tc: dict, cfg: dict) -> bool:
    """Captain permission gate."""
    perm = cfg.get("permission_mode", "auto")
    name = tc["name"]
    
    # Plan mode
    if perm == "plan" and name in ("Write", "Edit"):
        plan_file = cfg.get("_plan_file", "")
        target = tc["input"].get("file_path", "")
        if plan_file and target and os.path.normpath(target) == os.path.normpath(plan_file):
            return True
        return False
    
    if perm == "accept-all":
        return True
    if perm == "manual":
        return False
    
    # Auto mode: reads are safe, writes need Admiral
    if name in ("Read", "Glob", "Grep", "WebFetch", "WebSearch"):
        return True  # Captain auto-approves reads
    if name == "Bash":
        return _is_safe_bash(tc["input"].get("command", ""))
    return False  # Write, Edit → ask Admiral

def _permission_desc(tc: dict) -> str:
    name = tc["name"]
    inp = tc["input"]
    if name == "Bash":   return f"Run: {inp.get('command', '')}"
    if name == "Write":  return f"Write to: {inp.get('file_path', '')}"
    if name == "Edit":   return f"Edit: {inp.get('file_path', '')}"
    return f"{name}({list(inp.values())[:1]})"

# ── Provider streaming (uses CheetahClaws providers.py) ───────────────────
from providers import stream, detect_provider, AssistantTurn, TextChunk, ThinkingChunk
from compaction import maybe_compact

# ── Agent state ────────────────────────────────────────────────────────────
class AgentState:
    def __init__(self):
        self.messages: list = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.turn_count = 0
        self.cancelled = False

# ── Agent loop ─────────────────────────────────────────────────────────────
def run_agent(user_message: str, state: AgentState, cfg: dict, system_prompt: str):
    """Single user turn through the agent loop."""
    state.messages.append({"role": "user", "content": user_message})
    
    while True:
        if state.cancelled:
            return
        
        state.turn_count += 1
        maybe_compact(state, cfg)
        
        assistant_turn = None
        
        for event in stream(
            model=cfg["model"],
            system=system_prompt,
            messages=state.messages,
            tool_schemas=get_tool_schemas(),
            config=cfg,
        ):
            if isinstance(event, (TextChunk, ThinkingChunk)):
                if isinstance(event, TextChunk):
                    stream_text(event.text)
                else:
                    stream_thinking(event.text, cfg.get("verbose", False))
            elif isinstance(event, AssistantTurn):
                assistant_turn = event
        
        flush_response()
        
        if assistant_turn is None:
            break
        
        state.messages.append({
            "role": "assistant",
            "content": assistant_turn.text,
            "tool_calls": assistant_turn.tool_calls,
        })
        
        state.total_input_tokens += assistant_turn.in_tokens
        state.total_output_tokens += assistant_turn.out_tokens
        
        if not assistant_turn.tool_calls:
            break
        
        for tc in assistant_turn.tool_calls:
            name, inp = tc["name"], tc["input"]
            info(f"  \u2699 {name}({json.dumps(inp)[:80]}...)")
            
            permitted = _check_permission(tc, cfg)
            if not permitted and cfg.get("permission_mode") != "plan":
                desc = _permission_desc(tc)
                info(f"  \u26a0 Admiral approval needed: {desc}")
                answer = input(clr("  Approve? [y/n/skip] ", "yellow")).strip().lower()
                if answer == "y":
                    permitted = True
                elif answer == "skip":
                    info("  \u23ed Skipped")
                    state.messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": "Skipped by Admiral"})
                    continue
                else:
                    info("  \u274c Denied")
                    result = "Denied: Admiral rejected this operation"
                    state.messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": result})
                    continue
            
            if not permitted:
                result = f"[Plan mode] Write blocked. Write to plan file: {cfg.get('_plan_file', '')}"
            else:
                result = execute_tool(name, inp, permission_mode="accept-all", config=cfg)
            
            # Show result summary
            result_preview = result[:200] + ("..." if len(result) > 200 else "")
            if len(result) > 200:
                ok(f"  \u2713 {name} ({len(result)} chars)")
            else:
                ok(f"  \u2713 {name}")
            
            state.messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": result})

# ── Input handling ─────────────────────────────────────────────────────────
def get_input(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return "/exit"

# ── Slash commands ─────────────────────────────────────────────────────────
def handle_command(cmd: str, state: AgentState, cfg: dict) -> bool:
    """Handle slash commands. Returns True if should continue REPL."""
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    
    if command in ("/exit", "/quit"):
        return False
    
    elif command == "/help":
        print(__doc__)
    
    elif command == "/clear":
        state.messages.clear()
        ok("Conversation cleared")
    
    elif command == "/model":
        if arg:
            cfg["model"] = arg
            save_config(cfg)
            info(f"Model set to: {arg}")
        else:
            info(f"Model: {cfg['model']}")
    
    elif command == "/status":
        cost_in = state.total_input_tokens * 0.00014  # deepseek pricing
        cost_out = state.total_output_tokens * 0.00028
        info(f"Turns: {state.turn_count} | In: {state.total_input_tokens:,} | Out: {state.total_output_tokens:,} | ~${cost_in + cost_out:.4f}")
        info(f"Model: {cfg['model']} | Perm: {cfg['permission_mode']} | Memory: {len(memory_recent())} entries")
    
    elif command == "/memory":
        if arg == "save":
            insight = input(clr("Insight to remember: ", "cyan"))
            tags = input(clr("Tags (comma-separated): ", "cyan")).strip().split(",")
            tags = [t.strip() for t in tags if t.strip()]
            memory_save(insight, tags)
            ok("Memory saved")
        elif arg:
            results = memory_search(arg)
            if results:
                for r in results:
                    print(f"  [{r['ts'][:16]}] {r['insight'][:100]}")
            else:
                info("No memories found")
        else:
            recent = memory_recent(10)
            if recent:
                for r in recent:
                    print(f"  [{r['ts'][:16]}] {r['insight'][:100]}")
            else:
                info("No memories yet")
    
    elif command == "/equipment":
        eq = cfg.get("equipment", [])
        if eq:
            for e in eq:
                print(f"  \U0001f393 {e.get('name', '?')}: {e.get('desc', '')[:60]}")
        else:
            info("No equipment loaded. Place vessel.json in working directory.")
    
    elif command == "/mcp":
        if arg.startswith("add "):
            margs = arg[4:].split(maxsplit=2)
            if len(margs) >= 2:
                name, cmd = margs[0], margs[1]
                srv_args = margs[2] if len(margs) > 2 else ""
                if "mcp_servers" not in cfg:
                    cfg["mcp_servers"] = {}
                cfg["mcp_servers"][name] = {"command": cmd, "args": srv_args.split() if srv_args else []}
                save_config(cfg)
                ok(f"MCP server '{name}' added")
            else:
                err("Usage: /mcp add <name> <command> [args]")
        else:
            servers = cfg.get("mcp_servers", {})
            if servers:
                for name, info_d in servers.items():
                    print(f"  \U0001f517 {name}: {info_d.get('command', '?')} {' '.join(info_d.get('args', []))}")
            else:
                info("No MCP servers configured. Use /mcp add <name> <cmd>")
    
    elif command == "/plan":
        if arg and arg != "done":
            cfg["permission_mode"] = "plan"
            cfg["_plan_file"] = arg
            save_config(cfg)
            ok(f"Plan mode: writing to {arg} only. Use /plan done to exit.")
        elif arg == "done":
            cfg["permission_mode"] = "auto"
            cfg.pop("_plan_file", None)
            save_config(cfg)
            ok("Plan mode off. Full write access restored.")
        else:
            info("Usage: /plan <file> or /plan done")
    
    elif command == "/plan-done":
        cfg["permission_mode"] = "auto"
        cfg.pop("_plan_file", None)
        save_config(cfg)
        ok("Plan mode off. Full write access restored.")
    
    elif command.startswith("/git"):
        sub = command[4:].strip() or arg
        if sub == "status":
            print(git_cmd("status", "--short") or "Clean working tree")
        elif sub == "diff":
            print(git_cmd("diff", "--staged") or "No staged changes")
        elif sub == "log":
            print(git_cmd("log", "--oneline", "-10") or "No commits")
        elif sub == "branch":
            print(git_cmd("branch", "--show-current"))
        else:
            print(git_cmd(*sub.split()) if sub else "Usage: /git [status|diff|log|branch]")
    
    elif command == "/approve":
        if arg == "on":
            cfg["permission_mode"] = "accept-all"
            save_config(cfg)
            ok("Captain has full approval. Admiral can relax.")
        elif arg == "off":
            cfg["permission_mode"] = "auto"
            save_config(cfg)
            ok("Back to auto-approve reads, ask on writes.")
        else:
            info(f"Approve mode: {cfg['permission_mode']}")
    
    elif command == "/cost":
        cost_in = state.total_input_tokens * 0.00014
        cost_out = state.total_output_tokens * 0.00028
        info(f"Input: {state.total_input_tokens:,} tokens ({cost_in:.4f})")
        info(f"Output: {state.total_output_tokens:,} tokens ({cost_out:.4f})")
        info(f"Total: ~${cost_in + cost_out:.4f}")
    
    elif command == "/verbose":
        cfg["verbose"] = not cfg.get("verbose", False)
        save_config(cfg)
        info(f"Verbose: {'on' if cfg['verbose'] else 'off'}")
    
    elif command == "/save":
        path = arg or f"session-{datetime.now().strftime('%Y%m%d-%H%M')}.json"
        with open(path, "w") as f:
            json.dump({"messages": state.messages, "config": {k: v for k, v in cfg.items() if not k.startswith("_")}}, f, indent=2)
        ok(f"Session saved to {path}")
    
    elif command == "/load":
        if arg and os.path.exists(arg):
            data = json.loads(open(arg).read())
            state.messages = data.get("messages", [])
            ok(f"Loaded {len(state.messages)} messages from {arg}")
        else:
            err(f"File not found: {arg}")
    
    else:
        warn(f"Unknown command: {command}. Type /help for available commands.")
    
    return True

# ── Main REPL ──────────────────────────────────────────────────────────────
def repl(state: AgentState, cfg: dict, system_prompt: str):
    """Interactive REPL loop."""
    print()
    print(clr("\U0001f6a2 Git-Claw v4.0", "bold", "cyan"))
    print(clr(f"  Model: {cfg['model']} | Vessel: {cfg.get('vessel_name', 'unnamed')}", "dim"))
    print(clr(f"  Permission: {cfg['permission_mode']} | Type /help for commands", "dim"))
    print(clr(f"  Working dir: {os.getcwd()}", "dim"))
    eq = cfg.get("equipment", [])
    if eq:
        print(clr(f"  Equipment: {len(eq)} modules loaded", "dim"))
    print()
    
    while True:
        try:
            prompt = get_input(clr("\U0001f981 ", "bold", "green"))
        except (EOFError, KeyboardInterrupt):
            print()
            break
        
        prompt = prompt.strip()
        if not prompt:
            continue
        
        if prompt.startswith("/"):
            if not handle_command(prompt, state, cfg):
                break
            continue
        
        # Run agent
        print()
        run_agent(prompt, state, cfg, system_prompt)
        print()

# ── One-shot mode ──────────────────────────────────────────────────────────
def oneshot(prompt: str, state: AgentState, cfg: dict, system_prompt: str):
    """Non-interactive: run prompt, print response, exit."""
    run_agent(prompt, state, cfg, system_prompt)
    print()

# ── Entry point ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Git-Claw v4 — Cocapn Git-Agent TUI")
    parser.add_argument("prompt", nargs="*", help="Prompt to run (omit for REPL)")
    parser.add_argument("-p", "--print", action="store_true", help="Non-interactive mode")
    parser.add_argument("-m", "--model", help="Override model")
    parser.add_argument("--accept-all", action="store_true", help="Auto-approve all")
    parser.add_argument("--verbose", action="store_true", help="Show thinking")
    parser.add_argument("--approve-mode", action="store_true", help="Captain approves reads only")
    parser.add_argument("--equipment", help="Load equipment from vessel.json path")
    args = parser.parse_args()
    
    # Init
    memory_init()
    cfg = load_config()
    
    # CLI overrides
    if args.model:
        cfg["model"] = args.model
    if args.accept_all:
        cfg["permission_mode"] = "accept-all"
    if args.verbose:
        cfg["verbose"] = True
    if args.approve_mode:
        cfg["permission_mode"] = "auto"
    
    # Load equipment
    eq_path = Path(args.equipment) if args.equipment else Path.cwd() / "vessel.json"
    if eq_path.exists():
        cfg["equipment"] = load_equipment(eq_path)
        try:
            vj = json.loads(eq_path.read_text())
            cfg["vessel_name"] = vj.get("name", "unnamed")
            cfg["vessel_id"] = vj.get("id", None)
        except Exception:
            pass
    
    system_prompt = get_system_prompt(cfg)
    state = AgentState()
    
    prompt = " ".join(args.prompt)
    if prompt or args.print:
        oneshot(prompt or "Hello", state, cfg, system_prompt)
    else:
        repl(state, cfg, system_prompt)

if __name__ == "__main__":
    main()
