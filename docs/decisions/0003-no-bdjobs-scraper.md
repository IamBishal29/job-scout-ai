# 0003 — No Bdjobs scraper (robots.txt disallows it)

- Status: Accepted
- Date: 2026-11-11
- Issue: #19 (closed as won't-do)

## Context
Issue #19 planned a polite Bdjobs scraper whose first acceptance criterion was "checks robots.txt".
On 2026-11-11, `https://bdjobs.com/robots.txt` contained two groups for `User-agent: *`:

```
# All other agents will not spider
User-agent: *
Disallow: /App_Data/
... (system folders only)

# All other agents will not spider
User-agent: *
Disallow: /
```

Named crawlers (Googlebot, Bingbot, LinkedInBot, facebookexternalhit, some SEO tools) get `Allow: /`.

Per RFC 9309 (the robots.txt standard), groups matching the same user-agent are **combined**, so
any unlisted bot, JobPilot included, is disallowed from the whole site. The comment states the
intent plainly: "All other agents will not spider".

**Pitfall found:** Python's `urllib.robotparser` only honours the *first* `User-agent: *` group
and reports `can_fetch(...) == True`. Relying on it alone would have given the wrong answer.

## Decision
Do not build a Bdjobs scraper. Close #19 as "not planned". JobPilot does not include Bdjobs jobs.

## Alternatives considered
- **Bdjobs job-alert emails** via the #18 alert-email source: robots-safe, but not chosen for now.
  It remains the easiest path if Bdjobs coverage is wanted later (new issue: add a Bdjobs parser).
- **Ask Bdjobs** for permission or an API/RSS feed: possible later; not pursued now.
- **Scrape anyway**: rejected. It ignores the site owner's explicit wishes and our own
  acceptance criterion.

## Consequences
- Bangladesh coverage comes from remote-friendly boards, company boards, and LinkedIn/Indeed alerts
  (`[profile] based_in` lets the LLM score Dhaka-friendly roles higher).
- Rule for future sources: check robots.txt **by reading it**, not only with `urllib.robotparser`,
  and check the site's terms before writing a fetcher.
