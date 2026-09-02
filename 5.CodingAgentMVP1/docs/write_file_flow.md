# How `write_file` actually gets called

**The question:** the user types a prompt. A file appears on disk. Where did the
file's contents come from, and at which exact moment?

**The short answer:** the model wrote them. It wrote them in the *same breath*
as deciding to call the tool — see Step 4.

Every value in this document came from actually running the code.

---

## The one idea that makes it click

Think of the model as **someone dictating over the phone.**

They cannot touch your computer. All they can do is talk. So they say:

> *"Create a file called `greet.py`, and here is what goes inside it:
> `print('hello from the agent')`"*

You are the one holding the pen. **You** open the file, **you** type, **you**
save. The caller supplied both the filename and the contents in one sentence,
but they never touched anything.

That is exactly the relationship. The model produces a *request containing the
content*. Your Python does the writing.

---

## The cast

| Who | File | Job |
|---|---|---|
| **The user** | terminal | types a prompt |
| **The agent loop** | `agent.py` | orchestrates everything |
| **The model** | OpenAI's servers | decides what to do, writes the code |
| **`@tool`** | `write_file.py` line 6 | turns your function into something the model can be told about |
| **LangChain** | library | translates between the model and your function |
| **`write_file`** | `write_file.py` | actually writes to disk |
| **`text.py`** | `tools/text.py` | cleans the model's text before it is saved |
| **`paths.py`** | `tools/paths.py` | checks the location is inside the sandbox |

---

## The flow, end to end

```
 STEP 1   USER          "Create greet.py that prints hello"
            │
 STEP 2   YOUR CODE     build message list
            │           [SystemMessage, HumanMessage]
            │
 STEP 3   YOUR CODE     attach tool schemas   llm.bind_tools([write_file])
            │           ───────────────────────────────────────────►  MODEL
            │
 STEP 4   MODEL         ★ generates the tool call AND the file contents
            │           ◄───────────────────────────────────────────
            │           {"path": "greet.py", "content": "print('hello')"}
            │
 STEP 5   LANGCHAIN     parse JSON → write_file.invoke({...})
            │
 STEP 6   YOUR CODE     clean the text, check the path, WRITE THE FILE
            │           ──────────────────────────────► DISK
            │
 STEP 7   YOUR CODE     send the result back    ──────────────────►  MODEL
            │           ToolMessage("File 'greet.py' written successfully")
            │
 STEP 8   MODEL         ◄─── plain text, NO tool calls  = we are done
            │
          USER          "I created greet.py which prints hello"
```

---

## Step 1 — The user types a prompt

```
"Create a file called greet.py that prints 'hello from the agent'."
```

Just a string. Nothing else exists yet.

---

## Step 2 — Your code builds the message list

```python
messages = [
    SystemMessage(content="You are a coding agent. Use the tools to do the work."),
    HumanMessage(content="Create a file called greet.py that prints 'hello from the agent'."),
]
```

---

## Step 3 — Your code attaches the tools

```python
llm_with_tools = llm.bind_tools([write_file])
```

This is the step that makes everything else possible. **The model has never
seen your Python.** It only ever sees a JSON description of it, which `@tool`
generated automatically from your function's signature and docstring:

```json
{
  "name": "write_file",
  "description": "Create or overwrite a UTF-8 text file in the working directory.
                  ... Do not wrap it in markdown fence. Do not encode line breaks
                  as the two-character sequence backslash-n.",
  "properties": {
    "path":    {"type": "string"},
    "content": {"type": "string"}
  },
  "required": ["path", "content"]
}
```

Read that last part carefully. The model is being told:

> *"There is a thing called `write_file`. To use it you must give me two
> strings: a `path` and a `content`."*

**This is the moment `content` becomes the model's job.** Not because anyone
decided it should be — but because the schema says that field is required, and
the model cannot make the call without filling it in.

---

## Step 4 — ★ THE ANSWER TO YOUR QUESTION ★

The model replies. Here is exactly what came back:

```
ai.content    : ''                       <- EMPTY. it is not talking to the user
finish_reason : 'tool_calls'

arguments (as JSON text, which is how it travels):
  '{"path": "greet.py", "content": "print(\'hello from the agent\')"}'

parsed into Python:
  name    : write_file
  path    : 'greet.py'
  content : "print('hello from the agent')"
```

**`content` was created HERE, at this step, by the model.**

It is generated text — produced by exactly the same process that writes an
English sentence. It just happens to be Python code this time.

### There is no separate "decide, then write" step

This is the part that is easy to picture wrongly. The model does **not** think
"I should call write_file", pause, then compose a file.

It generates one continuous stream of tokens, left to right. Here is that
stream, captured live:

