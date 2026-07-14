"""Clinical & reference APIs, dashboard, cross-cutting validation, security."""
import models
from tests.conftest import valid_patient_payload


# ── Consultations (CONS) ────────────────────────────────────────────────────────
def test_cons_create(client, make_patient, db):
    p = make_patient()
    r = client.post("/consultations", json={"patientId": p.id, "chiefComplaint": "fever", "doctorName": "Dr. A"})
    assert r.status_code == 201
    db.refresh(p)
    assert p.status == "Consulted"


def test_cons_missing_patient_404(client):
    assert client.post("/consultations", json={"patientId": 9999, "chiefComplaint": "x"}).status_code == 404


def test_cons_audit(client, make_patient, db):
    p = make_patient()
    client.post("/consultations", json={"patientId": p.id, "chiefComplaint": "fever", "doctorName": "Dr. A"})
    assert db.query(models.AuditLog).filter(models.AuditLog.action == "Consultation Added").first() is not None


def test_cons_list_by_patient(client, make_patient):
    p = make_patient()
    client.post("/consultations", json={"patientId": p.id, "chiefComplaint": "fever"})
    d = client.get(f"/consultations/patient/{p.id}").json()
    assert len(d) == 1 and d[0]["chiefComplaint"] == "fever"


def test_cons_count_by_patient(client, make_patient):
    from datetime import date
    p = make_patient(name="Count Me", dob=date(1990, 5, 15), mobile="9111111111")
    client.post("/consultations", json={"patientId": p.id, "chiefComplaint": "a"})
    client.post("/consultations", json={"patientId": p.id, "chiefComplaint": "b"})
    r = client.get("/consultations/count-by-patient", params={"name": "Count Me", "dob": "1990-05-15"})
    assert r.status_code == 200


# ── Prescriptions (RX) ──────────────────────────────────────────────────────────
def test_rx_create(client, make_patient, db):
    p = make_patient()
    body = {"patientId": p.id, "medications": [{"name": "Amoxicillin", "dosage": "500mg", "frequency": "TDS", "duration": "5 days"}],
            "doctorName": "Dr. A", "notes": "after food"}
    r = client.post("/prescriptions", json=body)
    assert r.status_code == 201
    assert r.json()["medications"][0]["name"] == "Amoxicillin"
    db.refresh(p)
    assert p.status == "Completed"


def test_rx_missing_patient_404(client):
    assert client.post("/prescriptions", json={"patientId": 9999, "medications": [{"name": "X", "dosage": "1", "frequency": "OD"}]}).status_code == 404


def test_rx_audit(client, make_patient, db):
    p = make_patient()
    client.post("/prescriptions", json={"patientId": p.id, "medications": [{"name": "X", "dosage": "1", "frequency": "OD"}]})
    assert db.query(models.AuditLog).filter(models.AuditLog.action == "Prescription Added").first() is not None


def test_rx_list_by_patient(client, make_patient):
    p = make_patient()
    client.post("/prescriptions", json={"patientId": p.id, "medications": [{"name": "X", "dosage": "1", "frequency": "OD"}]})
    assert len(client.get(f"/prescriptions/patient/{p.id}").json()) == 1


# ── Reference data (MISC) ───────────────────────────────────────────────────────
def test_misc_list_doctors(client, seed_doctor):
    r = client.get("/doctors")
    assert r.status_code == 200 and any(d["name"] == "Dr. Rajesh Sharma" for d in r.json())


def test_misc_filter_doctors_role(client, seed_doctor, db):
    db.add(models.Doctor(name="Dr. Junior", specialization="ENT", role="Junior Doctor")); db.commit()
    d = client.get("/doctors", params={"role": "Junior Doctor"}).json()
    assert len(d) == 1 and d[0]["role"] == "Junior Doctor"


def test_misc_create_doctor(client):
    r = client.post("/doctors", json={"name": "Dr. New", "specialization": "ENT"})
    assert r.status_code == 201


def test_misc_list_receptionists(client, seed_receptionist):
    r = client.get("/receptionists")
    assert r.status_code == 200 and len(r.json()) == 1


def test_misc_create_insurance(client):
    r = client.post("/insurance-companies", json={"name": "Star Health", "contactNumber": "1800", "email": "a@x.com"})
    assert r.status_code == 201 and r.json()["name"] == "Star Health"


def test_misc_list_insurance(client):
    client.post("/insurance-companies", json={"name": "LIC"})
    assert any(c["name"] == "LIC" for c in client.get("/insurance-companies").json())


def test_misc_list_medications(client, db):
    db.add(models.Medication(name="Amoxicillin", category="Antibiotic", default_dosage="500mg")); db.commit()
    r = client.get("/medications")
    assert r.status_code == 200 and any(m["name"] == "Amoxicillin" for m in r.json())


