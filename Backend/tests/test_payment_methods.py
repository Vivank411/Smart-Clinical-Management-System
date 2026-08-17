"""Counter payment collection: QR, card and cash — all confirmed at the desk."""
import models
import time_utils

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="


def _upload_qr(client, label="MediClinic — clinic@okhdfcbank"):
    r = client.put("/payments/qr", json={"image": PNG, "label": label})
    assert r.status_code == 200, r.text
    return r.json()


def _start(client, patient_id, method):
    r = client.post("/payments/initiate", json={"patientId": patient_id, "method": method})
    assert r.status_code == 200, r.text
    return r.json()


# ── Config & QR upload ───────────────────────────────────────────────────────

def test_config_reports_the_flat_fee(client):
    cfg = client.get("/payments/config").json()
    assert cfg["amount"] == "500.00" and cfg["currency"] == "INR"
    assert cfg["qrConfigured"] is False and cfg["qrImage"] is None


def test_qr_upload_is_visible_to_everyone(client):
    """The QR belongs to the clinic, so it must come back from the server."""
    _upload_qr(client)
    cfg = client.get("/payments/config").json()
    assert cfg["qrConfigured"] is True
    assert cfg["qrImage"] == PNG
    assert cfg["qrLabel"] == "MediClinic — clinic@okhdfcbank"


def test_qr_upload_replaces_the_previous_one(client):
    _upload_qr(client, label="Old")
    _upload_qr(client, label="New")
    assert client.get("/payments/config").json()["qrLabel"] == "New"


def test_qr_can_be_removed(client):
    _upload_qr(client)
    client.put("/payments/qr", json={"image": None, "label": None})
    cfg = client.get("/payments/config").json()
    assert cfg["qrConfigured"] is False and cfg["qrImage"] is None


def test_qr_rejects_a_non_image(client):
    r = client.put("/payments/qr", json={"image": "data:text/html;base64,PHNjcmlwdD4="})
    assert r.status_code == 400 and "PNG" in r.json()["detail"]


def test_qr_rejects_an_oversized_image(client):
    r = client.put("/payments/qr", json={"image": "data:image/png;base64," + "A" * (2 * 1024 * 1024 + 10)})
    assert r.status_code == 400 and "too large" in r.json()["detail"].lower()


def test_qr_upload_is_audited(client, db):
    _upload_qr(client)
    log = db.query(models.AuditLog).filter(
        models.AuditLog.action == "Payment QR Updated").first()
    assert log is not None


# ── Starting a payment ───────────────────────────────────────────────────────

def test_qr_method_works_without_an_upload(client, make_patient):
    """The app ships with a default QR image, so the option always works."""
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "qr")
    assert body["method"] == "qr" and body["status"] == "Pending"


def test_qr_method_works_once_uploaded(client, make_patient):
    _upload_qr(client)
    body = _start(client, make_patient(payment_status="Pending").id, "qr")
    assert body["method"] == "qr" and body["status"] == "Pending"


def test_cash_and_card_need_no_qr(client, make_patient):
    for i, method in enumerate(("cash", "card")):
        p = make_patient(name=f"Pat {i}", mobile=f"9{i}11111111", payment_status="Pending")
        assert _start(client, p.id, method)["method"] == method


def test_initiate_rejects_an_unknown_method(client, make_patient):
    p = make_patient(payment_status="Pending")
    assert client.post("/payments/initiate",
                       json={"patientId": p.id, "method": "netbanking"}).status_code == 422


def test_initiate_unknown_patient_404(client):
    assert client.post("/payments/initiate",
                       json={"patientId": 9999, "method": "cash"}).status_code == 404


def test_cannot_start_a_second_payment_once_paid(client, make_patient):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    client.post(f"/payments/{body['txnid']}/confirm", json={})
    assert client.post("/payments/initiate",
                       json={"patientId": p.id, "method": "cash"}).status_code == 409


# ── Confirming — the moment the token is issued ──────────────────────────────

def test_confirming_cash_issues_the_token(client, make_patient, db):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    result = client.post(f"/payments/{body['txnid']}/confirm",
                         json={"collectedBy": "Sarah Williams"}).json()

    assert result["status"] == "Success" and result["queueToken"] == "Q-001"
    assert result["collectedBy"] == "Sarah Williams"
    db.expire_all()
    assert db.query(models.Patient).filter(
        models.Patient.id == p.id).first().payment_status == "Paid"


def test_confirming_qr_records_the_reference(client, make_patient):
    _upload_qr(client)
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "qr")
    result = client.post(f"/payments/{body['txnid']}/confirm",
                         json={"reference": "428911223344"}).json()
    assert result["status"] == "Success" and result["reference"] == "428911223344"


def test_confirming_card_records_last4_only(client, make_patient):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "card")
    result = client.post(f"/payments/{body['txnid']}/confirm",
                         json={"cardLast4": "4242", "reference": "APPR7781"}).json()
    assert result["cardLast4"] == "4242" and result["reference"] == "APPR7781"


def test_confirm_falls_back_to_the_signed_in_user(client, make_patient):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    result = client.post(f"/payments/{body['txnid']}/confirm", json={},
                         headers={"x-user-name": "Reception Desk 2"}).json()
    assert result["collectedBy"] == "Reception Desk 2"


def test_confirm_is_idempotent(client, make_patient):
    """A double-tap on a slow connection must not issue two tokens."""
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    first = client.post(f"/payments/{body['txnid']}/confirm", json={}).json()["queueToken"]
    assert client.post(f"/payments/{body['txnid']}/confirm", json={}).json()["queueToken"] == first


