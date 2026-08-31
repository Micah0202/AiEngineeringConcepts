# Dry run: `last_ai_text()`

Every value in this file was produced by actually running the function, not by
reading it. Only the print statements were added.

---

## Part 1 — The two built-ins

### `isinstance(thing, Type)` → `True` / `False`

Asks: **"is this object of this type?"**

```python
isinstance(m, AIMessage)    -> True     # m really is an AIMessage
isinstance(m, ToolMessage)  -> False    # but it is not a ToolMessage
isinstance("x", str)        -> True
isinstance(["a"], list)     -> True
isinstance(5, (int, float)) -> True     # a tuple means "any of these"
```

It answers a question and changes nothing.

**Why the function needs it:** the conversation list is *mixed*. It holds
`SystemMessage`, `HumanMessage`, `AIMessage` and `ToolMessage` all together.
Before reading `.content` we have to know which kind we are holding, because
only the model's own messages count as an answer.

It is used a second time further down for a different reason: `.content` can be
either a `str` or a `list`, and each needs different handling.

> Prefer `isinstance(x, str)` over `type(x) == str`. `isinstance` also accepts
> subclasses, which is what you almost always want.

---

### `getattr(object, "name", default)` → the value, or the default

Asks: **"does this object have an attribute called this? If not, give me this
instead."**

```python
getattr(m, "content")           -> 'hi'    # same as m.content
getattr(m, "tool_calls", None)  -> []      # exists, currently empty
getattr(m, "banana", None)      -> None    # does not exist -> default is used
getattr(m, "banana")            -> AttributeError: 'AIMessage' object has no attribute 'banana'
```

The third argument is a **safety net**. With it, a missing attribute gives you
the default. Without it, you get a crash.

So these two lines are equivalent:

```python
value = getattr(message, "tool_calls", None)

# the long way
try:
    value = message.tool_calls
except AttributeError:
    value = None
```

**Why the function needs it:** not every object in the list is guaranteed to
have `tool_calls`. Writing `message.tool_calls` directly would crash the whole
agent on one unexpected message. `getattr` turns a crash into a `None`.

---

## Part 2 — The dry runs

The conversation used in scenarios A and B:

| # | Message | Content | tool_calls |
|---|---------|---------|------------|
| 0 | `SystemMessage` | `"You are a coding agent."` | — |
| 1 | `HumanMessage`  | `"Create hello.py"` | — |
| 2 | `AIMessage`     | `""` *(empty!)* | `[write_file]` |
| 3 | `ToolMessage`   | `"Created hello.py (1 line)."` | — |
| 4 | `AIMessage`     | `"Done - I created hello.py for you."` | `[]` |

`reversed()` means we walk **4 → 3 → 2 → 1 → 0**, newest first.

---

### Scenario A — the normal case

```
[4] AIMessage
      isinstance(message, AIMessage) -> True
      getattr(message,'tool_calls',None) -> []  (truthy=False)
      content = 'Done - I created hello.py for you.'  type=str
      RETURN 'Done - I created hello.py for you.'
```

**Result:** `'Done - I created hello.py for you.'`

The very first message checked is a hit, so the loop ends immediately. The
other four are never even looked at.

---

### Scenario B — the model ran a tool and stopped

Same conversation, but cut off after the tool result (`convo[:4]`), so there is
no final answer yet. This is the case the function exists for.

```
[3] ToolMessage
      isinstance(message, AIMessage) -> False
      SKIP (not from the model)
[2] AIMessage
      isinstance(message, AIMessage) -> True
      getattr(message,'tool_calls',None) -> [{'name': 'write_file', ...}]  (truthy=True)
      SKIP (only asked for a tool)
[1] HumanMessage
      isinstance(message, AIMessage) -> False
      SKIP (not from the model)
[0] SystemMessage
      isinstance(message, AIMessage) -> False
      SKIP (not from the model)
      loop finished with no match -> RETURN ''
```

**Result:** `''`

Look at message `[2]`. It **is** an `AIMessage`, so a naive "grab the last
AIMessage" would have picked it — and returned its content, which is an empty
string. The user would see a blank screen.

The `tool_calls` check is what catches it. The message was the model *asking
for a tool*, not the model *answering*.

---

### ⚠ The check reads the opposite way round from how it looks

```python
if getattr(message, "tool_calls", None):
    continue
```

`continue` means **skip this message**. So:

| `tool_calls` value | truthy? | what happens |
|---|---|---|
| `[{'name': 'write_file', ...}]` | `True` | **skip it** — this was a tool request |
| `[]` (empty list) | `False` | **keep it** — this is a real answer |
| `None` | `False` | **keep it** |

So it skips when `tool_calls` **has something in it**, and keeps going when it
is empty or missing. An empty list is falsy in Python, which is what makes the
plain `if` work without any comparison.

---

### Scenario C — content is a list of blocks

Some providers return content as blocks instead of one string:

```python
AIMessage(content=[
    {"type": "text",  "text": "Here is the plan."},
    {"type": "image", "url": "diagram.png"},
    {"type": "text",  "text": "Shall I continue?"},
])
```

```
[0] AIMessage
      isinstance(message, AIMessage) -> True
      getattr(message,'tool_calls',None) -> []  (truthy=False)
      content = [{'type': 'text', ...}, {'type': 'image', ...}, {'type': 'text', ...}]  type=list
      parts  = ['Here is the plan.', 'Shall I continue?']
      RETURN 'Here is the plan.\nShall I continue?'
```

**Result:** `'Here is the plan.\nShall I continue?'`

The image block was dropped. The list comprehension keeps only blocks that are
dicts **and** have `type == "text"`, then joins them with newlines.

---

### Scenario D — nothing to find

```
loop finished with no match -> RETURN ''
```

**Result:** `''`

An empty list never enters the loop, so it falls straight to the final
`return ""`. The function always returns a string — never `None` — so callers
never have to check for one.

---

## Part 3 — Summary

| Situation | Returns |
|---|---|
| Model gave a normal text answer | that text |
| Model only requested a tool | `''` |
| Content came back as blocks | the text blocks, joined by `\n` |
| Empty conversation | `''` |
| No `AIMessage` anywhere | `''` |

**The one sentence:** walk backwards through the conversation and return the
first thing the model actually *said*, ignoring the turns where it was only
asking for a tool.

When this returns `''`, that is the signal for the caller to fall back to
`last_tool_text()` so the user still sees something useful.
