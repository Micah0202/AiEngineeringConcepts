#IMPORTANT   = MIDDLEWARE MAKES SURE THAT WE DO NOT  MAKE3 ANY TOOL  CALLS thatr can target secrets or dangerous pay loads 

import datetime
import json
import re 
from typing import Any, Callable

from config.config import get_work_dir 
from langchain.agents.middleware import AgentMiddleware 
from langchain.tools.tool_node import ToolCallRequest

from langchain.messages import ToolMessage
from langgraph.types import Command 

from tools.paths import is_blocked_path , resolve_work_path

_FILE_TOOLS = {"read_file" , "write_file" , "edit_file" , "list_files"}

BLOCKED_EDIT_PATTERNS = (
    r"\bos\.system\s*\(",
    r"\bsubprocess\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"__import__\s*\(",
)


#return a tool  message  where content is thew reason of denial 
def _tool_message(request: ToolCallRequest, reason: str) -> ToolMessage:
    return ToolMessage(
        content=reason,
        tool_call_id=request.tool_call["id"],
        name=request.tool_call["name"],
    )

#whether we should deny the tool  call  or not 
def deny_reason(tool_name : str ,  arguments : dict[str, Any]) ->str | None: 
    """Return a denial message or None if  the call  may proceed"""

    if tool_name not in _FILE_TOOLS:
        return None 

    path = arguments.get("path",".")

    if is_blocked_path(str(path)):
        return (
            f"Blocked by middleware: access to protected path  {path} is not  allowed " 
        )
    if tool_name == "read_file":
        try:
            file_path = resolve_work_path(str(path))
        except ValueError  as e : 
            return f"Blocked by middleware : {e}" 

        #means the path is not folder it is a file 
        if file_path.is_file() and file_path.stat().st_size > 1024 *1024 *10: 
            return (
                f"Blocked by middleware : file {file_path} is too large to read"
            )

    # means you are doing an edit file or write file or soemthing 
    payload = "" 
    if tool_name =="edit_file":
        payload = str(arguments.get("new_str",""))
    elif tool_name == "write_file":
        payload = str(arguments.get("content",""))

    if payload :
        for pattern in BLOCKED_EDIT_PATTERNS : 
            if re.search(pattern ,  payload):
                return (
                    f"Blocked by middleware : suspicious payload contains {pattern!r}."
                )

    return None         

               



class ProtectionMiddleware(AgentMiddleware): 
    """Short circuit tool calls that target  secret or dangerous payloads """

    def wrap_tool_call(self , request:ToolCallRequest ,  handler : Callable[[ToolCallRequest] , ToolMessage | Command ],)-> ToolMessage | Command : 
        name  = request.tool_call.get("name" , "")
        arguments = request.tool_call.get("args" , {})


        reason =  deny_reason(name ,  arguments)
        #me3ans we are going to  deny the tool call 
        if reason is not  None: 
            return _tool_message(request , reason)
   
        return handler(request ) # if we dont deny call the handler  , the actual ltool  call  being made 

    