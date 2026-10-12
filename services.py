"""Service-counter configuration. Add a new counter by adding an entry to SERVICES."""
import re

def O(v, *kw):
    return {"v": v, "kw": list(kw)}

NAME_RX = (r"(?:my name is|name is|name:)\s*([A-Za-z][A-Za-z.'-]*"
           r"(?:\s+(?!and\b|for\b|i\b|here\b|need\b|want\b)[A-Za-z][A-Za-z.'-]*){0,3})")
TIME_RX = (r"\b(today|tomorrow|day after tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
           r"\d{1,2}(?::\d{2})?\s?(?:am|pm)|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|any time)\b")
REF_RX = (r"(?:reference|ref|application|roll|file|pension)\s*(?:no\.?|number|id)?\s*(?:is|:|#)?\s*"
          r"((?=[A-Za-z0-9/-]*\d)[A-Za-z0-9/-]{3,})")

URGENCY = {"key": "urgency", "label": "How urgent is this?", "type": "select", "required": True,
           "ask": "How urgent is this: Routine, Soon, or Urgent?",
           "options": [O("Routine", "routine", "not urgent", "normal"),
                       O("Soon", "soon", "as early as possible"),
                       O("Urgent", "urgent", "emergency", "asap", "immediately")]}
ASSIST = {"key": "assistance", "label": "Help you need at the counter", "type": "select", "required": False,
          "ask": "", "options": [O("Wheelchair", "wheelchair"),
                                 O("Sign-language interpreter", "interpreter", "sign language"),
                                 O("Large print", "large print", "big text"),
                                 O("Escort to department", "escort", "guide me", "take me there"),
                                 O("None needed", "no help needed", "none needed")]}
DETAILS = {"key": "details", "label": "Anything else staff should know", "type": "textarea",
           "required": False, "ask": ""}

def name_field(key, label):
    return {"key": key, "label": label, "type": "text", "required": True, "rx": NAME_RX, "ask": "What is the name?"}

SERVICES = {
    "hospital": {
        "name": "Hospital reception",
        "fields": [
            {"key": "purpose", "label": "Why are you here?", "type": "select", "required": True,
             "ask": "What do you need today? For example: appointment, check-in, report, bill.",
             "options": [O("Appointment", "appointment", "book", "booking", "consultation"),
                         O("Check-in", "check in", "check-in", "checking in", "i have arrived"),
                         O("New registration", "register", "registration", "new patient"),
                         O("Collect report", "report", "test result", "scan result"),
                         O("Billing", "bill", "payment", "insurance"),
                         O("Directions", "where is", "directions", "way to"),
                         O("Emergency help", "emergency", "can't breathe", "bleeding")]},
            {"key": "department", "label": "Department", "type": "select", "required": False,
             "required_if": {"purpose": ["Appointment", "Check-in", "Collect report"]},
             "ask": "Which department? Choose 'Not sure' and staff will help.",
             "options": [O("General medicine", "general medicine", "general physician"),
                         O("Cardiology", "cardiology", "heart doctor"),
                         O("Orthopedics", "orthopedic", "orthopaedic", "bone doctor"),
                         O("Pediatrics", "pediatric", "paediatric", "child doctor"),
                         O("Gynecology", "gynecology", "gynaecology"),
                         O("ENT", "ent", "ear nose"),
                         O("Dermatology", "dermatology", "skin doctor"),
                         O("Eye care", "ophthalmology", "eye doctor"),
                         O("Not sure", "not sure", "don't know", "do not know")]},
            name_field("patient_name", "Patient name"),
            {"key": "appointment_time", "label": "Day and time", "type": "text", "required": False,
             "required_if": {"purpose": ["Appointment"]}, "rx": TIME_RX, "join": True,
             "ask": "Which day and time? Write 'Any time' if you have no preference."},
            URGENCY, ASSIST, DETAILS],
        "phrases": ["I want to book an appointment.", "I have come for check-in.",
                    "I need to collect my report.", "I need help with a bill.",
                    "Where is the department?", "This is urgent."],
    },
    "college": {
        "name": "College office",
        "fields": [
            {"key": "purpose", "label": "What do you need?", "type": "select", "required": True,
             "ask": "What do you need? For example: certificate, fee payment, ID card.",
             "options": [O("Admission enquiry", "admission"), O("Fee payment", "fee", "fees"),
                         O("Certificate / transcript", "certificate", "transcript", "bonafide"),
                         O("ID card", "id card"), O("Scholarship", "scholarship"),
                         O("Exam / hall ticket", "hall ticket", "exam")]},
            name_field("student_name", "Student name"),
            {"key": "roll_no", "label": "Roll number", "type": "text", "required": False,
             "required_if": {"purpose": ["Certificate / transcript", "ID card", "Exam / hall ticket"]},
             "rx": REF_RX, "ask": "What is the roll number?"},
            URGENCY, ASSIST, DETAILS],
        "phrases": ["I need a bonafide certificate.", "I want to pay my fees.",
                    "I lost my ID card.", "I need my hall ticket."],
    },
    "government": {
        "name": "Government service counter",
        "fields": [
            {"key": "purpose", "label": "What do you need?", "type": "select", "required": True,
             "ask": "What do you need? For example: apply, pay, check status.",
             "options": [O("Apply for certificate", "apply", "new certificate"),
                         O("Pay tax or bill", "tax", "pay"),
                         O("Check status", "status", "track"),
                         O("Update details", "update", "correct my", "change my"),
                         O("Pension", "pension"), O("Grievance", "complaint", "grievance")]},
            name_field("applicant_name", "Applicant name"),
            {"key": "reference_no", "label": "Reference number", "type": "text", "required": False,
             "required_if": {"purpose": ["Check status", "Update details"]},
             "rx": REF_RX, "ask": "What is the reference number on your receipt?"},
            URGENCY, ASSIST, DETAILS],
        "phrases": ["I want to check my application status.", "I need to update my address.",
                    "I want to apply for a certificate.", "I have a complaint."],
    },
}

NAME_KEYS = ("patient_name", "student_name", "applicant_name")


def public(key):
    s = SERVICES[key]
    return {"key": key, "name": s["name"], "phrases": s["phrases"], "fields": s["fields"]}


def is_required(field, fields):
    if field.get("required"):
        return True
    return any(fields.get(k) in vals for k, vals in field.get("required_if", {}).items())


def missing(service, fields):
    out = []
    for f in SERVICES[service]["fields"]:
        if is_required(f, fields) and not str(fields.get(f["key"], "")).strip():
            out.append({"key": f["key"], "label": f["label"], "ask": f["ask"],
                        "options": [o["v"] for o in f.get("options", [])]})
    return out


def clean_fields(service, raw):
    """Keep only known keys, trim, and validate select values."""
    clean = {}
    for f in SERVICES[service]["fields"]:
        v = str(raw.get(f["key"], "") or "").strip()[:500]
        if f["type"] == "select" and v and v not in [o["v"] for o in f["options"]]:
            raise ValueError(f"'{v}' is not a valid choice for {f['label']}")
        if v:
            clean[f["key"]] = v
    return clean


def sub(text, pattern, group=1):
    return [m.group(group) for m in re.finditer(pattern, text, re.I)]
