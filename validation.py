import re
from datetime import date, datetime

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")

# Wide limits: they only catch typos (an extra zero, a misplaced decimal),
# not unhealthy results. Unhealthy results are what the AI remark is for.
BLOOD_LIMITS = {
    "glucose": (10, 1000),      # mg/dL
    "haemoglobin": (1, 25),     # g/dL
    "cholesterol": (50, 1000),  # mg/dL
}


def parse_dob(text):
    """Accepts dd/mm/yyyy. Dots or dashes are allowed as separators too,
    since the test sheet writes dates as 28.01.1960."""
    text = text.strip()
    if not re.fullmatch(r"\d{2}[/.-]\d{2}[/.-]\d{4}", text):
        raise ValueError("Date of birth must be in dd/mm/yyyy format.")

    day, month, year = re.split(r"[/.-]", text)
    try:
        dob = datetime(int(year), int(month), int(day)).date()
    except ValueError:
        raise ValueError(f"{text} is not a real calendar date.")

    if dob > date.today():
        raise ValueError("Date of birth cannot be in the future.")
    if dob.year < 1900:
        raise ValueError("Date of birth looks too far in the past.")
    return dob


def validate(form):
    """Checks raw form input. Returns (clean, errors): clean holds the
    values ready to save, errors maps field name -> message."""
    clean, errors = {}, {}

    name = " ".join(form.get("full_name", "").split())
    if not name:
        errors["full_name"] = "Full name is required."
    elif not NAME_RE.match(name):
        errors["full_name"] = "Name can only contain letters, spaces, apostrophes and hyphens."
    else:
        clean["full_name"] = name

    try:
        clean["dob"] = parse_dob(form.get("dob", "")).strftime("%d/%m/%Y")
    except ValueError as e:
        errors["dob"] = str(e)

    email = form.get("email", "").strip()
    if not EMAIL_RE.match(email):
        errors["email"] = f"'{email}' is not a valid email address."
    else:
        clean["email"] = email.lower()

    for field, (low, high) in BLOOD_LIMITS.items():
        raw = str(form.get(field, "")).strip()
        label = field.capitalize()
        try:
            value = float(raw)
        except ValueError:
            errors[field] = f"{label} must be a number."
            continue
        if not low <= value <= high:
            errors[field] = f"{label} should be between {low} and {high}."
        else:
            clean[field] = value

    return clean, errors


def age_on(dob_text, today=None):
    today = today or date.today()
    dob = datetime.strptime(dob_text, "%d/%m/%Y").date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
