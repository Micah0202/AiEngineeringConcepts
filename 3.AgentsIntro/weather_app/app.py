import streamlit as st

from weather_agent.prompts import build_greeting_prompt, build_system_prompt
from weather_agent.client import get_client_and_model
from weather_agent.agent import run_agent_turns

with st.sidebar:
    st.header("About this project")
    st.markdown(build_greeting_prompt())

    st.divider()

    st.subheader("Provider")
    try:
        _client, model, provider = get_client_and_model()
        st.success(f"Provider: {provider.name} (model: {model}).")
    except RuntimeError as e:
        st.error("Something went wrong")

    st.divider()

    st.subheader("Jinja system prompt")
    st.caption("The system prompt is the prompt that the agent will use to answer the question.")

    with st.expander("Preview rendered prompt", expanded=False):
        st.code(build_system_prompt(), language="markdown")

    if st.button("Clear chat"):
        st.session_state.chat_log = []
        st.rerun()


st.title("Weather Agent")

if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

for entry in st.session_state.chat_log:
    if entry.get("content"):
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])

prompt = st.chat_input("Ask the agent about weather information")

if prompt:
    st.session_state.chat_log.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = run_agent_turns(st.session_state.chat_log)
            except Exception as e:
                st.error("Something went wrong")
                answer = str(e)

            st.write(answer)
            # st.session_state.chat_log.append({"role": "assistant", "content": answer})