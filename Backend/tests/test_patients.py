"""Patient endpoints."""
from datetime import date, timedelta
from tests.conftest import valid_patient_payload


def test_register_success(client):
    r = client.post("/patients", json=valid_patient_payload())
    assert r.status_code == 201
    b = r.json()
    assert b["name"] == "John Doe" and b["patientId"] == "MED-0001" and b["status"] == "Registered"


def test_register_dup_name_dob_409(client):
    client.post("/patients", json=valid_patient_payload(mobileNumber="9111111111"))
    r = client.post("/patients", json=valid_patient_payload(mobileNumber="9222222222"))
    assert r.status_code == 409 and "already registered" in r.json()["detail"]


def test_register_dup_mobile_409(client):
    client.post("/patients", json=valid_patient_payload())
    r = client.post("/patients", json=valid_patient_payload(firstName="Jane", lastName="Smith"))
    assert r.status_code == 409 and "Mobile number" in r.json()["detail"]


def test_register_family_mobile_ok(client):
    client.post("/patients", json=valid_patient_payload())
    r = client.post("/patients", json=valid_patient_payload(firstName="Jane", lastName="Smith", allowDuplicateMobile=True))
    assert r.status_code == 201


def test_register_bad_mobile_422(client):
    assert client.post("/patients", json=valid_patient_payload(mobileNumber="12345")).status_code == 422


def test_register_bad_gender_422(client):
    assert client.post("/patients", json=valid_patient_payload(gender="Alien")).status_code == 422


def test_register_future_dob_422(client):
    future = (date.today() + timedelta(days=5)).isoformat()
    assert client.post("/patients", json=valid_patient_payload(dob=future, age=0)).status_code == 422


def test_register_age_mismatch_422(client):
    assert client.post("/patients", json=valid_patient_payload(age=5)).status_code == 422


def test_register_bad_name_422(client):
    assert client.post("/patients", json=valid_patient_payload(firstName="John123")).status_code == 422


def test_register_bad_aadhaar_422(client):
    assert client.post("/patients", json=valid_patient_payload(idProofType="Aadhaar Card", idProofNumber="123")).status_code == 422


def test_register_good_aadhaar_201(client):
    assert client.post("/patients", json=valid_patient_payload(idProofType="Aadhaar Card", idProofNumber="123456789012")).status_code == 201


def test_register_id_uppercased(client):
    r = client.post("/patients", json=valid_patient_payload(idProofType="PAN Card", idProofNumber="abcde1234f"))
    assert r.status_code == 201 and r.json()["idProofNumber"] == "ABCDE1234F"


def test_validation_error_shape(client):
    r = client.post("/patients", json=valid_patient_payload(mobileNumber="bad"))
    assert r.status_code == 422
    b = r.json()
    assert b["detail"] == "Validation failed" and isinstance(b["errors"], list) and b["errors"]


def test_list_empty(client):
    assert client.get("/patients").json() == []


def test_list_newest_first(client, make_patient):
    make_patient(name="First Patient", mobile="9111111111")
    make_patient(name="Second Patient", mobile="9222222222")
    assert [p["name"] for p in client.get("/patients").json()] == ["Second Patient", "First Patient"]


def test_list_search_name(client, make_patient):
    make_patient(name="Alice Wonder", mobile="9111111111")
    make_patient(name="Bob Builder", mobile="9222222222")
    d = client.get("/patients", params={"search": "alice"}).json()
    assert len(d) == 1 and d[0]["name"] == "Alice Wonder"


def test_list_filter_status(client, make_patient):
    make_patient(name="Reg One", mobile="9111111111", status="Registered")
    make_patient(name="Checked Two", mobile="9222222222", status="Checked-In")
    d = client.get("/patients", params={"status": "Checked-In"}).json()
    assert len(d) == 1 and d[0]["name"] == "Checked Two"


def test_get_by_id(client, make_patient):
    p = make_patient()
    r = client.get(f"/patients/{p.id}")
    assert r.status_code == 200 and r.json()["patientId"] == f"MED-{p.id:04d}"


def test_get_not_found_404(client):
    assert client.get("/patients/9999").status_code == 404


def test_lookup_id_proof_found(client, make_patient):
    make_patient(id_proof_type="PAN Card", id_proof_number="ABCDE1234F")
    r = client.get("/patients/by-id-proof", params={"id_proof_type": "PAN Card", "id_proof_number": "abcde1234f"})
    assert r.status_code == 200 and r.json()["idProofNumber"] == "ABCDE1234F"


def test_lookup_id_proof_404(client):
    assert client.get("/patients/by-id-proof", params={"id_proof_type": "PAN Card", "id_proof_number": "ZZZZZ9999Z"}).status_code == 404


def test_check_duplicate_match(client, make_patient):
    make_patient(name="John Doe", dob=date(1990, 5, 15), mobile="9876543210")
    b = client.get("/patients/check-duplicate", params={"name": "John Doe", "dob": "1990-05-15", "mobile": "9876543210"}).json()
    assert b["nameDobExists"] and b["nameDobPatientId"] == "MED-0001" and b["mobileExists"] and b["mobilePatientName"] == "John Doe"


def test_check_duplicate_none(client):
    b = client.get("/patients/check-duplicate", params={"name": "Nobody", "dob": "2000-01-01", "mobile": "9000000000"}).json()
    assert b["nameDobExists"] is False and b["mobileExists"] is False


def test_update_fields(client, make_patient):
    p = make_patient()
    r = client.put(f"/patients/{p.id}", json={"city": "Pune", "doctor": "Dr. Rajesh Sharma"})
    assert r.status_code == 200 and r.json()["city"] == "Pune" and r.json()["doctor"] == "Dr. Rajesh Sharma"


def test_update_not_found_404(client):
    assert client.put("/patients/9999", json={"city": "Pune"}).status_code == 404


def test_checkin_generates_token(client, make_patient):
    p = make_patient()
    b = client.put(f"/patients/{p.id}", json={"status": "Checked-In", "doctor": "Dr. Rajesh Sharma"}).json()
    assert b["status"] == "Checked-In" and b["queueToken"] == "Q-001" and b["checkinTime"]


def test_checkin_token_increments(client, make_patient):
    p1 = make_patient(name="Pat One", mobile="9111111111")
    p2 = make_patient(name="Pat Two", mobile="9222222222")
    t1 = client.put(f"/patients/{p1.id}", json={"status": "Checked-In", "doctor": "Dr. A"}).json()["queueToken"]
    t2 = client.put(f"/patients/{p2.id}", json={"status": "Checked-In", "doctor": "Dr. A"}).json()["queueToken"]
    assert t1 == "Q-001" and t2 == "Q-002"


def test_checkin_audit_logged(client, make_patient, db):
    import models
    p = make_patient()
    client.put(f"/patients/{p.id}", json={"status": "Checked-In", "doctor": "Dr. A"})
    logs = db.query(models.AuditLog).filter(models.AuditLog.module == "Queue").all()
    assert len(logs) == 1 and logs[0].action == "Patient Checked In"