def test_misc_search_medications(client, db):
    db.add_all([models.Medication(name="Amoxicillin"), models.Medication(name="Paracetamol")]); db.commit()
    d = client.get("/medications", params={"search": "amox"}).json()
    assert len(d) == 1 and d[0]["name"] == "Amoxicillin"


# ── Dashboard (DASH) ────────────────────────────────────────────────────────────
def test_dash_counts(client, make_patient, seed_doctor):
    make_patient(name="A", mobile="9111111111", status="Checked-In")
    make_patient(name="B", mobile="9222222222", status="Consulted")
    make_patient(name="C", mobile="9333333333", status="Completed")
    b = client.get("/dashboard/stats").json()
    assert b["totalPatients"] == 3 and b["checkedIn"] == 1 and b["inConsultation"] == 1 and b["completed"] == 1 and b["doctorsOnDuty"] == 1


def test_dash_empty(client):
    b = client.get("/dashboard/stats").json()
    assert b["totalPatients"] == 0 and b["checkedIn"] == 0 and b["completed"] == 0


def test_dash_reflects_transitions(client, make_patient):
    p = make_patient()
    assert client.get("/dashboard/stats").json()["checkedIn"] == 0
    client.put(f"/patients/{p.id}", json={"status": "Checked-In", "doctor": "Dr. A"})
    assert client.get("/dashboard/stats").json()["checkedIn"] == 1


# ── Cross-cutting validation (VAL) ──────────────────────────────────────────────
def test_val_missing_field(client):
    body = valid_patient_payload(); body.pop("firstName")
    r = client.post("/patients", json=body)
    assert r.status_code == 422 and isinstance(r.json()["errors"], list)


def test_val_wrong_type(client):
    assert client.post("/patients", json=valid_patient_payload(age="abc")).status_code == 422


def test_val_malformed_json(client):
    r = client.post("/patients", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_val_unknown_route(client):
    assert client.get("/does-not-exist").status_code == 404


def test_val_method_not_allowed(client):
    assert client.delete("/patients").status_code == 405


def test_val_extra_fields_ignored(client):
    body = valid_patient_payload(); body["unexpected"] = "x"
    assert client.post("/patients", json=body).status_code == 201


def test_val_query_bounds(client):
    assert client.get("/admin/patient-flow", params={"days": 6}).status_code == 422


def test_val_large_text(client, make_patient):
    p = make_patient()
    r = client.put(f"/patients/{p.id}", json={"medicalHistory": "x" * 5000})
    assert r.status_code == 200


def test_val_non_ascii_name(client):
    assert client.post("/patients", json=valid_patient_payload(firstName="José")).status_code == 422


# ── Security (SEC) ──────────────────────────────────────────────────────────────
def test_sec_deactivated_blocked(client, seed_doctor, db):
    seed_doctor.is_active = False; db.commit()
    assert client.post("/auth/login", json={"email": "dr.rajesh.sharma@mediclinic.com", "password": "rajesh@123"}).status_code == 403


def test_sec_password_hashed(client, seed_doctor, db):
    db.refresh(seed_doctor)
    assert seed_doctor.password.startswith("$2")  # bcrypt hash, not plaintext


def test_sec_sql_injection_login(client, seed_admin):
    assert client.post("/auth/login", json={"email": "' OR 1=1 --", "password": "x"}).status_code == 401


def test_sec_sql_injection_search(client, make_patient):
    make_patient()
    r = client.get("/patients", params={"search": "' OR '1'='1"})
    assert r.status_code == 200 and r.json() == []  # no rows leaked


def test_sec_password_not_returned(client, seed_doctor):
    r = client.post("/auth/login", json={"email": "dr.rajesh.sharma@mediclinic.com", "password": "rajesh@123"})
    assert "password" not in r.json()
    assert all(u["password"] == "" for u in client.get("/auth/users").json())


def test_sec_reactivation_rotates(client, seed_doctor, db):
    seed_doctor.is_active = False; old = seed_doctor.password; db.commit()
    client.put(f"/admin/users/doctor/{seed_doctor.id}/toggle")
    db.refresh(seed_doctor)
    assert seed_doctor.password != old and seed_doctor.must_change_password is True


def test_sec_actions_audited(client, seed_admin, make_patient, db):
    client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "admin@123"})
    assert db.query(models.AuditLog).count() >= 1


def test_sec_weak_password_rejected(client, seed_doctor):
    r = client.post("/auth/change-password", json={"email": "dr.rajesh.sharma@mediclinic.com",
                                                   "currentPassword": "rajesh@123", "newPassword": "short"})
    assert r.status_code == 400
