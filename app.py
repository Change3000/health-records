import streamlit as st
from dotenv import load_dotenv

import db
from ai import RemarkError, get_remark
from validation import age_on, validate

load_dotenv()
db.init_db()

st.set_page_config(page_title="Patient Health Records", layout="wide")

LABELS = {
    "full_name": "Full name",
    "dob": "Date of birth (dd/mm/yyyy)",
    "email": "Email",
    "glucose": "Glucose (mg/dL)",
    "haemoglobin": "Haemoglobin (g/dL)",
    "cholesterol": "Cholesterol (mg/dL)",
}
BLOOD_FIELDS = ["glucose", "haemoglobin", "cholesterol"]


def flash(kind, message):
    st.session_state["flash"] = (kind, message)


def show_flash():
    # Always render the container, even when empty, so the tabs below keep the
    # same position on the page; otherwise Streamlit resets them to the first tab.
    area = st.container()
    if "flash" in st.session_state:
        kind, message = st.session_state.pop("flash")
        getattr(area, kind)(message)


def patient_form(key, values=None):
    values = values or {}
    left, right = st.columns(2)
    form = {}
    with left:
        form["full_name"] = st.text_input(LABELS["full_name"], values.get("full_name", ""), key=f"{key}_name")
        form["dob"] = st.text_input(LABELS["dob"], values.get("dob", ""), key=f"{key}_dob", placeholder="28/01/1960")
        form["email"] = st.text_input(LABELS["email"], values.get("email", ""), key=f"{key}_email")
    with right:
        for field in BLOOD_FIELDS:
            current = values.get(field)
            form[field] = st.text_input(LABELS[field], "" if current is None else f"{current:g}", key=f"{key}_{field}")
    return form


def check(form, exclude_id=None):
    """Validates the form and shows any problems. Returns clean data or None."""
    clean, errors = validate(form)
    if "email" in clean and db.email_taken(clean["email"], exclude_id):
        errors["email"] = f"A patient with the email {clean['email']} already exists."
    if errors:
        st.error("Not saved. Please fix the following:\n\n" + "\n".join(f"- {m}" for m in errors.values()))
        return None
    return clean


def fetch_remark(clean):
    """Returns (remark, problem). A failed AI call never blocks saving; the
    remark is left empty and retried the next time the record is saved."""
    try:
        with st.spinner("Asking the AI for a remark..."):
            return get_remark(age_on(clean["dob"]), *(clean[f] for f in BLOOD_FIELDS)), None
    except RemarkError as e:
        return None, str(e)


def save_done(message, problem):
    if problem:
        flash("warning", f"{message} No AI remark yet: {problem}")
    else:
        flash("success", message)
    st.rerun()


st.title("Patient Health Records")
st.caption("Blood test results with an AI-generated health remark for each patient.")
show_flash()

# The key keeps the chosen tab open when the page reruns after a save.
records_tab, add_tab = st.tabs(["Records", "Add patient"], key="view")

with add_tab:
    # A new key after each save gives an empty form; failed saves keep what was typed.
    add_key = f"add_{st.session_state.get('saved_count', 0)}"
    with st.form(add_key):
        form = patient_form(add_key)
        submitted = st.form_submit_button("Save patient", type="primary")

    if submitted:
        clean = check(form)
        if clean:
            clean["remarks"], problem = fetch_remark(clean)
            try:
                db.add_patient(clean)
            except db.DuplicateEmail:
                st.error(f"A patient with the email {clean['email']} already exists.")
            else:
                st.session_state["saved_count"] = st.session_state.get("saved_count", 0) + 1
                save_done(f"Saved {clean['full_name']}.", problem)

with records_tab:
    patients = db.list_patients()

    if not patients:
        st.info("No patients yet. Add one from the Add patient tab.")
    else:
        st.write(f"{len(patients)} patient{'s' if len(patients) != 1 else ''}")
        st.table(
            [
                {
                    "ID": p["id"],
                    "Full name": p["full_name"],
                    "Date of birth": p["dob"],
                    "Email": p["email"],
                    "Glucose": f"{p['glucose']:g}",
                    "Haemoglobin": f"{p['haemoglobin']:g}",
                    "Cholesterol": f"{p['cholesterol']:g}",
                    "Remarks": p["remarks"] or "Not available",
                }
                for p in patients
            ],
            hide_index=True,
        )

        st.subheader("Edit or delete a patient")
        by_id = {p["id"]: p for p in patients}
        selected_id = st.selectbox(
            "Patient",
            list(by_id),
            format_func=lambda pid: f"#{pid}  {by_id[pid]['full_name']}  ({by_id[pid]['email']})",
        )
        patient = by_id[selected_id]

        with st.form(f"edit_{selected_id}"):
            form = patient_form(f"edit_{selected_id}", patient)
            save, delete = st.columns([1, 1])
            saved = save.form_submit_button("Save changes", type="primary")
            confirm = delete.checkbox("I want to delete this patient")
            deleted = delete.form_submit_button("Delete patient")

        if saved:
            clean = check(form, exclude_id=selected_id)
            if clean:
                results_changed = any(clean[f] != patient[f] for f in BLOOD_FIELDS + ["dob"])
                problem = None
                if results_changed or not patient["remarks"]:
                    clean["remarks"], problem = fetch_remark(clean)
                else:
                    clean["remarks"] = patient["remarks"]
                try:
                    db.update_patient(selected_id, clean)
                except db.DuplicateEmail:
                    st.error(f"A patient with the email {clean['email']} already exists.")
                else:
                    save_done(f"Updated {clean['full_name']}.", problem)

        if deleted:
            if not confirm:
                st.error("Tick the box to confirm before deleting.")
            else:
                db.delete_patient(selected_id)
                flash("success", f"Deleted {patient['full_name']}.")
                st.rerun()
