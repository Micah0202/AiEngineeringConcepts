#prepare a simple function that can help  us inject HITL  to  any agent in langchain  .

from langchain.agents.middleware import HumanInTheLoopMiddleware


def build_hitl_middleware() -> HumanInTheLoopMiddleware:
    return HumanInTheLoopMiddleware(
        interrupt_on={
            #add tools that  do mutations here
            "read_file": False,   # no HITL
            "list_files": False,
            "write_file": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": "Write or overwrite  a file on disk"
            },
            "edit_file": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": "Edit  an existing file on disk"
            }
        },
        description_prefix='Coding agent needs your  approval to  move ahead'
    )
