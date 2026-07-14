"""Admin analytics / reporting + audit-log listing."""
from datetime import date
import models


def test_admin_stats(client, db):
    db.add_all([
        models.Doctor(name="Dr. A", specialization="ENT", role="Doctor"),
        models.Doctor(name="Dr. B", specialization="ENT", role="Junior Doctor"),
        models.Admin(name="Adm", email="a@x.com", password="x"),
        models.Patient(name="P One", gender="Male", dob=date(1990, 1, 1), age=36, mobile_number="9111111111"),
    ]); db.commit()
    b = client.get("/admin/stats").json()
    assert b["totalUsers"] == 3 and b["activeDoctors"] == 1 and b["totalPatients"] == 1 and b["avgWaitingTime"] == 14


def test_patient_flow_default(client):
    assert len(client.get("/admin/patient-flow").json()) == 7


def test_patient_flow_today(client, make_patient, db):
    p = make_patient()
    db.add(models.Consultation(patient_id=p.id, chief_complaint="fever", consultation_date=date.today())); db.commit()
    assert client.get("/admin/patient-flow").json()[-1]["count"] == 1


def test_patient_flow_out_of_range(client):
    assert client.get("/admin/patient-flow", params={"days": 3}).status_code == 422
    assert client.get("/admin/patient-flow", params={"days": 60}).status_code == 422


def test_consultation_stats_empty(client):
    d = client.get("/admin/consultation-stats").json()
    assert [s["label"] for s in d] == ["Completed", "Pending", "Cancelled"] and all(s["count"] == 0 for s in d)


def test_consultation_stats_pct(client, make_patient):
    make_patient(name="Done One", mobile="9111111111", status="Consulted")
    make_patient(name="Wait Two", mobile="9222222222", status="Checked-In")
    make_patient(name="Reg Three", mobile="9333333333", status="Registered")
    by = {s["label"]: s for s in client.get("/admin/consultation-stats").json()}
    assert by["Completed"]["count"] == 1 and by["Pending"]["count"] == 2 and round(by["Completed"]["percentage"]) == 33


def test_doctor_workload(client, make_patient):
    make_patient(name="P1", mobile="9111111111", doctor="Dr. Busy")
    make_patient(name="P2", mobile="9222222222", doctor="Dr. Busy")
    make_patient(name="P3", mobile="9333333333", doctor="Dr. Quiet")
    d = client.get("/admin/doctor-workload").json()
    assert d[0]["name"] == "Dr. Busy" and d[0]["count"] == 2 and d[0]["maxCount"] == 2


def test_doctor_workload_empty(client):
    assert client.get("/admin/doctor-workload").json() == []


def test_waiting_time(client):
    d = client.get("/admin/waiting-time").json()
    assert len(d) == 7 and all("day" in x and "mins" in x for x in d)


def test_department_stats(client, make_patient, db):
    db.add(models.Doctor(name="Dr. Heart", specialization="Cardiology")); db.commit()
    make_patient(name="P1", mobile="9111111111", doctor="Dr. Heart")
    make_patient(name="P2", mobile="9222222222", doctor="Dr. Heart")
    d = client.get("/admin/department-stats").json()
    assert len(d) == 1 and d[0]["department"] == "Cardiology" and d[0]["count"] == 2 and d[0]["percentage"] == 100.0


def test_department_stats_empty(client):
    assert client.get("/admin/department-stats").json() == []


def test_peak_hours(client):
    assert [x["hour"] for x in client.get("/admin/peak-hours").json()] == ["8 AM", "10 AM", "12 PM", "2 PM", "4 PM", "6 PM", "8 PM"]


def test_weekly_summary(client, make_patient):
    make_patient()
    b = client.get("/admin/weekly-summary").json()
    for k in ("totalPatients", "totalConsultations", "avgWaitingTime", "cancelledConsultations", "consultationsChange"):
        assert k in b
    assert b["totalPatients"] == 1


def test_recent_audit(client, make_patient):
    p = make_patient()
    client.put(f"/patients/{p.id}", json={"status": "Checked-In", "doctor": "Dr. A"})
    assert any(e["action"] == "Patient Check-in" for e in client.get("/admin/audit-logs").json())


def test_audit_full_pagination(client, seed_admin):
    client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "admin@123"})
    client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "wrong"})
    b = client.get("/admin/audit-logs-full", params={"page": 1, "page_size": 10}).json()
    assert b["total"] >= 2 and len(b["logs"]) == b["total"]
    assert {"id", "time", "user", "action", "module", "status", "actionType"} <= set(b["logs"][0])


def test_audit_full_filter_status(client, seed_admin):
    client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "admin@123"})
    client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "wrong"})
    b = client.get("/admin/audit-logs-full", params={"status": "Failed"}).json()
    assert b["total"] == 1 and b["logs"][0]["status"] == "Failed"
