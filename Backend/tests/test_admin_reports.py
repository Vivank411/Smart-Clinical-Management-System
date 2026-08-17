"""Admin analytics / reporting + audit-log listing."""
from datetime import date, timedelta
import models
import time_utils


def _visit(db, patient, doctor="Dr. A", when=None, created_at=None):
    """Record a consultation — the unit every report figure is derived from."""
    when = when or time_utils.today()
    c = models.Consultation(
        patient_id=patient.id, chief_complaint="fever",
        consultation_date=when, doctor_name=doctor,
        created_at=created_at or time_utils.now_iso(),
    )
    db.add(c); db.commit(); db.refresh(c)
    return c


def test_admin_stats(client, db):
    db.add_all([
        models.Doctor(name="Dr. A", specialization="ENT", role="Doctor"),
        models.Doctor(name="Dr. B", specialization="ENT", role="Junior Doctor"),
        models.Admin(name="Adm", email="a@x.com", password="x"),
        models.Patient(name="P One", gender="Male", dob=date(1990, 1, 1), age=36, mobile_number="9111111111"),
    ]); db.commit()
    b = client.get("/admin/stats").json()
    assert b["totalUsers"] == 3 and b["activeDoctors"] == 1 and b["totalPatients"] == 1
    # No check-in/consultation pair recorded, so there is nothing to average.
    assert b["avgWaitingTime"] == 0


def test_patient_flow_default(client):
    assert len(client.get("/admin/patient-flow").json()) == 7


def test_patient_flow_today(client, make_patient, db):
    _visit(db, make_patient())
    assert client.get("/admin/patient-flow").json()[-1]["count"] == 1


def test_patient_flow_single_day_range(client, make_patient, db):
    _visit(db, make_patient())
    d = client.get("/admin/patient-flow", params={"days": 1}).json()
    assert d == [{"day": "Today", "count": 1}]


def test_patient_flow_out_of_range(client):
    assert client.get("/admin/patient-flow", params={"days": 0}).status_code == 422
    assert client.get("/admin/patient-flow", params={"days": 91}).status_code == 422


def test_patient_flow_excludes_older_visits(client, make_patient, db):
    p = make_patient()
    _visit(db, p, when=time_utils.today() - timedelta(days=20))
    assert sum(x["count"] for x in client.get("/admin/patient-flow").json()) == 0
    assert sum(x["count"] for x in client.get("/admin/patient-flow", params={"days": 30}).json()) == 1


def test_consultation_stats_empty(client):
    d = client.get("/admin/consultation-stats").json()
    assert [s["label"] for s in d] == ["Completed", "Pending", "Cancelled"] and all(s["count"] == 0 for s in d)


def test_consultation_stats_completed_needs_a_prescription(client, make_patient, db):
    done, waiting = make_patient(name="Done One", mobile="9111111111"), make_patient(name="Wait Two", mobile="9222222222")
    _visit(db, done); _visit(db, waiting)
    db.add(models.Prescription(
        patient_id=done.id, medications="[]", prescription_date=time_utils.today(),
    )); db.commit()

    by = {s["label"]: s for s in client.get("/admin/consultation-stats").json()}
    assert by["Completed"]["count"] == 1 and by["Pending"]["count"] == 1
    assert by["Completed"]["percentage"] == 50.0
    assert by["Cancelled"]["count"] == 0


def test_doctor_workload(client, make_patient, db):
    p1, p2, p3 = (make_patient(name=f"P{i}", mobile=f"9{i}11111111") for i in (1, 2, 3))
    _visit(db, p1, doctor="Dr. Busy"); _visit(db, p2, doctor="Dr. Busy")
    _visit(db, p3, doctor="Dr. Quiet")
    d = client.get("/admin/doctor-workload").json()
    assert d[0]["name"] == "Dr. Busy" and d[0]["count"] == 2 and d[0]["maxCount"] == 2


def test_doctor_workload_empty(client):
    assert client.get("/admin/doctor-workload").json() == []


def test_waiting_time(client):
    d = client.get("/admin/waiting-time").json()
    assert len(d) == 7 and all("day" in x and "mins" in x for x in d)


