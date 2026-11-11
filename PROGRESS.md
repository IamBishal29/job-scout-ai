# Progress

## Current
- Milestone: M1 Fetch & Store (last issue in review) -> next M2 Dashboard & Tracker
- Issue: #7 Greenhouse/Lever company boards (PR open)
- Branch: feat/7-greenhouse-lever
- Next step: Syed reviews/merges #7 PR, then /next-task (#8 Streamlit job list, milestone M2)

## Done
- Agent kit added (CLAUDE.md, skills, settings)
- Kickoff: PRD, architecture, ADR 0001, scaffold + CI, backlog (5 milestones, issues #1-#19)
- #1 Job dataclass + SQLite db layer (models.py, db.py, 6 tests) - merged
- #2 config.toml + load_config() + get_secret() via python-dotenv - merged
- #3 Remotive fetcher + shared httpx client (sources/http.py, sources/remotive.py) - merged
- #4 JobSource Protocol + RemoteOK (~99 jobs) + Arbeitnow (300 jobs, mostly German on-site) - merged
- #5 WWR RSS fetcher: 4 category feeds, ~174 unique jobs (106 worldwide, 50 USA-only) - merged
- #6 pipeline + `python -m jobpilot fetch`: dedupe_key UNIQUE index, exclude_locations; live: 586 fetched, 29 matched, 27 stored, rerun 0 new - merged
- #7 GreenhouseSource/LeverSource + [boards] in config.toml + build_sources(); live: greenhouse 715 fetched, 87 new

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
