"""Settings page: enter your key, CV and Gmail in the UI instead of editing files."""

import os

import streamlit as st

from jobpilot import cv_import, llm, mailer
from jobpilot.config import Config, ConfigError, get_secret
from jobpilot.env_store import env_path, load_env, save_secrets, secret_status
from jobpilot.ui_common import notify, status_icon

APP_PASSWORD_HELP = """\
1. Turn on **2-Step Verification** for your Google account.
2. Open **myaccount.google.com/apppasswords**, name it "JobPilot", click **Create**.
3. Copy the 16-letter password Google shows (spaces are fine) and paste it below.
"""


def render_settings(config: Config) -> None:
    load_env()  # after a restart, show what's already saved in .env
    st.caption(
        f"Saved on this computer only, in `{env_path()}` (git-ignored). "
        "The dashboard is reachable only from this computer (localhost)."
    )
    if note := st.session_state.pop("settings_flash", None):  # message from the save rerun
        notify("success", note)
    for section in (lambda: _gemini_section(config), lambda: _cv_section(config), _gmail_section):
        with st.container(border=True):  # one box per setting, each with a ✓ / ⚠ heading
            section()


def _cv_section(config: Config) -> None:
    info = cv_import.cv_info(config.cv_path)
    st.subheader(f"{status_icon(info.exists)} Your CV")
    if info.exists:
        st.write(f"Status: **saved** ({info.words} words, updated {info.updated_at:%d %b %Y})")
    else:
        st.write("Status: **not set**. Scoring and cover letters need it.")
    st.caption(
        "Stays on this computer; its text is sent to Gemini when scoring jobs or drafting "
        "letters. Leave out your phone number and home address."
    )

    upload = st.file_uploader("Upload CV (PDF, TXT or MD)", type=["pdf", "txt", "md"])
    if upload is not None:
        try:
            draft, source = cv_import.extract_text(upload.name, upload.getvalue()), upload.file_id
        except cv_import.CvImportError as e:
            st.error(str(e))
            return
        st.info("Check the extracted text below and fix anything that came out wrong.")
    elif info.exists:
        draft, source = config.cv_path.read_text(encoding="utf-8"), f"saved-{info.updated_at}"
    else:
        return

    # a new upload (or a newly saved CV) gets a fresh text box instead of stale edits
    text = st.text_area("CV text", draft, height=300, key=f"cv_text_{source}")
    if st.button("Save CV"):
        if len(text.split()) < 20:
            st.error("That's too short to be a CV.")
        else:
            cv_import.save_cv(config.cv_path, text)
            _saved("CV saved. New scores and cover letters will use it.")


def _saved(message: str) -> None:
    st.session_state.settings_flash = message
    st.rerun()  # redraw so the status lines show the new values


def _gemini_section(config: Config) -> None:
    status = secret_status("GEMINI_API_KEY")
    st.subheader(f"{status_icon(status is not None)} Gemini API key")
    st.write(f"Status: **{status}**" if status else "Status: **not set**")
    st.caption("Free key, no card: https://aistudio.google.com → Get API key.")

    with st.form("gemini_key", clear_on_submit=True):  # the key isn't kept on screen
        key = st.text_input("New API key", type="password", placeholder="paste your key")
        if st.form_submit_button("Save key"):
            if not key.strip():
                st.error("Paste a key first.")
            else:
                save_secrets({"GEMINI_API_KEY": key.strip()})
                _saved("Saved. Use 'Test key' to check it works.")

    if st.button("Test key", disabled=status is None):
        with st.spinner(f"Asking {config.llm_model}..."):
            try:
                reply = llm.check_connection(config)
            except (ConfigError, llm.LlmError) as e:
                st.error(f"Key check failed: {e}")
            else:
                st.success(f"It works. {config.llm_model} replied: {reply}")


def _gmail_section() -> None:
    ready = all(os.environ.get(n) for n in ("SMTP_USER", "SMTP_APP_PASSWORD", "DIGEST_TO"))
    st.subheader(f"{status_icon(ready)} Gmail for the daily digest")
    pw_status = secret_status("SMTP_APP_PASSWORD")
    st.write(f"App password: **{pw_status}**" if pw_status else "App password: **not set**")
    with st.expander("How do I get a Gmail app password?"):
        st.markdown(APP_PASSWORD_HELP)

    with st.form("gmail"):
        user = st.text_input("Your Gmail address", os.environ.get("SMTP_USER", ""))
        to = st.text_input(
            "Send digest to", os.environ.get("DIGEST_TO", ""), placeholder="usually the same"
        )
        password = st.text_input(
            "App password",
            type="password",
            placeholder="leave blank to keep the saved one" if pw_status else "abcd efgh ijkl mnop",
        )
        if st.form_submit_button("Save Gmail settings"):
            new_password = password if password.strip() or not pw_status else None
            problems = mailer.validate_gmail_settings(user, new_password, to or user)
            if problems:
                for problem in problems:
                    st.error(problem)
            else:
                values = {"SMTP_USER": user.strip(), "DIGEST_TO": (to or user).strip()}
                if new_password is not None:
                    values["SMTP_APP_PASSWORD"] = mailer.normalize_app_password(new_password)
                save_secrets(values)
                _saved("Gmail settings saved. Use 'Send test email' to check them.")

    if st.button("Send test email", disabled=not ready):
        with st.spinner("Sending..."):
            try:
                to_address = get_secret("DIGEST_TO")
                mailer.send_test_email(
                    get_secret("SMTP_USER"), get_secret("SMTP_APP_PASSWORD"), to_address
                )
            except (ConfigError, mailer.MailError) as e:
                st.error(f"Test email failed: {e}")
            else:
                st.success(f"Sent to {to_address}. Check your inbox (and spam folder).")
