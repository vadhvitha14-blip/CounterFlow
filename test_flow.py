import os, tempfile
os.environ["COUNTERFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
from fastapi.testclient import TestClient
import main

FIELDS = {"purpose": "Appointment", "department": "Cardiology", "patient_name": "Asha Rao",
          "appointment_time": "tomorrow 10 am", "urgency": "Routine"}


def start():
    return c.post("/api/requests", json={"service": "hospital"}).json()["id"]


with TestClient(main.app) as c:
    def test_analyze_never_guesses():
        a = c.post("/api/analyze", json={"service": "hospital", "fields": {},
                   "text": "My name is Asha Rao. I want an appointment, not urgent. My chest hurts"}).json()
        assert a["extracted"]["purpose"] == "Appointment"
        assert a["extracted"]["patient_name"] == "Asha Rao"
        assert a["extracted"]["urgency"] == "Routine"
        assert "department" not in a["extracted"]            # never inferred from symptoms
        assert any(q["key"] == "department" for q in a["questions"])

    def test_ambiguity_is_asked_not_filled():
        a = c.post("/api/analyze", json={"service": "hospital", "fields": {},
                   "text": "appointment or bill"}).json()
        assert "purpose" not in a["extracted"]
        assert any("Did you mean" in q["text"] for q in a["questions"])

    def test_missing_info_blocks_confirmation():
        rid = start()
        c.post(f"/api/requests/{rid}/versions", json={"fields": {"purpose": "Billing"}, "author": "user"})
        r = c.post(f"/api/requests/{rid}/confirm", json={"role": "user", "version_no": 1})
        assert r.status_code == 422

    def test_mutual_confirmation_and_versioning():
        rid = start()
        c.post(f"/api/requests/{rid}/versions", json={"fields": FIELDS, "author": "user"})
        assert c.post(f"/api/requests/{rid}/confirm", json={"role": "user", "version_no": 1}).json()["status"] == "awaiting_staff"
        # staff corrects the department -> version 2, user's confirmation no longer counts
        r = c.post(f"/api/requests/{rid}/versions", json={"fields": {**FIELDS, "department": "Orthopedics"},
                   "author": "staff", "base_version": 1, "note": "Doctor available only here"}).json()
        assert r["current"]["version_no"] == 2 and r["status"] == "ready_for_review"
        assert r["original"]["fields"]["department"] == "Cardiology"      # original preserved
        assert c.post(f"/api/requests/{rid}/confirm", json={"role": "staff", "version_no": 1}).status_code == 409
        c.post(f"/api/requests/{rid}/confirm", json={"role": "staff", "version_no": 2})
        done = c.post(f"/api/requests/{rid}/confirm", json={"role": "user", "version_no": 2}).json()
        assert done["status"] == "completed"
        locked = c.post(f"/api/requests/{rid}/versions", json={"fields": {**FIELDS, "urgency": "Urgent"}, "author": "user"})
        assert locked.status_code == 409

    def test_stale_edit_rejected():
        rid = start()
        c.post(f"/api/requests/{rid}/versions", json={"fields": FIELDS, "author": "user"})
        r = c.post(f"/api/requests/{rid}/versions", json={"fields": {**FIELDS, "urgency": "Soon"}, "author": "staff", "base_version": 0})
        assert r.status_code == 409

    def test_short_keywords_match_whole_words_only():
        a = c.post("/api/analyze", json={"service": "hospital", "fields": {}, "text": "book an appointment"}).json()
        assert "department" not in a["extracted"]        # 'ent' must not match inside 'appointment'
