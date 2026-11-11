# 0005 — Multipage dashboard with sidebar navigation

- Status: Accepted
- Date: 2026-11-11
- Issues: #52 (skeleton), #53–#55 (M7 UI redesign)

## Context
The dashboard grew into one `app.py` with four tabs (Jobs, Tracker, Run, Settings). Syed chose a
redesign: a Home page with a sidebar menu, job cards, and a clean light theme with an indigo accent.
With tabs, Streamlit runs the code for *every* tab on every click, and one file mixed all screens.

## Decision
- **`st.navigation`** with four file-based pages in `app_pages/` (Home, Jobs, Tracker, Settings),
  Material icons, Home as the default.
- **Thin pages**: each `app_pages/*.py` file is a few lines calling a `render_*` function in the
  `jobpilot` package (`ui_jobs`, `ui_tracker`, `ui_settings`, `ui_run`), so the real code stays importable,
  linted and tested.
- **Shared start-up** in `ui_common.py`: `load_app_config()`, `open_db()` (one connection per page run,
  migrations applied, always closed) and `show_flash()`.
- **Theme** in `.streamlit/config.toml`: light base, primary `#4F46E5` (indigo), soft grey secondary
  background. Users can still switch to dark mode in Streamlit's menu.
- File-based pages (not callables) so tests can open a page with `AppTest.switch_page()`.

## Alternatives considered
- **Keep tabs and only restyle**: smaller change, but no room for a real Home page, and every tab's
  code runs on every click.
- **Callable pages** (`st.Page(func)`): no extra files, but `AppTest` can only switch to file-based pages.
- **Another UI framework** (React, NiceGUI): far more work, against the "smallest thing that works" rule.

## Consequences
- Only the visible page's code runs on each click, so it's faster as data grows.
- Each page reads only what it needs (e.g. Settings never loads the jobs table).
- UI tests open pages explicitly (`open_page(at, "jobs")`) and find messages by content, not position.
