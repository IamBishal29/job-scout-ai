# Progress

## Current
- Milestone: M6 Settings UI (M1-M5 done)
- Issue: #42 Settings tab: Gemini key (PR open)
- Branch: feat/42-settings-gemini-key
- Next step: Syed merges #42 PR; then /next-task (#43 Gmail settings + test email)

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
- #10 tracker: applications table, PRAGMA user_version migrations, status state machine, Tracker tab (ADR 0002) - merged
- #11 llm.py: LlmClient Protocol, GeminiClient (httpx REST, key in header, 429/5xx backoff), FakeLlmClient, llm-check CLI - merged
- #12 matcher.py + scores table (migration v3) + `score --limit` CLI; prompt includes based_in (Dhaka); real DB at v3, 114 unscored - merged
- #13 dashboard: Score progress column + Why, best-first sort (unscored last), min-score slider, Match metric in detail - merged
- #14 cover_letter.py (grounded template, placeholders + unsupported-number checks), cover_letters table (migration v4), draft UI with copy; real DB at v4 - merged (M3 complete)
- #15 digest.py (HTML + text, escaped), digested_jobs log (migration v5), [digest] top_n/min_score; real DB at v5 - merged
- #16 mailer.py (STARTTLS, app password, multipart) + `digest [--dry-run]` CLI; build -> send -> mark - merged
- #17 `python -m jobpilot daily` (fetch->score->digest, keeps going, exit code), scripts/daily.ps1 + register-task.ps1, README scheduling - merged (MVP complete)
- #18 alerts.py: read-only IMAP (BODY.PEEK), link-based LinkedIn/Indeed parsers (synthetic fixtures, Syed's choice), TRUSTED_LOCATION, [alerts] config; source disabled by default - merged
- #19 Bdjobs: robots.txt disallows unlisted bots (2nd `User-agent: *` group = Disallow: /) -> won't-do, ADR 0003 - merged
- #42 Settings tab: env_store (.env writes, atomic, no newline injection), masked Gemini key + Test key, localhost binding, Settings reachable on empty DB (ADR 0004)

## Decisions waiting for Syed
- #18 parser built from SYNTHETIC alert samples: verify on one real LinkedIn + Indeed alert before relying on it
- Location filter lets country-restricted remotes through (e.g. 'Remote, Poland' on Greenhouse); decide: tighten config, add BD/APAC rule, or rely on M3 scoring
- Company board list is a default (gitlab, canonical, grafanalabs, toptal); edit [boards] in config.toml
- Keyword filter is coarse (e.g. 'Team Lead Account Executive' matched); tune config.toml or rely on M3 scoring
- Remotive free API returns only ~13 jobs (24h delayed); volume now comes from RemoteOK/Arbeitnow
- Get a free Gemini API key (aistudio.google.com, no card) and add GEMINI_API_KEY to .env, then run `python -m jobpilot llm-check`
- Put your CV as plain text/markdown in cv.md (git-ignored) before #12
- Gmail app password (2-step verification) -> SMTP_USER, SMTP_APP_PASSWORD, DIGEST_TO in .env
- Run scripts\register-task.ps1 yourself (auto mode blocked me from running PowerShell with -ExecutionPolicy Bypass)

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
- 2026-11-11: #11 implemented, PR opened; live Gemini call pending Syed's key
- 2026-11-11: #12 implemented, PR opened; live scoring pending key + cv.md
- 2026-11-11: #13 implemented, PR opened
- 2026-11-11: #14 implemented, PR opened; M3 features all built, live LLM run still pending key + CV
- 2026-11-11: #15 implemented, PR opened
- 2026-11-11: #16 implemented, PR opened; caught + tested a misplaced __main__ guard
- 2026-11-11: #17 implemented, PR opened; PowerShell run of daily.ps1 left to Syed
- 2026-11-11: #18 started; IMAP part pushed, parsers wait for Syed's sample .eml files
- 2026-11-11: #18 finished with synthetic samples at Syed's request, PR opened
- 2026-11-11: #19 investigated; Bdjobs robots.txt disallows bots; closed as won't-do (Syed's decision), ADR 0003
- 2026-11-11: M6 Settings UI planned (#42-#45); #42 implemented, PR opened
