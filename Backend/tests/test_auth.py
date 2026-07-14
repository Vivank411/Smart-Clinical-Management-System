"""Auth endpoints: /auth/login, /auth/users, /auth/change-password."""


def test_login_doctor_success(client, seed_doctor):
    r = client.post("/auth/login", json={"email": "dr.rajesh.sharma@mediclinic.com", "password": "rajesh@123"})
    assert r.status_code == 200
    b = r.json()
    assert b["name"] == "Dr. Rajesh Sharma"
    assert b["role"] == "Doctor"
    assert b["specialization"] == "General Medicine"
    assert b["mustChangePassword"] is False


def test_login_admin_success(client, seed_admin):
    r = client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "admin@123"})
    assert r.status_code == 200 and r.json()["role"] == "Admin"


def test_login_receptionist_success(client, seed_receptionist):
    r = client.post("/auth/login", json={"email": "sarah.williams@mediclinic.com", "password": "sarah@123"})
    assert r.status_code == 200 and r.json()["role"] == "Receptionist"


def test_login_case_insensitive(client, seed_admin):
    assert client.post("/auth/login", json={"email": "ADMIN@MediClinic.com", "password": "admin@123"}).status_code == 200


def test_login_wrong_password_401(client, seed_doctor):
    r = client.post("/auth/login", json={"email": "dr.rajesh.sharma@mediclinic.com", "password": "nope"})
    assert r.status_code == 401 and r.json()["detail"] == "Incorrect password"


def test_login_unknown_email_401(client):
    r = client.post("/auth/login", json={"email": "ghost@mediclinic.com", "password": "x"})
    assert r.status_code == 401 and "No account found" in r.json()["detail"]


def test_login_deactivated_403(client, seed_doctor, db):
    seed_doctor.is_active = False; db.commit()
    r = client.post("/auth/login", json={"email": "dr.rajesh.sharma@mediclinic.com", "password": "rajesh@123"})
    assert r.status_code == 403 and "deactivated" in r.json()["detail"].lower()


def test_login_sql_injection(client, seed_admin):
    r = client.post("/auth/login", json={"email": "' OR 1=1 --", "password": "x"})
    assert r.status_code == 401


def test_login_missing_email_422(client):
    assert client.post("/auth/login", json={"password": "x"}).status_code == 422


def test_login_missing_password_422(client):
    assert client.post("/auth/login", json={"email": "a@b.com"}).status_code == 422


def test_login_audit_logged(client, seed_admin, db):
    import models
    client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "admin@123"})
    logs = db.query(models.AuditLog).filter(models.AuditLog.action == "Login").all()
    assert len(logs) == 1 and logs[0].module == "Authentication"


def test_failed_login_audit_logged(client, seed_admin, db):
    import models
    client.post("/auth/login", json={"email": "admin@mediclinic.com", "password": "wrong"})
    logs = db.query(models.AuditLog).filter(models.AuditLog.status == "Failed").all()
    assert len(logs) == 1 and logs[0].action == "Failed Login"


def test_auth_users_all(client, seed_doctor, seed_admin, seed_receptionist):
    r = client.get("/auth/users")
    assert r.status_code == 200
    assert {u["role"] for u in r.json()} == {"Doctor", "Admin", "Receptionist"}


def test_auth_users_filter_role(client, seed_doctor, seed_admin):
    r = client.get("/auth/users", params={"role": "Doctor"})
    assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["role"] == "Doctor"


def test_auth_users_filter_junior(client, seed_doctor, db):
    import models
    db.add(models.Doctor(name="Dr. Amit", specialization="ENT", role="Junior Doctor", email="a@x.com")); db.commit()
    r = client.get("/auth/users", params={"role": "Junior Doctor"})
    assert r.status_code == 200 and all(u["role"] == "Junior Doctor" for u in r.json()) and len(r.json()) == 1


def test_auth_users_invalid_role_400(client):
    assert client.get("/auth/users", params={"role": "Wizard"}).status_code == 400


def test_auth_users_no_password_leak(client, seed_doctor):
    assert all(u["password"] == "" for u in client.get("/auth/users").json())


def test_change_password_success(client, seed_doctor):
    r = client.post("/auth/change-password", json={"email": "dr.rajesh.sharma@mediclinic.com",
                                                   "currentPassword": "rajesh@123", "newPassword": "brandNew@123"})
    assert r.status_code == 200 and r.json() == {"success": True}
    assert client.post("/auth/login", json={"email": "dr.rajesh.sharma@mediclinic.com", "password": "brandNew@123"}).status_code == 200
    assert client.post("/auth/login", json={"email": "dr.rajesh.sharma@mediclinic.com", "password": "rajesh@123"}).status_code == 401


def test_change_password_clears_flag(client, seed_doctor, db):
    seed_doctor.must_change_password = True; db.commit()
    client.post("/auth/change-password", json={"email": "dr.rajesh.sharma@mediclinic.com",
                                               "currentPassword": "rajesh@123", "newPassword": "brandNew@123"})
    db.refresh(seed_doctor)
    assert seed_doctor.must_change_password is False


def test_change_password_wrong_current_401(client, seed_doctor):
    r = client.post("/auth/change-password", json={"email": "dr.rajesh.sharma@mediclinic.com",
                                                   "currentPassword": "wrong", "newPassword": "brandNew@123"})
    assert r.status_code == 401


def test_change_password_weak_400(client, seed_doctor):
    r = client.post("/auth/change-password", json={"email": "dr.rajesh.sharma@mediclinic.com",
                                                   "currentPassword": "rajesh@123", "newPassword": "short"})
    assert r.status_code == 400 and "at least 8" in r.json()["detail"]


def test_change_password_unknown_404(client):
    r = client.post("/auth/change-password", json={"email": "ghost@mediclinic.com",
                                                   "currentPassword": "x", "newPassword": "brandNew@123"})
    assert r.status_code == 404
