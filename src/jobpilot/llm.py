"""LLM access behind a tiny interface, so the rest of the app never depends on one provider.

GeminiClient talks to Google's REST API with plain httpx (ADR 0001: Gemini free tier).
FakeLlmClient returns canned answers for tests: no network, no API key, no quota.
"""

import logging
import time
from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

import httpx

from jobpilot.config import Config, get_secret

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class LlmError(Exception):
    """The LLM call failed (after retries) or returned no usable text."""


@runtime_checkable
class LlmClient(Protocol):
    def generate(self, prompt: str, *, system: str | None = None, json_output: bool = False) -> str:
        """Send one prompt, return the model's text. json_output asks for a JSON reply."""
        ...


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        http: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self._http = http or httpx.Client(timeout=60.0)
        self._headers = {"x-goog-api-key": api_key}  # header, never the URL: keeps it out of logs
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._sleep = sleep

    def generate(self, prompt: str, *, system: str | None = None, json_output: bool = False) -> str:
        body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_output:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        return _extract_text(self._post(body))

    def _post(self, body: dict) -> dict:
        url = GEMINI_URL.format(model=self.model)
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.post(url, json=body, headers=self._headers)
            except httpx.TransportError as e:
                problem, wait = f"network error: {type(e).__name__}", None
            else:
                if response.status_code not in RETRY_STATUSES:
                    if response.is_error:
                        raise LlmError(
                            f"Gemini HTTP {response.status_code}: {_error_message(response)}"
                        )
                    return response.json()
                problem, wait = f"HTTP {response.status_code}", _retry_after(response)
            if attempt == self._max_retries:
                raise LlmError(f"Gemini failed after {attempt + 1} attempts ({problem})")
            wait = wait if wait is not None else self._backoff * 2**attempt  # 2s, 4s, 8s...
            log.warning("Gemini %s; retrying in %.1fs", problem, wait)
            self._sleep(wait)
        raise AssertionError("unreachable")


class FakeLlmClient:
    """Test double: replies in order (or via a function) and records every prompt."""

    def __init__(self, replies: Sequence[str] | Callable[[str], str] = ("ok",)) -> None:
        self._replies = replies
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, system: str | None = None, json_output: bool = False) -> str:
        self.prompts.append(prompt)
        if callable(self._replies):
            return self._replies(prompt)
        return self._replies[min(len(self.prompts), len(self._replies)) - 1]


def make_llm_client(config: Config) -> LlmClient:
    """The real client for the app: Gemini with the key from .env / environment."""
    return GeminiClient(get_secret("GEMINI_API_KEY"), config.llm_model)


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        reason = (data.get("promptFeedback") or {}).get("blockReason") or (
            candidates[0].get("finishReason") if candidates else "no candidates"
        )
        raise LlmError(f"Gemini returned no text ({reason})")
    return text


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after", "")
    return float(value) if value.replace(".", "", 1).isdigit() else None


def _error_message(response: httpx.Response) -> str:
    try:
        return response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return response.text[:200]
