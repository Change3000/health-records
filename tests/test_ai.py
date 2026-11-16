import pytest
import requests

import ai


class FakeResponse:
    def __init__(self, status_code, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


def answer(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)


def test_prompt_contains_age_and_values():
    prompt = ai.build_prompt(66, 232.0, 13.5, 180.0)
    assert prompt == "Age: 66\nGlucose: 232 mg/dL\nHaemoglobin: 13.5 g/dL\nCholesterol: 180 mg/dL"


def test_remark_is_returned(api_key, monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, json=json)
        return FakeResponse(200, answer("Glucose is in the diabetic range. Please confirm with a doctor."))

    monkeypatch.setattr(ai.requests, "post", fake_post)
    remark = ai.get_remark(66, 232.0, 13.5, 180.0)

    assert remark.startswith("Glucose is in the diabetic range")
    assert sent["url"].endswith("/models/gemini-flash-latest:generateContent")
    assert sent["headers"] == {"x-goog-api-key": "test-key"}
    assert "Glucose: 232 mg/dL" in sent["json"]["contents"][0]["parts"][0]["text"]


def test_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ai.RemarkError, match="not set"):
        ai.get_remark(30, 90.0, 14.0, 180.0)


@pytest.mark.parametrize(
    "response, message",
    [
        (FakeResponse(400, text="API key not valid. Please pass a valid API key."), "rejected"),
        (FakeResponse(429), "Rate limited"),
        (FakeResponse(500), r"error \(500\)"),
        (FakeResponse(200, {"promptFeedback": {"blockReason": "SAFETY"}}), "declined"),
        (FakeResponse(200, {"candidates": []}), "no answer"),
        (FakeResponse(200, answer("   ")), "empty"),
    ],
)
def test_api_failures_become_readable_errors(api_key, monkeypatch, response, message):
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: response)
    with pytest.raises(ai.RemarkError, match=message):
        ai.get_remark(30, 90.0, 14.0, 180.0)


def test_network_failure(api_key, monkeypatch):
    def fail(*a, **k):
        raise requests.ConnectionError()

    monkeypatch.setattr(ai.requests, "post", fail)
    with pytest.raises(ai.RemarkError, match="Could not reach"):
        ai.get_remark(30, 90.0, 14.0, 180.0)
