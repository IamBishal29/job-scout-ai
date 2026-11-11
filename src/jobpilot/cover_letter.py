"""Draft a cover letter grounded in my CV. A draft only: I edit it and send it myself."""

import re

from jobpilot.llm import LlmClient
from jobpilot.matcher import MAX_DESCRIPTION_CHARS, cv_hash
from jobpilot.models import CoverLetter, Job

SYSTEM_PROMPT = """You write honest, specific cover letters for a software engineer.
Grounding rules (most important):
- Use ONLY facts stated in the CV. Never invent employers, job titles, years of experience,
  degrees, certifications, numbers, or achievements.
- If the job asks for something the CV does not show, do not claim it. At most say the
  candidate is keen to learn it.
- Where a detail is unknown (hiring manager name, why this company), write a placeholder in
  square brackets, e.g. [Hiring Manager], [specific reason I like this company].
Style: about 250 words, 3-4 short paragraphs, plain and confident, no clichés.
Do not include addresses, dates, or a subject line. Output only the letter text."""

TEMPLATE = """## CV (the only source of facts about the candidate)
{cv}

## Job
Title: {title}
Company: {company}
Location: {location}

### Description
{description}

Write the cover letter for this job now."""

_PLACEHOLDER = re.compile(r"\[[^\[\]\n]{1,60}\]")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def build_prompt(job: Job, cv_text: str) -> str:
    return TEMPLATE.format(
        cv=cv_text.strip(),
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description[:MAX_DESCRIPTION_CHARS],
    )


def generate_draft(llm: LlmClient, job: Job, cv_text: str, model: str) -> CoverLetter:
    body = llm.generate(build_prompt(job, cv_text), system=SYSTEM_PROMPT).strip()
    return CoverLetter(job.id, body, model, cv_hash(cv_text))


def placeholders(draft: str) -> list[str]:
    """Gaps the model marked as unknown: you must fill these before sending."""
    return list(dict.fromkeys(_PLACEHOLDER.findall(draft)))


def unsupported_numbers(draft: str, *sources: str) -> list[str]:
    """Numbers in the draft found in none of the sources: likely invented, so check them.

    A cheap hallucination tripwire: '12 years' when the CV says 10 gets flagged.
    """
    known = {n for text in sources for n in _NUMBER.findall(text)}
    return list(dict.fromkeys(n for n in _NUMBER.findall(draft) if n not in known))
