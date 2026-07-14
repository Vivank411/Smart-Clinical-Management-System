"""Admin doctor management."""
import models


def test_doctor_stats(client, db):
    db.add_all([
        models.Doctor(name="Dr. A", specialization="Cardiology", is_active=True),
        models.Doctor(name="Dr. B", specialization="Cardiology", is_active=False),
        models.Doctor(name="Dr. C", specialization="ENT", is_active=True),
    ]); db.commit()
    b = client.get("/admin/doctor-stats").json()
    assert b["total"] == 3 and b["active"] == 2 and b["inactive"] == 1 and b["specializations"] == 2


def test_create_doctor(client, db):
    r = client.post("/admin/doctors", json={"name": "Dr. Meera Nair", "specialization": "Pediatrics",
                                            "email": "meera@mediclinic.com", "role": "Doctor"})
    assert r.status_code == 201 and r.json()["is_active"] is True and r.json()["available_from"] == "09:00 AM"
    assert db.query(models.Doctor).filter(models.Doctor.email == "meera@mediclinic.com").first() is not None


def test_create_doctor_audit(client, db):
    client.post("/admin/doctors", json={"name": "Dr. X", "specialization": "ENT"})
    assert db.query(models.AuditLog).filter(models.AuditLog.action == "Doctor Added").first() is not None


def test_toggle_status(client, seed_doctor):
    assert client.put(f"/admin/doctors/{seed_doctor.id}/toggle").json()["isActive"] is False
    assert client.put(f"/admin/doctors/{seed_doctor.id}/toggle").json()["isActive"] is True


def test_toggle_not_found(client):
    assert client.put("/admin/doctors/9999/toggle").status_code == 404


def test_update_doctor(client, seed_doctor):
    r = client.put(f"/admin/doctors/{seed_doctor.id}", json={"specialization": "Neurology", "available_from": "10:00 AM", "available_to": "06:00 PM"})
    b = r.json()
    assert r.status_code == 200 and b["specialization"] == "Neurology" and b["available_from"] == "10:00 AM" and b["available_to"] == "06:00 PM"


def test_update_partial(client, seed_doctor):
    r = client.put(f"/admin/doctors/{seed_doctor.id}", json={"phone": "+91 90000 00000"})
    assert r.status_code == 200 and r.json()["phone"] == "+91 90000 00000" and r.json()["name"] == "Dr. Rajesh Sharma"


def test_update_not_found(client):
    assert client.put("/admin/doctors/9999", json={"specialization": "ENT"}).status_code == 404


def test_delete_doctor(client, seed_doctor, db):
    r = client.delete(f"/admin/doctors/{seed_doctor.id}")
    assert r.status_code == 200 and r.json() == {"deleted": True} and db.query(models.Doctor).count() == 0


def test_delete_audit(client, seed_doctor, db):
    client.delete(f"/admin/doctors/{seed_doctor.id}")
    log = db.query(models.AuditLog).filter(models.AuditLog.action == "Doctor Deleted").first()
    assert log is not None and log.action_type == "delete"


def test_delete_not_found(client):
    assert client.delete("/admin/doctors/9999").status_code == 404
