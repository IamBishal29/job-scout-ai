# 0004 — Secrets entered in the UI are stored in the local .env

- Status: Accepted
- Date: 2026-11-11
- Issues: #42 (Gemini key), #43 (Gmail), M6 Settings UI

## Context
Users want to enter their Gemini API key and Gmail app password in the dashboard instead of
editing `.env`. The CLI and the Windows scheduled task (#17) also need these values.

## Decision
- The Settings tab writes secrets to the **existing git-ignored `.env`** (path overridable with
  `JOBPILOT_ENV`). `.env` stays the single source of truth for the UI, the CLI and the scheduler.
- `env_store.save_secrets()` updates only the given keys, keeps other lines and comments, quotes
  values with spaces, rejects line breaks (no injecting extra settings), writes atomically
  (temp file + `os.replace`), and updates `os.environ` so the running app uses the new value at once.
- Secrets are **never shown back**: inputs are masked and cleared after save, and status shows only
  "set (ends with abcd)".
- The dashboard binds to **localhost** (`.streamlit/config.toml` `server.address`), so other devices on
  the network can't open the Settings tab.

## Alternatives considered
- **Windows Credential Manager (`keyring`)**: encrypted at rest, but a new dependency and
  Windows-specific; the scheduler would need the same lookup. Possible later upgrade.
- **Session-only**: nothing on disk, but the daily scheduled email couldn't work.

## Consequences
- Secrets remain plain text on disk, protected by your Windows account, the same as before.
- Anyone who can run programs as you can read `.env`; that is acceptable for a personal local tool.
- Never run the dashboard on a shared or server machine with `server.address = 0.0.0.0`.
