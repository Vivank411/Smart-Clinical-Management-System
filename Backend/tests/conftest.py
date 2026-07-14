"""Shared pytest fixtures — isolated in-memory SQLite, stubbed e-mail."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SMTP_USER", "")
os.environ.setdefault("SMTP_PASSWORD", "")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import database
import models
import email_service
import main
from main import app, _hash

test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
models.Base.metadata.create_all(bind=test_engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[database.get_db] = _override_get_db

email_service.send_welcome_email      = lambda *a, **k: True
email_service.send_reactivation_email = lambda *a, **k: True
email_service.send_reset_email        = lambda *a, **k: True


@pytest.fixture(autouse=True)
def _reset_db():
    models.Base.metadata.drop_all(bind=test_engine)
    models.Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seed_admin(db):
    a = models.Admin(name="Administrator", email="admin@mediclinic.com", password=_hash("admin@123"), is_active=True)
    db.add(a); db.commit(); db.refresh(a)
    return a


@pytest.fixture
def seed_receptionist(db):
    r = models.Receptionist(name="Sarah Williams", email="sarah.williams@mediclinic.com", password=_hash("sarah@123"), is_active=True)
    db.add(r); db.commit(); db.refresh(r)
    return r


@pytest.fixture
def seed_doctor(db):
    d = models.Doctor(name="Dr. Rajesh Sharma", specialization="General Medicine",
                      email="dr.rajesh.sharma@mediclinic.com", password=_hash("rajesh@123"),
                      role="Doctor", is_active=True, available_from="09:00 AM", available_to="05:00 PM")
    db.add(d); db.commit(); db.refresh(d)
    return d


@pytest.fixture
def make_patient(db):
    from datetime import date

    def _make(name="John Doe", dob=date(1990, 5, 15), mobile="9876543210", **extra):
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        p = models.Patient(name=name, gender=extra.pop("gender", "Male"), dob=dob,
                           age=extra.pop("age", age), mobile_number=mobile,
                           status=extra.pop("status", "Registered"), **extra)
        db.add(p); db.commit(); db.refresh(p)
        return p

    return _make


def valid_patient_payload(**overrides):
    from datetime import date
    dob = overrides.pop("dob", "1990-05-15")
    d = date.fromisoformat(dob) if isinstance(dob, str) else dob
    today = date.today()
    age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    body = {"firstName": "John", "lastName": "Doe", "gender": "Male",
            "dob": dob if isinstance(dob, str) else dob.isoformat(),
            "age": age, "mobileNumber": "9876543210"}
    body.update(overrides)
    return body
