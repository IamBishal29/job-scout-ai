# JobPilot

A local job-search assistant. It fetches jobs from free sources, scores them against
your CV with a free LLM (Gemini), drafts cover letters and tracks your applications.
**It never submits an application. You review and submit.**

## Setup (Windows, PowerShell)
```powershell
py install 3.12            # once, if Python 3.12 is missing
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env     # then fill in your keys
```

## Run
```powershell
python -m jobpilot fetch    # collect jobs into data/jobpilot.db
streamlit run app.py        # open the dashboard
```

## Daily run (scheduling)
One command does the whole pipeline: fetch new jobs, score them, email the best new matches.
```powershell
python -m jobpilot daily --dry-run   # try it: the digest prints instead of sending
```
To run it every morning with Windows Task Scheduler (only while you are logged in):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1 -At 08:00
Start-ScheduledTask -TaskName JobPilotDaily      # run once now to test
Get-Content data\logs\daily-*.log -Tail 30       # see what happened
Unregister-ScheduledTask -TaskName JobPilotDaily -Confirm:$false   # remove it
```
Each step runs even if an earlier one fails (e.g. no API key yet). The task's
"Last Run Result" is 0 when every step succeeded. Logs live in `data/logs/` (git-ignored).

## Test & lint
```powershell
pytest
ruff check .
ruff format --check .
```

## Docs
- [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Decisions](docs/decisions/)
- [Learning notes](docs/learning/)
