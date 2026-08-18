import json
from logging import fatal

from weather_agent.client import get_client_and_model
from weather_agent.prompts import build_system_prompt
from weather_agent.tools import TOOL_FUNCTIONS
from weather_agent.schemas import TOOL_MENU
from weather_agent.config import MAX_TURNS, MAX_TOKENS

def run_agent_turns(messages: list, max_turns: int = MAX_TURNS) -> str:
    client, model, _ = get_client_and_model()

    working = [
        {
            "role": "system",
            "content": build_system_prompt(),
        },
        *messages
    ]

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=model,
            messages=working,
            tools=TOOL_MENU,
            max_tokens=MAX_TOKENS,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            answer = message.content or ""
            messages.append({"role": "assistant", "content": answer})
            return answer

        # make a tool call
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
        for call in message.tool_calls:
            name = call.function.name
            if name not in TOOL_FUNCTIONS:
                result = f"Unknown tool: {name}"
            else:
                arguments = json.loads(call.function.arguments)
                tool_result = TOOL_FUNCTIONS[name](**arguments) # make the actual tool call
            
            working.append({
                "role": "tool", # role is tool because we are using the tool to answer the question
                "content": str(tool_result),
                "tool_call_id": call.id,
            })

    # this will be triggered if agent loop doesnt end in max_turns
    fallback = "Stopped after hitting max_turns without a final answer"
    messages.append({"role": "assistant", "content": fallback})
    return fallback


