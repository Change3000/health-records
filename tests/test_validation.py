from datetime import date

import pytest

from validation import age_on, parse_dob, validate

GOOD = {
    "full_name": "Robyn Pears",
    "dob": "28.01.1960",
    "email": "robyn@gmail.com",
    "glucose": "232",
    "haemoglobin": "13.5",
    "cholesterol": "180",
}


def with_(**changes):
    return {**GOOD, **changes}


def test_valid_record_is_cleaned():
    clean, errors = validate(GOOD)
    assert errors == {}
    assert clean["dob"] == "28/01/1960"
    assert clean["glucose"] == 232.0


@pytest.mark.parametrize("email", ["hunter@gmail", "Kris.wu.gmail.com", "a@@b.com", ""])
def test_bad_emails(email):
    _, errors = validate(with_(email=email))
    assert "email" in errors


def test_email_is_lowercased():
    clean, _ = validate(with_(email="Larry@hotmail.com"))
    assert clean["email"] == "larry@hotmail.com"


@pytest.mark.parametrize("dob", ["28/01/1960", "28.01.1960", "28-01-1960"])
def test_date_separators(dob):
    assert parse_dob(dob) == date(1960, 1, 28)


@pytest.mark.parametrize(
    "dob, message",
    [
        ("31.11.2001", "not a real calendar date"),
        ("19.10.2030", "future"),
        ("1960-01-28", "dd/mm/yyyy"),
        ("2/1/1960", "dd/mm/yyyy"),
    ],
)
def test_bad_dates(dob, message):
    with pytest.raises(ValueError, match=message):
        parse_dob(dob)


@pytest.mark.parametrize("value", ["abc", "", "12,5", "nan"])
def test_blood_values_must_be_numbers(value):
    _, errors = validate(with_(glucose=value))
    assert "glucose" in errors


def test_blood_value_out_of_range():
    _, errors = validate(with_(haemoglobin="135"))
    assert "haemoglobin" in errors


def test_name_rules():
    assert "full_name" in validate(with_(full_name="  "))[1]
    assert "full_name" in validate(with_(full_name="R0byn"))[1]
    assert validate(with_(full_name="  Madison   XI "))[0]["full_name"] == "Madison XI"


def test_age_on():
    assert age_on("28/01/1960", today=date(2026, 1, 27)) == 65
    assert age_on("28/01/1960", today=date(2026, 1, 28)) == 66
