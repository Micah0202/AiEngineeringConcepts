#custom  middleware for logs 

import datetime
import json
from typing import Any, Callable

from config.config import get_work_dir 
from langchain.agents.middleware import AgentMiddleware 
from langchain.tools.tool_node import ToolCallRequest

from langchain.messages import ToolMessage
from langgraph.types import Command 


#IMPORTANT - we can override the methods provided  by AgentMiddleware

#AgentMiddleware already  defines wrap_tool_call so  we need to  override it 
class AuditMiddleware(AgentMiddleware):
    """Append a JSON record after each tool call(allowed or  denied)"""

    #overrride the wrap  tool  call  function bcuz we want a  log after  every tool  call 
    def wrap_tool_call(
            self ,
            request : ToolCallRequest ,
            #handler is like next in node js 
            handler : Callable[[ToolCallRequest],  ToolMessage | Command],#Callable is a function that takes the tool call request and return too l message or a command 

    )->  ToolMessage | Command:
        result =  handler(request) #tool call  runs at this step so  we can so stuff before or after this line 
        preview = ""
        if isinstance(result , ToolMessage):
            preview= str(result.content)[:200]#log initial 200  characters of tool  message

        self._write({
            "timestamp":datetime.now(datetime.UTC).isoformat(),
            "tool": request.tool_call.get("name"),
            "result_preview":preview , 
            "arguments" : request.tool_call.get("args")
            
        })
        return result 

    #write to  the file agent_audit log file 
    def _write(
            self , 
            entry: dict[str, Any]
    ) -> None :       
        log_path = get_work_dir()   / ".agent_audit.log"
        log_path.parent.mkdir(parents=True , exist_ok=True)
        with log_path.open("a" , encoding="utf-8") as f : 
            f.write(json.dumps(entry)+ "\n")
           

    
        
