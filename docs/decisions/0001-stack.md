# 0001 — Stack: Python 3.12 + Streamlit + SQLite + Gemini

- Status: Accepted
- Date: 2026-11-11

## Context
JobPilot is a single-user, local tool. It must use free tools only. It is also a learning
vehicle for moving from .NET into AI engineering, so the stack should match where the AI
ecosystem lives.

## Decision
- **Language: Python 3.12.** Most AI/LLM libraries target Python first. We use 3.12 rather
  than the installed 3.14 because every library already ships wheels for it.
- **UI: Streamlit.** A dashboard written in pure Python, with no frontend build.
- **Storage: SQLite** via stdlib `sqlite3`. A zero-ops file database, enough for one user.
- **LLM: Google Gemini free tier** behind a thin `llm.py` wrapper so we can swap it out later.
- **Email: Gmail SMTP** with an app password, for the daily digest.
- **Tooling:** `venv` + `pip`, `ruff` (lint + format), `pytest`, GitHub Actions CI.
- **Sources:** free public APIs/RSS only for the MVP. LinkedIn/Indeed (alert emails) and Bdjobs
  (polite scraping) are deferred.

## Alternatives considered
- **ASP.NET Core + Blazor**: familiar, but teaches little of the Python AI ecosystem.
- **FastAPI + React**: more powerful, but two apps and a JS build are overkill for one user.
- **Postgres**: needs a server; there is no benefit at this scale.
- **Groq / Ollama**: viable later; Gemini has the most generous free tier with no card.
- **Apify for LinkedIn**: costs money after the free credit; it breaks the free-only rule.

## Consequences
- Fast to build; one process; easy to run on Windows.
- Streamlit is weak for complex UIs. If that limit is reached, revisit with a new ADR.
- On Gemini's free tier, prompts may be used for training, so don't send sensitive data
  beyond the CV and job text.
- Free-tier rate limits mean scoring must be cached and batched.
