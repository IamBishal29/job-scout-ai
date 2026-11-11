---
name: kickoff
description: One-time project kickoff for JobPilot - gather requirements, choose the stack, write the PRD and architecture, scaffold the repo and create the GitHub backlog.
---

1. Read CLAUDE.md and PROGRESS.md.
2. Interview me with AskUserQuestion, at most 8 questions in total, in small batches:
   target roles and locations (incl. remote), job sources, what the MVP must do,
   stack (recommend Python 3.12 + Streamlit + SQLite), free LLM provider, how I want
   results delivered (dashboard only, or also a daily email/Telegram digest).
3. Write `docs/PRD.md` (1-2 pages): problem, user, MVP features, out of scope,
   success criteria.
4. Write `docs/ARCHITECTURE.md` with a Mermaid diagram of components and data flow,
   and `docs/decisions/0001-stack.md` as the first ADR.
5. Scaffold the project: folder layout, `pyproject.toml`, ruff, pytest with one passing
   test, `.gitignore`, `.env.example`, `README.md`, and a GitHub Actions workflow that
   runs lint + tests on every pull request.
6. Draft milestones and 3-8 small issues per milestone (each with goal, acceptance
   criteria, and "concepts you'll learn"). Show me the list; after I approve, create
   them with `gh` (milestones via `gh api repos/{owner}/{repo}/milestones`).
7. Write `docs/learning/00-how-we-work.md`: git flow, PRs, CI, ADRs, in plain words.
8. Fill "Project facts" in CLAUDE.md and update PROGRESS.md.
9. Branch `chore/kickoff`, commit, push, open the PR, and give me the link.