def test_waiting_time_measures_checkin_to_consultation(client, make_patient, db):
    p = make_patient()
    p.checkin_at = (time_utils.now() - timedelta(minutes=20)).isoformat(timespec="seconds")
    db.commit()
    _visit(db, p)

    today_row = client.get("/admin/waiting-time").json()[-1]
    assert 19.0 <= today_row["mins"] <= 21.0
    # The summary card must agree with the chart it sits beside.
    assert client.get("/admin/weekly-summary").json()["avgWaitingTime"] == 20


def test_waiting_time_ignores_stale_checkin(client, make_patient, db):
    """A check-in from a previous visit must not inflate today's wait."""
    p = make_patient()
    p.checkin_at = (time_utils.now() - timedelta(days=3)).isoformat(timespec="seconds")
    db.commit()
    _visit(db, p)
    assert client.get("/admin/waiting-time").json()[-1]["mins"] == 0.0


def test_department_stats(client, make_patient, db):
    db.add(models.Doctor(name="Dr. Heart", specialization="Cardiology")); db.commit()
    p1, p2 = make_patient(name="P1", mobile="9111111111"), make_patient(name="P2", mobile="9222222222")
    _visit(db, p1, doctor="Dr. Heart"); _visit(db, p2, doctor="Dr. Heart")
    d = client.get("/admin/department-stats").json()
    assert len(d) == 1 and d[0]["department"] == "Cardiology" and d[0]["count"] == 2 and d[0]["percentage"] == 100.0


def test_department_stats_empty(client):
    assert client.get("/admin/department-stats").json() == []


def test_report_totals_agree(client, make_patient, db):
    """The whole point of the rewrite: every panel totals the same visit count."""
    db.add(models.Doctor(name="Dr. Heart", specialization="Cardiology")); db.commit()
    p1, p2, p3 = (make_patient(name=f"P{i}", mobile=f"9{i}11111111") for i in (1, 2, 3))
    _visit(db, p1, doctor="Dr. Heart"); _visit(db, p2, doctor="Dr. Heart")
    _visit(db, p3, doctor="Dr. Heart")

    total = client.get("/admin/weekly-summary").json()["totalConsultations"]
    assert total == 3
    assert sum(x["count"] for x in client.get("/admin/patient-flow").json()) == total
    assert sum(x["count"] for x in client.get("/admin/consultation-stats").json()) == total
    assert sum(x["count"] for x in client.get("/admin/doctor-workload").json()) == total
    assert sum(x["count"] for x in client.get("/admin/department-stats").json()) == total


def test_peak_hours_counts_checkins(client, make_patient, db):
    assert [x["hour"] for x in client.get("/admin/peak-hours").json()] \
        == ["8 AM", "10 AM", "12 PM", "2 PM", "4 PM", "6 PM", "8 PM"]

    p = make_patient()
    p.checkin_at = time_utils.now().replace(hour=10, minute=30).isoformat(timespec="seconds")
    db.commit()
    by = {x["hour"]: x["count"] for x in client.get("/admin/peak-hours").json()}
    assert by["10 AM"] == 1 and sum(by.values()) == 1


def test_weekly_summary(client, make_patient, db):
    p = make_patient()
    _visit(db, p)
    b = client.get("/admin/weekly-summary").json()
    for k in ("totalPatients", "totalConsultations", "avgWaitingTime", "cancelledConsultations", "consultationsChange"):
        assert k in b
    # "Patients seen" counts distinct patients with a visit, not everyone on file.
    assert b["totalPatients"] == 1 and b["totalConsultations"] == 1


def test_weekly_summary_ignores_unvisited_patients(client, make_patient):
    make_patient()
    b = client.get("/admin/weekly-summary").json()
    assert b["totalPatients"] == 0 and b["totalConsultations"] == 0


def test_recent_audit(client, make_patient):
    p = make_patient()
    client.put(f"/patients/{p.id}", json={"status": "Checked-In", "doctor": "Dr. A"})
    logs = client.get("/admin/audit-logs").json()
    assert any(e["action"] == "Patient Checked In" for e in logs)


def test_audit_timestamps_are_clinic_local(client, seed_admin):
    """Audit times must be stamped in the clinic timezone, not the host's."""
    client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "admin@123"})
    stamp = client.get("/admin/audit-logs-full").json()["logs"][0]["time"]

    recorded = time_utils.parse(stamp)
    assert recorded is not None
    assert recorded.utcoffset() == time_utils.now().utcoffset()
    assert abs((time_utils.now() - recorded).total_seconds()) < 60


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
