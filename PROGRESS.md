# Progress

## Current
- Milestone: M1 Fetch & Store
- Issue: #3 Remotive API fetcher (PR open)
- Branch: feat/3-remotive-fetcher
- Next step: Syed reviews/merges #3 PR, then /next-task (#4 RemoteOK + Arbeitnow fetchers)

## Done
- Agent kit added (CLAUDE.md, skills, settings)
- Kickoff: PRD, architecture, ADR 0001, scaffold + CI, backlog (5 milestones, issues #1-#19)
- #1 Job dataclass + SQLite db layer (models.py, db.py, 6 tests) - merged
- #2 config.toml + load_config() + get_secret() via python-dotenv - merged
- #3 Remotive fetcher + shared httpx client (sources/http.py, sources/remotive.py)

## Decisions waiting for Syed
- Remotive free API returns only ~13 jobs (24h delayed); volume must come from other sources
- Get a free Gemini API key (aistudio.google.com) before M3 — no card needed
- Gmail app password needed before M4 (requires 2-step verification)

## Log
- 2026-11-11: agent kit added
- 2026-11-11: kickoff done; split into two PRs to keep review small
- 2026-11-11: #1 implemented, PR opened
- 2026-11-11: #2 implemented, PR opened
- 2026-11-11: #3 implemented, PR opened
