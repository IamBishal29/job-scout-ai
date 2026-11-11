"""Settings tab: enter secrets in the UI instead of editing .env by hand."""

import streamlit as st

from jobpilot import llm
from jobpilot.config import Config, ConfigError
from jobpilot.env_store import env_path, save_secrets, secret_status


def render_settings(config: Config) -> None:
    st.caption(
        f"Saved on this computer only, in `{env_path()}` (git-ignored). "
        "The dashboard is reachable only from this computer (localhost)."
    )
    _gemini_section(config)


def _gemini_section(config: Config) -> None:
    st.subheader("Gemini API key")
    if note := st.session_state.pop("settings_flash", None):  # message from the save rerun
        st.success(note)
    status = secret_status("GEMINI_API_KEY")
    st.write(f"Status: **{status}**" if status else "Status: **not set**")
    st.caption("Free key, no card: https://aistudio.google.com → Get API key.")

    with st.form(
        "gemini_key", clear_on_submit=True
    ):  # clears the box: the key isn't kept on screen
        key = st.text_input("New API key", type="password", placeholder="paste your key")
        if st.form_submit_button("Save key"):
            if not key.strip():
                st.error("Paste a key first.")
            else:
                save_secrets({"GEMINI_API_KEY": key.strip()})
                st.session_state.settings_flash = "Saved. Use 'Test key' to check it works."
                st.rerun()  # redraw so the status line shows the new key

    if st.button("Test key", disabled=status is None):
        with st.spinner(f"Asking {config.llm_model}..."):
            try:
                reply = llm.check_connection(config)
            except (ConfigError, llm.LlmError) as e:
                st.error(f"Key check failed: {e}")
            else:
                st.success(f"It works. {config.llm_model} replied: {reply}")
