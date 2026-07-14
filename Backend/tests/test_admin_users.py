"""Admin user management."""
import models


def test_list_merges_sources(client, seed_doctor, seed_admin, seed_receptionist):
    assert {u["source"] for u in client.get("/admin/users").json()} == {"doctor", "admin", "receptionist"}


def test_list_filter_role(client, seed_doctor, seed_admin):
    d = client.get("/admin/users", params={"role": "Admin"}).json()
    assert all(u["role"] == "Admin" for u in d) and len(d) == 1


def test_list_search(client, seed_doctor, seed_admin):
    d = client.get("/admin/users", params={"search": "rajesh"}).json()
    assert len(d) == 1 and "Rajesh" in d[0]["name"]


def test_create_doctor(client, db):
    r = client.post("/admin/users", json={"firstName": "New", "lastName": "Doc", "email": "new.doc@mediclinic.com",
                                          "role": "Doctor", "specialization": "Cardiology", "sendWelcomeEmail": True})
    assert r.status_code == 201 and r.json()["source"] == "doctor" and r.json()["specialization"] == "Cardiology"
    doc = db.query(models.Doctor).filter(models.Doctor.email == "new.doc@mediclinic.com").first()
    assert doc is not None and doc.must_change_password is True


def test_create_receptionist(client):
    r = client.post("/admin/users", json={"firstName": "Front", "lastName": "Desk", "email": "front.desk@mediclinic.com",
                                          "role": "Receptionist", "sendWelcomeEmail": False})
    assert r.status_code == 201 and r.json()["source"] == "receptionist"


def test_create_admin(client):
    r = client.post("/admin/users", json={"firstName": "Super", "lastName": "Admin", "email": "super.admin@mediclinic.com",
                                          "role": "Admin", "sendWelcomeEmail": False})
    assert r.status_code == 201 and r.json()["source"] == "admin"


def test_create_invalid_role_400(client):
    r = client.post("/admin/users", json={"firstName": "Bad", "lastName": "Role", "email": "bad@mediclinic.com",
                                          "role": "Wizard", "sendWelcomeEmail": False})
    assert r.status_code == 400


def test_toggle_disable(client, seed_doctor, db):
    r = client.put(f"/admin/users/doctor/{seed_doctor.id}/toggle")
    assert r.status_code == 200 and r.json()["isActive"] is False and r.json()["passwordEmailed"] is False
    db.refresh(seed_doctor)
    assert seed_doctor.is_active is False


def test_reactivate_emails_new_password(client, seed_doctor, db):
    seed_doctor.is_active = False
    old_hash = seed_doctor.password
    db.commit()
    r = client.put(f"/admin/users/doctor/{seed_doctor.id}/toggle")
    assert r.status_code == 200 and r.json()["isActive"] is True and r.json()["passwordEmailed"] is True
    db.refresh(seed_doctor)
    assert seed_doctor.is_active is True and seed_doctor.must_change_password is True and seed_doctor.password != old_hash


def test_reactivation_audit(client, seed_doctor, db):
    seed_doctor.is_active = False; db.commit()
    client.put(f"/admin/users/doctor/{seed_doctor.id}/toggle")
    log = db.query(models.AuditLog).filter(models.AuditLog.action == "User Enabled").first()
    assert log is not None and "reactivated" in log.details.lower()


def test_toggle_invalid_source_400(client):
    assert client.put("/admin/users/wizard/1/toggle").status_code == 400


def test_toggle_missing_404(client):
    assert client.put("/admin/users/doctor/9999/toggle").status_code == 404


def test_update_info(client, seed_doctor):
    r = client.put(f"/admin/users/doctor/{seed_doctor.id}", json={"firstName": "Rajesh", "lastName": "Kumar", "specialization": "Neurology"})
    assert r.status_code == 200 and r.json()["name"] == "Rajesh Kumar" and r.json()["specialization"] == "Neurology"


def test_update_not_found_404(client):
    assert client.put("/admin/users/doctor/9999", json={"firstName": "X"}).status_code == 404


def test_delete_user(client, seed_receptionist, db):
    r = client.delete(f"/admin/users/receptionist/{seed_receptionist.id}")
    assert r.status_code == 200 and r.json() == {"deleted": True} and db.query(models.Receptionist).count() == 0


def test_delete_audit(client, seed_receptionist, db):
    client.delete(f"/admin/users/receptionist/{seed_receptionist.id}")
    assert db.query(models.AuditLog).filter(models.AuditLog.action == "User Deleted").first() is not None


def test_delete_invalid_source_400(client):
    assert client.delete("/admin/users/wizard/1").status_code == 400


def test_delete_not_found_404(client):
    assert client.delete("/admin/users/admin/9999").status_code == 404


def test_reset_password_endpoint_removed(client, seed_doctor):
    assert client.post(f"/admin/users/doctor/{seed_doctor.id}/reset-password").status_code == 404