def test_confirm_unknown_transaction_404(client):
    assert client.post("/payments/NOPE/confirm", json={}).status_code == 404


# ── Card data must not be storable ───────────────────────────────────────────

def test_a_full_card_number_in_reference_is_refused(client, make_patient):
    """
    Holding a PAN would put the clinic under PCI-DSS and turn any breach of
    this database into a breach of every patient's card.
    """
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "card")
    r = client.post(f"/payments/{body['txnid']}/confirm",
                    json={"reference": "4111 1111 1111 1111"})
    assert r.status_code == 422
    assert "card number" in str(r.json()).lower()


def test_card_last4_must_be_exactly_four_digits(client, make_patient):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "card")
    for bad in ("12345", "12a4", "123"):
        r = client.post(f"/payments/{body['txnid']}/confirm", json={"cardLast4": bad})
        assert r.status_code == 422, bad


def test_last4_is_not_kept_for_non_card_methods(client, make_patient):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    result = client.post(f"/payments/{body['txnid']}/confirm",
                         json={"cardLast4": "4242"}).json()
    assert result["cardLast4"] is None


# ── Cancelling ───────────────────────────────────────────────────────────────

def test_cancelling_leaves_the_patient_unpaid(client, make_patient, db):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    result = client.post(f"/payments/{body['txnid']}/cancel").json()

    assert result["status"] == "Cancelled" and result["queueToken"] is None
    db.expire_all()
    patient = db.query(models.Patient).filter(models.Patient.id == p.id).first()
    assert patient.payment_status == "Pending" and patient.queue_token is None


def test_a_collected_payment_cannot_be_cancelled(client, make_patient):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    client.post(f"/payments/{body['txnid']}/confirm", json={})
    r = client.post(f"/payments/{body['txnid']}/cancel")
    assert r.status_code == 409 and "already been collected" in r.json()["detail"]


def test_a_cancelled_payment_cannot_be_confirmed(client, make_patient):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    client.post(f"/payments/{body['txnid']}/cancel")
    r = client.post(f"/payments/{body['txnid']}/confirm", json={})
    assert r.status_code == 409 and "cancelled" in r.json()["detail"].lower()


# ── Tokens ───────────────────────────────────────────────────────────────────

def test_all_methods_share_one_daily_sequence(client, make_patient):
    _upload_qr(client)
    tokens = []
    for i, method in enumerate(("cash", "qr", "card")):
        p = make_patient(name=f"Pat {i}", mobile=f"9{i}11111111", payment_status="Pending")
        body = _start(client, p.id, method)
        tokens.append(client.post(f"/payments/{body['txnid']}/confirm", json={}).json()["queueToken"])
    assert tokens == ["Q-001", "Q-002", "Q-003"]


def test_token_sequence_restarts_each_day(client, make_patient, db):
    from datetime import timedelta
    stale = make_patient(name="Yesterday Pat", mobile="9111111111")
    stale.queue_token = "Q-007"
    stale.token_issued_on = (time_utils.today() - timedelta(days=1)).isoformat()
    db.commit()

    p = make_patient(name="Today Pat", mobile="9222222222", payment_status="Pending")
    body = _start(client, p.id, "cash")
    assert client.post(f"/payments/{body['txnid']}/confirm", json={}).json()["queueToken"] == "Q-001"


def test_token_arrives_only_after_paying(client, db):
    """The full order: register -> check in -> pay -> token."""
    from tests.conftest import valid_patient_payload
    pid = client.post("/patients", json=valid_patient_payload()).json()["id"]
    client.put(f"/patients/{pid}", json={"status": "Checked-In", "doctor": "Dr. A"})
    assert client.get(f"/patients/{pid}").json()["queueToken"] is None

    body = _start(client, pid, "cash")
    client.post(f"/payments/{body['txnid']}/confirm", json={})

    patient = client.get(f"/patients/{pid}").json()
    assert patient["queueToken"] == "Q-001" and patient["paymentStatus"] == "Paid"


def test_checkin_is_never_blocked_by_payment(client):
    from tests.conftest import valid_patient_payload
    pid = client.post("/patients", json=valid_patient_payload()).json()["id"]
    r = client.put(f"/patients/{pid}", json={"status": "Checked-In", "doctor": "Dr. A"})
    assert r.status_code == 200 and r.json()["paymentStatus"] == "Pending"


# ── History & audit ──────────────────────────────────────────────────────────

def test_payment_history_is_newest_first(client, make_patient):
    p = make_patient(payment_status="Pending")
    first = _start(client, p.id, "cash")
    client.post(f"/payments/{first['txnid']}/cancel")
    second = _start(client, p.id, "card")

    rows = client.get(f"/payments/patient/{p.id}").json()
    assert [r["txnid"] for r in rows] == [second["txnid"], first["txnid"]]
    assert rows[1]["status"] == "Cancelled"


def test_collection_is_audited_with_method_and_token(client, make_patient, db):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    client.post(f"/payments/{body['txnid']}/confirm", json={"collectedBy": "Sarah Williams"})

    log = db.query(models.AuditLog).filter(
        models.AuditLog.action == "Payment Received").first()
    assert log is not None
    assert "Q-001" in log.details and "cash" in log.details


def test_cancellation_is_audited(client, make_patient, db):
    p = make_patient(payment_status="Pending")
    body = _start(client, p.id, "cash")
    client.post(f"/payments/{body['txnid']}/cancel")
    assert db.query(models.AuditLog).filter(
        models.AuditLog.action == "Payment Cancelled").first() is not None
