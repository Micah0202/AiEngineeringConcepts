import json
from logging import fatal

from weather_agent.client import get_client_and_model
from weather_agent.prompts import build_system_prompt
from weather_agent.tools import TOOL_FUNCTIONS
from weather_agent.schemas import TOOL_MENU
from weather_agent.config import MAX_TURNS, MAX_TOKENS

#max_turns agentic loop  will  run multiple times,  even after one tall call  , there can be multiple tool  calls so we need to  set a max number of  turns 
def run_agent_turns(messages: list, max_turns: int = MAX_TURNS) -> str:
    client, model, _ = get_client_and_model()

    working = [
        #current working copy of chat , system prompt is run first 
        {
            "role": "system",
            "content": build_system_prompt(),
        },
        *messages
    ]
    #run  the agentic loop only max_turns number of times 
    for _ in range(max_turns):
        # ===================== IMPORTANT =====================
        # WHAT: Send the whole conversation so far to the model, plus the list of
        #       tools it is allowed to use, then read back its single reply.
        # WHY:  The model is stateless - it remembers nothing between calls, so
        #       `working` must be re-sent in full every turn. `tools=TOOL_MENU` is
        #       what actually gives the model the ability to answer with a tool
        #       REQUEST instead of plain text. Without it, tool calling is impossible.
        response = client.chat.completions.create(
            model=model,
            messages=working,
            tools=TOOL_MENU,
            max_tokens=MAX_TOKENS,
        )

        message = response.choices[0].message

        # ===================== IMPORTANT =====================
        # WHAT: The exit door. No tool_calls means the model is done thinking and
        #       has written a final answer for the user.
        # WHY:  This is the ONLY normal way out of the loop. Note it appends to
        #       `messages` (the caller's chat history, which Streamlit keeps on
        #       screen) and NOT to `working` - `working` is a throwaway copy that
        #       dies when this function returns.
        if not message.tool_calls:
            answer = message.content or ""
            #if llm  says i dont need to make any tool calls and 
            messages.append({"role": "assistant", "content": answer})
            return answer

        # make a tool call
        #"for each tool call the model requested, build one dict and then this is appended to  working and sent back to  the model
        #llm is  saying make all  of these tool  calls
        # ===================== IMPORTANT =====================
        # WHAT: Copy the model's OWN request into the history as an "assistant"
        #       message (converting the SDK objects into plain dicts).
        # WHY:  The API refuses a "tool" result message unless the assistant message
        #       that asked for it appears directly before it. Skip this block and the
        #       next API call fails with a 400 error. It also lets the model see what
        #       it already asked for, so it does not repeat the same request.
        working.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": json.dumps(call.function.arguments),
                    }
                } for call in message.tool_calls
            ] 
        })

        # make actual tool calls
        # ===================== IMPORTANT =====================
        # WHAT: Actually RUN each requested tool here on our machine, then append
        #       each answer back as a "tool" message tagged with its tool_call_id.
        # WHY:  The model can only ask - it cannot execute code. This block is where
        #       the real work happens. `tool_call_id` is what pairs each answer with
        #       the matching request, which matters when the model asks for several
        #       tools at once (e.g. Berlin AND Budapest). Once this finishes, the
        #       loop repeats and the model finally gets to see the results.
        for call in message.tool_calls:
            name = call.function.name
            if name not in TOOL_FUNCTIONS:
                result = f"Unknown tool: {name}"
            else:
                arguments = json.loads(call.function.arguments)
                tool_result = TOOL_FUNCTIONS[name](**arguments) # make the actual tool call ,  arguments is the location 
            #we run the tool in our code and give the repsonse to  the llm 
            working.append({
                "role": "tool", # role is tool because we are using the tool to answer the question
                "content": str(tool_result),
                "tool_call_id": call.id,
            })

    # this will be triggered if agent loop doesnt end in max_turns
    #this should be outside loop
    fallback = "Stopped after hitting max_turns without a final answer"
    messages.append({"role": "assistant", "content": fallback})
    return fallback


