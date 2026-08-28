# =============================================================================
# READ THIS FIRST - the one rule that explains everything below.
#
# Streamlit re-runs this ENTIRE file, top to bottom, on EVERY interaction.
# Typing a message, clicking a button, expanding a panel -> the whole script
# runs again from line 1.
#
# So this file is not "set up the UI once". It is "describe what the screen
# should look like right now", executed over and over. Every normal Python
# variable is wiped on each re-run. Only st.session_state survives.
# =============================================================================

import streamlit as st

from weather_agent.prompts import build_greeting_prompt, build_system_prompt
from weather_agent.client import get_client_and_model
from weather_agent.agent import run_agent_turns

# ===================== IMPORTANT =====================
# WHAT: Everything inside this `with` block is drawn in the left sidebar
#       instead of the main page.
# WHY:  It keeps reference material (what the app does, which model is in use,
#       the actual prompt being sent) beside the chat without cluttering it.
#       Remember: this whole block re-draws on every single interaction.
with st.sidebar:
    st.header("About this project")
    # Text for the HUMAN, not for the model. Read from greeting.jinja.
    # st.markdown() is used so the "- " lines render as real bullet points.
    st.markdown(build_greeting_prompt())

    st.divider()

    # ===================== IMPORTANT =====================
    # WHAT: Show which LLM provider is active, or show an error if no API key
    #       was found.
    # WHY:  get_client_and_model() raises RuntimeError when no key is set in
    #       .env. Without this try/except the whole page would crash with a
    #       traceback. Catching it here means the user sees a red box and the
    #       rest of the app still loads.
    st.subheader("Provider")
    try:
        _client, model, provider = get_client_and_model()
        st.success(f"Provider: {provider.name} (model: {model}).")
    except RuntimeError as e:
        st.error("Something went wrong")

    st.divider()

    # ===================== IMPORTANT =====================
    # WHAT: A collapsible panel showing the finished system prompt - the exact
    #       text the model receives after Jinja fills in the tool list.
    # WHY:  This is a debugging window. Prompts are the main thing you tune in
    #       an AI app, so being able to SEE the rendered result (not the
    #       template) makes it obvious when a tool is missing or a variable
    #       did not fill in.
    st.subheader("Jinja system prompt")
    st.caption("The system prompt is the prompt that the agent will use to answer the question.")

    with st.expander("Preview rendered prompt", expanded=False):
        st.code(build_system_prompt(), language="markdown")

    # ===================== IMPORTANT =====================
    # WHAT: Wipe the saved conversation and redraw the page.
    # WHY:  st.button() returns True only on the run where it was just clicked.
    #       Emptying chat_log is not enough on its own - st.rerun() restarts the
    #       script immediately so the old messages disappear from the screen
    #       right away instead of on the next interaction.
    if st.button("Clear chat"):
        st.session_state.chat_log = []
        st.rerun()


st.title("Weather Agent")

# ===================== IMPORTANT =====================
# WHAT: Create the chat history the first time only.
# WHY:  This is THE core Streamlit idea. A normal variable would be reset to []
#       on every re-run, so the conversation would vanish after each message.
#       st.session_state is a dict that survives re-runs. The `if not in` guard
#       is what makes this "create once" instead of "reset every time".
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

# ===================== IMPORTANT =====================
# WHAT: Re-draw every past message as a chat bubble.
# WHY:  The screen is wiped and rebuilt on every re-run, so old messages are
#       NOT still sitting there - they must be painted again from scratch each
#       time. This loop is what makes the conversation appear persistent.
#       The `if entry.get("content")` skips any message with empty text so we
#       never draw a blank bubble.
for entry in st.session_state.chat_log:
    if entry.get("content"):
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])

# ===================== IMPORTANT =====================
# WHAT: The input box pinned to the bottom of the page.
# WHY:  It returns None on most runs, and returns the typed text exactly once -
#       on the re-run triggered by pressing Enter. That is why the next block
#       is guarded by `if prompt:`.
prompt = st.chat_input("Ask the agent about weather information")

# ===================== IMPORTANT =====================
# WHAT: The main event. Save the user's message, run the agent, show the answer.
# WHY:  This only runs on the one re-run where the user actually submitted
#       something. Note the order: save to chat_log FIRST, then draw it, then
#       call the agent - so the user's own message is on screen while they wait.
if prompt:
    st.session_state.chat_log.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt) #write the messagfe to the chat as a user 

    #then switch to the assu
    with st.chat_message("assistant"):
        # st.spinner shows the "Thinking..." animation while the agent works.
        with st.spinner("Thinking..."):
            # ===================== IMPORTANT =====================
            # WHAT: Hand the whole chat history to the agent loop and get the
            #       final answer back.
            # WHY:  Passing chat_log (not just `prompt`) is what gives this app
            #       MEMORY - the model sees every earlier message, so follow-ups
            #       like "and what about Paris?" work.
            #       The try/except stops any failure (bad API key, network down,
            #       max_turns hit) from crashing the entire page.
            try:
                #make the call to  run agent 
                answer = run_agent_turns(st.session_state.chat_log)
                
            except Exception as e:
                st.error("Something went wrong")
                answer = str(e)

            st.write(answer)
            # ===================== IMPORTANT =====================
            # This line is commented out ON PURPOSE. Do not re-enable it.
            # Python passes lists BY REFERENCE, so `messages` inside
            # run_agent_turns IS this same chat_log object. agent.py already
            # appends the assistant's answer to it (see agent.py line 50).
            # Uncommenting this would add the same answer a second time and
            # every reply would appear twice on screen.
            # st.session_state.chat_log.append({"role": "assistant", "content": answer})
