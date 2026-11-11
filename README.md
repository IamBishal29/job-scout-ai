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

## Test & lint
```powershell
pytest
ruff check .
ruff format --check .
```

## Docs
- [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Decisions](docs/decisions/)
- [Learning notes](docs/learning/)
