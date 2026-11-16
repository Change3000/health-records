import os
import time

import requests

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-flash-latest"
# Used if the main model stays busy or is unavailable.
BACKUP_MODEL = "gemini-flash-lite-latest"
# Temporary errors (rate limit, server busy) that are worth retrying.
RETRY_STATUSES = {429, 500, 502, 503, 504}
ATTEMPTS_PER_MODEL = 3

SYSTEM_PROMPT = """You review basic blood test results for a health records app.
Given a patient's age and their glucose, haemoglobin and cholesterol values,
reply with a short remark (at most two sentences) that names the most likely
health risk, or says the values look normal. Use plain language.
Reference ranges for an adult:
- Fasting glucose: 70-99 mg/dL normal, 100-125 prediabetic, 126+ diabetic range
- Haemoglobin: about 12-17.5 g/dL depending on sex; below 12 suggests anaemia
- Total cholesterol: under 200 mg/dL desirable, 200-239 borderline, 240+ high
End with "Please confirm with a doctor." Do not add anything else."""


class RemarkError(Exception):
    pass


def build_prompt(age, glucose, haemoglobin, cholesterol):
    return (
        f"Age: {age}\n"
        f"Glucose: {glucose:g} mg/dL\n"
        f"Haemoglobin: {haemoglobin:g} g/dL\n"
        f"Cholesterol: {cholesterol:g} mg/dL"
    )


def get_remark(age, glucose, haemoglobin, cholesterol):
    """Sends the patient's age and results to the Google Gemini API and
    returns its short health-risk remark. Raises RemarkError on any failure.

    Busy or rate-limited answers are retried with a short wait, and if the
    main model still fails, the backup model is tried."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RemarkError("GEMINI_API_KEY is not set.")

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {"role": "user", "parts": [{"text": build_prompt(age, glucose, haemoglobin, cholesterol)}]}
        ],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }

    error = None
    for model in [os.getenv("GEMINI_MODEL") or DEFAULT_MODEL, BACKUP_MODEL]:
        for attempt in range(ATTEMPTS_PER_MODEL):
            if attempt:
                time.sleep(2 ** (attempt - 1))  # wait 1s, then 2s

            try:
                response = requests.post(
                    API_URL.format(model=model),
                    headers={"x-goog-api-key": api_key},
                    json=body,
                    timeout=30,
                )
            except requests.RequestException:
                error = RemarkError("Could not reach the AI service.")
                continue

            if response.status_code == 200:
                return read_remark(response.json())
            if response.status_code in (400, 401, 403) and "API key" in response.text:
                raise RemarkError("The API key was rejected.")
            if response.status_code == 429:
                error = RemarkError("Rate limited by the AI service, try again shortly.")
                continue
            if response.status_code in RETRY_STATUSES:
                error = RemarkError(f"The AI service is busy ({response.status_code}), try again shortly.")
                continue

            # Anything else (for example the model name not found) won't fix
            # itself on a retry, so move on to the backup model.
            error = RemarkError(f"AI service error ({response.status_code}).")
            break

    raise error


def read_remark(data):
    """Pulls the remark text out of a Gemini generateContent response."""
    if data.get("promptFeedback", {}).get("blockReason"):
        raise RemarkError("The AI service declined to comment on these values.")

    candidates = data.get("candidates") or []
    if not candidates:
        raise RemarkError("The AI service returned no answer.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise RemarkError("The AI service returned an empty remark.")
    return text
