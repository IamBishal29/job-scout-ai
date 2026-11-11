import json
from pathlib import Path

import httpx
import pytest

from jobpilot.config import ConfigError, load_config
from jobpilot.llm import FakeLlmClient, GeminiClient, LlmClient, LlmError, make_llm_client

KEY = "test-key-123"


def ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def gemini(responses: list, seen: list[httpx.Request], sleeps: list[float]) -> GeminiClient:
    """Client whose HTTP layer replays `responses` in order (Response or Exception)."""
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return GeminiClient(KEY, "gemini-test", http=http, sleep=sleeps.append)


def test_request_shape_and_key_in_header_not_url():
    seen, sleeps = [], []
    client = gemini([ok(' {"score": 80} ')], seen, sleeps)

    assert client.generate("Rate this job", system="You are a recruiter", json_output=True) == (
        '{"score": 80}'
    )
    req = seen[0]
    assert req.url.path.endswith("/models/gemini-test:generateContent")
    assert req.headers["x-goog-api-key"] == KEY
    assert KEY not in str(req.url)
    body = json.loads(req.content)
    assert body["contents"][0]["parts"][0]["text"] == "Rate this job"
    assert body["systemInstruction"]["parts"][0]["text"] == "You are a recruiter"
    assert body["generationConfig"] == {"responseMimeType": "application/json"}
    assert sleeps == []


def test_retries_rate_limit_and_server_errors_with_backoff():
    seen, sleeps = [], []
    responses = [
        httpx.Response(429, headers={"Retry-After": "7"}),  # server says how long to wait
        httpx.Response(503),
        httpx.ConnectError("boom"),
        ok("done"),
    ]
    assert gemini(responses, seen, sleeps).generate("hi") == "done"
    assert sleeps == [7.0, 4.0, 8.0]  # Retry-After honoured, then 2s * 2^attempt


def test_gives_up_after_max_retries_without_leaking_key():
    seen, sleeps = [], []
    client = gemini([httpx.Response(429)] * 4, seen, sleeps)
    with pytest.raises(LlmError, match="after 4 attempts") as err:
        client.generate("hi")
    assert KEY not in str(err.value)
    assert len(seen) == 4


def test_client_errors_are_not_retried():
    seen, sleeps = [], []
    bad_key = httpx.Response(400, json={"error": {"message": "API key not valid"}})
    with pytest.raises(LlmError, match="400: API key not valid"):
        gemini([bad_key], seen, sleeps).generate("hi")
    assert len(seen) == 1


def test_blocked_or_empty_answer_raises():
    blocked = httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(LlmError, match="SAFETY"):
        gemini([blocked], [], []).generate("hi")


def test_fake_client_replays_and_records():
    fake = FakeLlmClient(["first", "second"])
    assert isinstance(fake, LlmClient)
    assert [fake.generate("a"), fake.generate("b"), fake.generate("c")] == [
        "first",
        "second",
        "second",
    ]
    assert fake.prompts == ["a", "b", "c"]
    assert FakeLlmClient(lambda p: p.upper()).generate("x") == "X"


def test_make_llm_client_uses_config_model_and_env_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    cfg = load_config(Path(__file__).parents[1] / "config.toml")
    client = make_llm_client(cfg)
    assert isinstance(client, GeminiClient)
    assert client.model == cfg.llm_model == "gemini-flash-latest"


def test_llm_check_cli(monkeypatch, capsys):
    from jobpilot import __main__ as cli
    from jobpilot import llm

    monkeypatch.setattr(llm, "make_llm_client", lambda cfg: FakeLlmClient(["JobPilot OK"]))
    assert cli.main(["llm-check"]) == 0
    assert "replied: JobPilot OK" in capsys.readouterr().out

    def no_key(cfg):
        raise ConfigError("Missing secret GEMINI_API_KEY")

    monkeypatch.setattr(llm, "make_llm_client", no_key)
    assert cli.main(["llm-check"]) == 1
    assert "Missing secret GEMINI_API_KEY" in capsys.readouterr().err
