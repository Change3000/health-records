# Patient Health Records

A small Streamlit app for keeping patients' blood test results (glucose,
haemoglobin, cholesterol). When a valid record is saved, the app sends the
patient's age and results to the Google Gemini API and stores the short
health-risk remark it returns.

## Running it

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then paste your Gemini API key into .env
streamlit run app.py
```

Records are stored in `patients.db` (SQLite), created on first run.

Tests:

```bash
pytest
```

## Layout

| File | What it does |
|---|---|
| `app.py` | The Streamlit screen: list, add, edit and delete patients |
| `validation.py` | Input checks. Returns cleaned values plus an error per bad field |
| `db.py` | SQLite table and the create, read, update and delete queries |
| `ai.py` | Builds the prompt, calls the Gemini API, turns API failures into readable messages |
| `tests/` | Unit tests for the validation rules and the AI call (the API is mocked, so no key is needed) |

## Validation rules

- **Name:** required. Letters, spaces, apostrophes and hyphens only.
- **Date of birth:** dd/mm/yyyy. It must be a real date, not in the future,
  and not before 1900. Dots and dashes are accepted as separators, because the
  test data is written as `28.01.1960`. Dates are always stored as `dd/mm/yyyy`.
- **Email:** must look like `name@domain.tld`. It's stored in lower case and
  must be unique, so the same patient can't be entered twice.
- **Blood values:** must be numbers within wide limits (glucose 10–1000,
  haemoglobin 1–25, cholesterol 50–1000). The limits only catch typos.
  Judging whether a result is healthy is the AI's job.

A record is saved only if every field passes. Otherwise the form lists each
problem and keeps what was typed.

## AI remark

`ai.get_remark()` sends the age and the three values to Google's Gemini API
(`generateContent` REST endpoint, called with `requests`) together with a short
system prompt that contains adult reference ranges. The prompt asks for at most
two sentences naming the likeliest risk. The API key is read from the
`GEMINI_API_KEY` environment variable (`.env` locally) and is never stored in
the code. A free key is available at https://aistudio.google.com/apikey.

Busy or rate-limited answers (HTTP 429/5xx) are retried twice with a short
wait. If the main model (`gemini-flash-latest`) still fails, the backup model
(`gemini-flash-lite-latest`) is tried. A rejected key is reported straight away.

If the API key is missing or the call fails, the record is still saved without
a remark, and the remark is retried the next time the record is saved. Editing
only the name or email keeps the existing remark. Changing the date of birth
or any result fetches a new one.

The remark is a screening hint, not a diagnosis.

## Test data results

Results from entering the 10 records on the task sheet:

| # | Name | Result | Reason |
|---|---|---|---|
| 1 | Robyn Pears | Saved | |
| 2 | John Hunter | Rejected | `hunter@gmail` has no domain ending (`.com`) |
| 3 | Darryl Tim | Saved | |
| 4 | Peter Larry | Rejected | 31 November doesn't exist |
| 5 | Sam Kerr | Saved | |
| 6 | Robyn Pears | Rejected | Same email as record 1 (duplicate patient) |
| 7 | Madison XI | Saved | |
| 8 | Kris Wu | Rejected | Born in 2030 (future date), and `Kris.wu.gmail.com` has no `@` |
| 9 | Tenille Singh | Saved | |
| 10 | Prem Kumar | Saved | |
