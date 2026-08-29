# The public front door of the package.
#
# Right now this is deliberately EMPTY of imports. Once agent.py exists (Step 7)
# it will re-export the one thing callers actually need:
#
#     from coding_agent.agent import run_agent
#     __all__ = ["run_agent"]
#
# Remember from weather_app: whatever we put here runs on EVERY import of any
# submodule, so we keep it light on purpose.