```
chunk   1: name  = 'write_file'      <- the decision
chunk   2: args += '{"'
chunk   3: args += 'path'
chunk   4: args += '":"'
chunk   5: args += 'f'
chunk   6: args += 'izz'
chunk   7: args += '.py'
chunk   8: args += '","'
chunk   9: args += 'content'
chunk  10: args += '":"'              <- the content string OPENS here
chunk  11: args += 'for'              <- the code starts arriving
chunk  12: args += ' i'
chunk  13: args += ' in'
chunk  14: args += ' range'
chunk  15: args += '('
chunk  16: args += '1'
   ...
chunk  37: args += 'Fizz'
chunk  38: args += "')"
chunk  39: args += '"}'               <- closes
```

Notice the order:

1. The **tool name** comes out first (chunk 1)
2. Then the **path** (chunks 2-7)
3. Only at chunk 11 does the **actual code** start

So the model commits to *which tool* and *which filename* before it has written
a single character of the file. And it cannot go back — once a token is out, it
is out. There is no draft and no editing pass.

> **Consequence:** if the file is long enough to hit `max_tokens`, generation
> stops mid-string and you get broken JSON rather than a shorter file. This is
> also why `edit_file` is safer for small changes: replacing one exact string
> is far less generation than re-emitting an entire file.

---

## Step 5 — LangChain translates the request into a real call

The model sent **text**. Your function needs **arguments**. LangChain bridges
the two:

```python
# what arrived (a string)
'{"path": "greet.py", "content": "print(\'hello from the agent\')"}'

#   ↓ json.loads

# a Python dict
{'path': 'greet.py', 'content': "print('hello from the agent')"}

#   ↓ unpacked into the call

write_file.invoke({'path': 'greet.py', 'content': "print('hello from the agent')"})
```

**This is the exact moment your `content` parameter is filled in.**

```python
def write_file(path: str, content: str) -> str:
    #              ↑             ↑
    #        'greet.py'    "print('hello from the agent')"
```

---

## Step 6 — Your function runs

Now, and only now, does anything touch the disk. Line by line:

```python
if not path:
    return "Error: Path is required"
```
Guard against an empty path.

```python
content = prepare_file_content(path, content)
```
**Clean the model's text.** The docstring asked it not to send markdown fences
or `\n` escapes — this is the safety net for when it does anyway. Instruct,
then verify.

```python
file_path = resolve_work_path(path)
```
**Check the location.** Raises `ValueError` if the path escapes the sandbox.
Two untrusted inputs from the model, two separate checks.

```python
file_path.parent.mkdir(parents=True, exist_ok=True)
file_path.write_text(content, encoding="utf-8")
```
Create any missing folders, then write.

```python
return f"File {path!r} written successfully"
```
Return a **string**. This is important — see Step 7.

Confirmed on disk:

```
...\5.CodingAgentMVP1\workspace\greet.py
---- contents ----
print('hello from the agent')
------------------
```

---

## Step 7 — The result goes back to the model

The string your function returned becomes a `ToolMessage`, appended to the
conversation:

```python
messages.append(ToolMessage(
    content="File 'greet.py' written successfully",
    tool_call_id=call["id"],       # pairs this answer with that request
))
```

The whole list is sent again:

```
SystemMessage  You are a coding agent...
HumanMessage   Create a file called greet.py...
AIMessage      (empty)                                 <- the tool request
ToolMessage    File 'greet.py' written successfully    <- what we just added
```

**Why send it back at all?** Because the model has no idea whether its request
worked. It asked; we did it; now we tell it what happened. Without this step it
could never report success, retry a failure, or decide what to do next.

---

## Step 8 — The model writes the final answer

```
tool_calls this time: []      <- EMPTY

FINAL ANSWER:
  The file `greet.py` has been created, and it contains the following code:
  ```python
  print('hello from the agent')
  ```
```

**Empty `tool_calls` is the stop signal.** As long as the model keeps
requesting tools, the loop keeps going. The moment it replies with text and no
tool calls, you are done.

This is exactly what `last_ai_text()` in `messages.py` looks for — it walks
backwards past any message that has `tool_calls` to find the real answer.

---

## Answering the question directly

> **Where does `content` come from?**
> The model generates it.

> **At which step?**
> Step 4 — when it replies to your request.

> **Is it created before or after deciding to call the tool?**
> Neither. Both come out of the same left-to-right token stream. The tool name
> is generated first, then the arguments, then the content — all in one pass,
> with no going back.

> **How does the model know a `content` field exists at all?**
> Step 3. `@tool` read your function signature and turned it into a JSON schema
> saying `content` is a required string. That schema went to the model with
> your prompt.

---

## Two rules to remember

**1. The model can only ASK. It never executes anything.**

Every action is your Python. The model produces a request; you decide whether
to honour it. That is exactly why `paths.py` and `text.py` can work at all — if
the model could write files itself, no amount of checking would help.

**2. `content` is generated text, so treat it as untrusted.**

It comes from the same machinery that writes chat prose, which means it can be
malformed in all the usual ways: wrapped in a markdown fence, escaped one time
too many, cut off halfway. That is not a bug in the model; it is the nature of
generated output — and the reason `prepare_file_content()` exists.
