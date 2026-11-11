# Progress

## Current
- Milestone: M2 Dashboard & Tracker (M1 done)
- Issue: #10 Application tracker (PR open)
- Branch: feat/10-application-tracker
- Next step: Syed reviews/merges #10 PR (M2 complete), then /next-task (#11 LLM wrapper, M3 - needs free Gemini API key in .env)

## Done
- Agent kit added (CLAUDE.md, skills, settings)
- Kickoff: PRD, architecture, ADR 0001, scaffold + CI, backlog (5 milestones, issues #1-#19)
- #1 Job dataclass + SQLite db layer (models.py, db.py, 6 tests) - merged
- #2 config.toml + load_config() + get_secret() via python-dotenv - merged
- #3 Remotive fetcher + shared httpx client (sources/http.py, sources/remotive.py) - merged
- #4 JobSource Protocol + RemoteOK (~99 jobs) + Arbeitnow (300 jobs, mostly German on-site) - merged
- #5 WWR RSS fetcher: 4 category feeds, ~174 unique jobs (106 worldwide, 50 USA-only) - merged
- #6 pipeline + `python -m jobpilot fetch`: dedupe_key UNIQUE index, exclude_locations; live: 586 fetched, 29 matched, 27 stored, rerun 0 new - merged
- #7 GreenhouseSource/LeverSource + [boards] in config.toml + build_sources(); live: greenhouse 715 fetched, 87 new - merged (M1 complete)
- #8 Streamlit dashboard: app.py + views.py (filter_jobs/to_rows), AppTest smoke tests, telemetry off - merged
- #9 detail panel: selectable table, selected job id in st.session_state, md_escape for descriptions - merged
- #10 tracker: applications table, PRAGMA user_version migrations, status state machine, Tracker tab (ADR 0002)

## Decisions waiting for Syed
- Location filter lets country-restricted remotes through (e.g. 'Remote, Poland' on Greenhouse); decide: tighten config, add BD/APAC rule, or rely on M3 scoring
- Company board list is a default (gitlab, canonical, grafanalabs, toptal); edit [boards] in config.toml
- Keyword filter is coarse (e.g. 'Team Lead Account Executive' matched); tune config.toml or rely on M3 scoring
- Remotive free API returns only ~13 jobs (24h delayed); volume now comes from RemoteOK/Arbeitnow
- Get a free Gemini API key (aistudio.google.com) before M3 — no card needed
- Gmail app password needed before M4 (requires 2-step verification)

## Log
- 2026-11-11: agent kit added
- 2026-11-11: kickoff done; split into two PRs to keep review small
- 2026-11-11: #1 implemented, PR opened
- 2026-11-11: #2 implemented, PR opened
- 2026-11-11: #3 implemented, PR opened
- 2026-11-11: #4 implemented, PR opened
- 2026-11-11: #5 implemented, PR opened
- 2026-11-11: #6 implemented, PR opened
- 2026-11-11: #7 implemented, PR opened (M1 complete once merged)
- 2026-11-11: #8 implemented, PR opened
- 2026-11-11: #9 implemented, PR opened; stopped adding Co-Authored-By to commits (Syed's request)
- 2026-11-11: #10 implemented, PR opened; real DB migrated v0 -> v2, 114 jobs kept
