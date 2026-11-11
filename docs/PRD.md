# JobPilot — Product Requirements (MVP)

## Problem
Job hunting across many boards is slow and repetitive. Each day I open several sites,
see the same postings again, skim long descriptions to judge fit, and rewrite a cover
letter from scratch. Relevant jobs get missed and there is no single record of what I
applied to.

## User
One user: Syed, a senior .NET developer in Dhaka moving toward AI engineering. Target roles:

- Senior .NET / C# Developer
- AI / LLM Engineer, AI Automation
- Backend / Full-stack Engineer
- Solutions / Software Architect
- Project Management / Team Lead

Locations: **Remote (worldwide)**, **Remote (Bangladesh-based companies)**, **Dhaka on-site/hybrid**.

## MVP features
1. **Fetch jobs** from free, legal sources: Remotive, RemoteOK, Arbeitnow APIs,
   WeWorkRemotely RSS, and Greenhouse/Lever boards for companies I choose.
2. **Dedupe and store** jobs in SQLite (the same job from two sources counts once).
3. **Filter** by role keywords and location rules from a config file.
4. **Match score**: Gemini (free tier) scores each new job 0–100 against my CV and gives
   a two-line reason. Scores are cached, so a job is never scored twice.
5. **Cover letter draft**: one click creates a tailored draft that I edit and send myself.
6. **Application tracker**: status per job (new → saved → applied → interview →
   offer/rejected), with notes and dates.
7. **Dashboard** (Streamlit): a job list sorted by score, filters, job detail, tracker view.
8. **Daily email digest**: top-N new matches sent with Gmail SMTP (app password).

## Out of scope (MVP)
- Auto-submitting applications. **Never**: the app prepares, I submit.
- LinkedIn / Indeed scraping. Planned later through their job-alert emails.
- Bdjobs.com. Planned later as polite, rate-limited scraping.
- Multi-user accounts, auth, cloud hosting, paid APIs, Telegram.

## Constraints
- Free tools and free tiers only; no credit card.
- Runs locally on Windows; one command to start.
- Secrets live only in `.env` (never committed).

## Success criteria
- One `fetch` run collects 100+ jobs from 3+ sources in under 2 minutes, with no duplicates.
- Each day I spend under 15 minutes reviewing the top matches instead of about an hour browsing.
- Match scores feel right: at least 7 of my top 10 are jobs I'd actually consider.
- A cover letter draft needs under 5 minutes of editing.
- Every application I send is tracked in the app.
- CI (lint + tests) is green on every PR.
