# Progress

## Current
- Milestone: M1 Fetch & Store
- Issue: #5 WeWorkRemotely RSS fetcher (PR open)
- Branch: feat/5-wwr-rss
- Next step: Syed reviews/merges #5 PR, then /next-task (#6 Pipeline + fetch CLI)

## Done
- Agent kit added (CLAUDE.md, skills, settings)
- Kickoff: PRD, architecture, ADR 0001, scaffold + CI, backlog (5 milestones, issues #1-#19)
- #1 Job dataclass + SQLite db layer (models.py, db.py, 6 tests) - merged
- #2 config.toml + load_config() + get_secret() via python-dotenv - merged
- #3 Remotive fetcher + shared httpx client (sources/http.py, sources/remotive.py) - merged
- #4 JobSource Protocol + RemoteOK (~99 jobs) + Arbeitnow (300 jobs, mostly German on-site) - merged
- #5 WWR RSS fetcher: 4 category feeds, ~174 unique jobs (106 worldwide, 50 USA-only)

## Decisions waiting for Syed
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
