"""Sending a saved prescription to the patient by email or WhatsApp."""
from urllib.parse import unquote

import pytest

import email_service
import models
import time_utils


@pytest.fixture
def sent_mail(monkeypatch):
    """Capture outgoing prescription emails instead of hitting SMTP."""
    captured = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(email_service, "send_prescription_email", _fake)
    return captured


@pytest.fixture
def prescription(db, make_patient):
    p = make_patient(email="pat@example.com")
    rx = models.Prescription(
        patient_id=p.id,
        medications='[{"name": "Amoxicillin", "dosage": "500mg", "frequency": "BD", "duration": "5 days"}]',
        doctor_name="Dr. Rajesh Sharma",
        prescription_date=time_utils.today(),
        notes="Take after food.",
        created_at=time_utils.now_iso(),
    )
    db.add(rx); db.commit(); db.refresh(rx)
    return rx, p


# ── Email ────────────────────────────────────────────────────────────────────

def test_send_email_uses_patient_address(client, prescription, sent_mail):
    rx, p = prescription
    b = client.post(f"/prescriptions/{rx.id}/send", json={"channel": "email"}).json()

    assert b["sent"] is True and b["target"] == "pat@example.com"
    assert sent_mail["to"] == "pat@example.com"
    assert sent_mail["patient_name"] == p.name
    assert sent_mail["medications"][0]["name"] == "Amoxicillin"
    assert sent_mail["notes"] == "Take after food."


def test_send_email_accepts_an_override_address(client, prescription, sent_mail):
    rx, _ = prescription
    b = client.post(f"/prescriptions/{rx.id}/send",
                    json={"channel": "email", "email": "Other@Example.com"}).json()
    assert b["target"] == "other@example.com" and sent_mail["to"] == "other@example.com"


def test_send_email_without_an_address_is_a_clear_400(client, db, make_patient):
    p = make_patient()          # no email on file
    rx = models.Prescription(patient_id=p.id, medications="[]",
                             prescription_date=time_utils.today())
    db.add(rx); db.commit(); db.refresh(rx)

    r = client.post(f"/prescriptions/{rx.id}/send", json={"channel": "email"})
    assert r.status_code == 400 and "no email address" in r.json()["detail"].lower()


def test_send_email_records_delivery(client, prescription, sent_mail, db):
    rx, _ = prescription
    client.post(f"/prescriptions/{rx.id}/send", json={"channel": "email"})
    db.expire_all()
    stored = db.query(models.Prescription).filter(models.Prescription.id == rx.id).first()
    assert time_utils.parse(stored.sent_email_at) is not None


def test_failed_send_is_not_recorded_as_delivered(client, prescription, monkeypatch, db):
    """SMTP being unconfigured must not leave a false 'sent' trail."""
    rx, _ = prescription
    monkeypatch.setattr(email_service, "send_prescription_email", lambda **k: False)

    b = client.post(f"/prescriptions/{rx.id}/send", json={"channel": "email"}).json()
    assert b["sent"] is False and "not configured" in b["message"]

    db.expire_all()
    assert db.query(models.Prescription).filter(
        models.Prescription.id == rx.id).first().sent_email_at is None


def test_failed_send_is_audited_as_failed(client, prescription, monkeypatch, db):
    rx, _ = prescription
    monkeypatch.setattr(email_service, "send_prescription_email", lambda **k: False)
    client.post(f"/prescriptions/{rx.id}/send", json={"channel": "email"})

    log = db.query(models.AuditLog).filter(models.AuditLog.action == "Prescription Sent").first()
    assert log is not None and log.status == "Failed"


# ── WhatsApp ─────────────────────────────────────────────────────────────────

def test_send_whatsapp_builds_a_prefilled_link(client, prescription):
    rx, p = prescription
    b = client.post(f"/prescriptions/{rx.id}/send", json={"channel": "whatsapp"}).json()

    assert b["sent"] is True
    # A local 10-digit number is promoted to international form for wa.me.
    assert b["whatsappUrl"].startswith("https://wa.me/919876543210?text=")

    text = unquote(b["whatsappUrl"].split("?text=", 1)[1])
    assert f"RX-{rx.id:04d}" in text
    assert "Amoxicillin — 500mg · BD · for 5 days" in text
    assert p.name in text and "Take after food." in text


def test_send_whatsapp_without_a_number_is_a_clear_400(client, db, make_patient):
    p = make_patient()
    p.mobile_number = None
    rx = models.Prescription(patient_id=p.id, medications="[]",
                             prescription_date=time_utils.today())
    db.add(rx); db.commit(); db.refresh(rx)

    r = client.post(f"/prescriptions/{rx.id}/send", json={"channel": "whatsapp"})
    assert r.status_code == 400 and "no mobile number" in r.json()["detail"].lower()


# ── Guards ───────────────────────────────────────────────────────────────────

def test_send_unknown_prescription_404(client):
    assert client.post("/prescriptions/9999/send", json={"channel": "email"}).status_code == 404


def test_send_rejects_an_unknown_channel(client, prescription):
    rx, _ = prescription
    assert client.post(f"/prescriptions/{rx.id}/send", json={"channel": "sms"}).status_code == 422
