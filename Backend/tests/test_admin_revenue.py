"""Revenue reporting: what was collected, how, and from whom."""
from datetime import timedelta

import models
import time_utils


_seq = iter(range(1, 10_000))


def _pay(db, patient, amount="500.00", method="cash", when=None, status="Success"):
    """Record a completed payment, optionally back-dated."""
    stamp = (when or time_utils.now()).isoformat(timespec="seconds")
    p = models.Payment(
        # A counter, not the timestamp: two payments in the same second would
        # otherwise collide on the unique txnid.
        txnid=f"TXN{next(_seq):06d}",
        patient_id=patient.id, amount=amount, currency="INR",
        purpose="Consultation Fee", status=status, method=method,
        created_at=stamp, completed_at=stamp if status == "Success" else None,
        queue_token="Q-001",
    )
    db.add(p); db.commit()
    return p


# ── Summary ──────────────────────────────────────────────────────────────────

def test_summary_is_empty_with_no_payments(client):
    b = client.get("/admin/payment-summary").json()
    assert b["totalCollected"] == 0 and b["transactionCount"] == 0
    assert b["payingPatients"] == 0 and b["averagePerPatient"] == 0
    assert [m["method"] for m in b["byMethod"]] == ["qr", "card", "cash"]


def test_summary_totals_what_was_collected(client, make_patient, db):
    a = make_patient(name="Pat A", mobile="9111111111")
    b = make_patient(name="Pat B", mobile="9222222222")
    _pay(db, a, "500.00", "cash")
    _pay(db, a, "300.00", "qr")
    _pay(db, b, "500.00", "card")

    s = client.get("/admin/payment-summary").json()
    assert s["totalCollected"] == 1300.0
    assert s["transactionCount"] == 3
    assert s["payingPatients"] == 2
    assert s["averagePerPatient"] == 650.0


def test_only_successful_payments_count(client, make_patient, db):
    p = make_patient()
    _pay(db, p, "500.00", "cash")
    _pay(db, p, "500.00", "cash", status="Cancelled")
    s = client.get("/admin/payment-summary").json()
    assert s["totalCollected"] == 500.0 and s["transactionCount"] == 1


def test_method_split_sums_to_the_total(client, make_patient, db):
    p = make_patient()
    _pay(db, p, "500.00", "qr")
    _pay(db, p, "200.00", "card")
    _pay(db, p, "300.00", "cash")

    s = client.get("/admin/payment-summary").json()
    by = {m["method"]: m for m in s["byMethod"]}
    assert by["qr"]["amount"] == 500.0 and by["card"]["amount"] == 200.0
    assert by["cash"]["amount"] == 300.0
    assert sum(m["amount"] for m in s["byMethod"]) == s["totalCollected"]
    assert round(sum(m["percentage"] for m in s["byMethod"])) == 100


def test_payments_outside_the_window_are_excluded(client, make_patient, db):
    p = make_patient()
    _pay(db, p, "500.00", "cash", when=time_utils.now() - timedelta(days=20))
    assert client.get("/admin/payment-summary").json()["totalCollected"] == 0
    assert client.get("/admin/payment-summary",
                      params={"days": 30}).json()["totalCollected"] == 500.0


def test_collected_change_compares_to_the_previous_window(client, make_patient, db):
    p = make_patient()
    _pay(db, p, "400.00", "cash", when=time_utils.now() - timedelta(days=8))
    _pay(db, p, "600.00", "cash")
    # 600 this week against 400 last week.
    assert client.get("/admin/payment-summary").json()["collectedChange"] == 50.0


def test_unpaid_visits_are_counted(client, make_patient, db):
    paid = make_patient(name="Paid Pat", mobile="9111111111", payment_status="Paid")
    paid.checkin_at = time_utils.now().isoformat(timespec="seconds")
    owing = make_patient(name="Owing Pat", mobile="9222222222", payment_status="Pending")
    owing.checkin_at = time_utils.now().isoformat(timespec="seconds")
    db.commit()
    _pay(db, paid, "500.00", "cash")

    assert client.get("/admin/payment-summary").json()["outstandingVisits"] == 1


# ── Revenue per day ──────────────────────────────────────────────────────────

def test_revenue_flow_spans_the_window(client):
    assert len(client.get("/admin/revenue-flow").json()) == 7
    assert client.get("/admin/revenue-flow", params={"days": 1}).json()[0]["day"] == "Today"


def test_revenue_flow_sums_to_the_summary_total(client, make_patient, db):
    """The chart and the headline figure must agree."""
    p = make_patient()
    _pay(db, p, "500.00", "cash")
    _pay(db, p, "250.00", "qr", when=time_utils.now() - timedelta(days=2))

    flow  = client.get("/admin/revenue-flow").json()
    total = client.get("/admin/payment-summary").json()["totalCollected"]
    assert round(sum(d["amount"] for d in flow), 2) == total == 750.0


def test_revenue_lands_on_the_day_it_was_collected(client, make_patient, db):
    p = make_patient()
    _pay(db, p, "500.00", "cash")
    assert client.get("/admin/revenue-flow").json()[-1]["amount"] == 500.0


# ── Who paid what ────────────────────────────────────────────────────────────

def test_top_payers_is_empty_with_no_payments(client):
    assert client.get("/admin/top-payers").json() == []


def test_top_payers_ranks_by_amount(client, make_patient, db):
    small = make_patient(name="Small Spender", mobile="9111111111")
    big   = make_patient(name="Big Spender", mobile="9222222222")
    _pay(db, small, "200.00", "cash")
    _pay(db, big, "500.00", "qr")
    _pay(db, big, "700.00", "card")

    rows = client.get("/admin/top-payers").json()
    assert [r["name"] for r in rows] == ["Big Spender", "Small Spender"]
    assert rows[0]["amount"] == 1200.0 and rows[0]["payments"] == 2
    assert rows[1]["amount"] == 200.0
    # maxAmount lets the UI size the bars without a second pass.
    assert all(r["maxAmount"] == 1200.0 for r in rows)


def test_top_payers_lists_the_methods_used(client, make_patient, db):
    p = make_patient(name="Mixed Payer")
    _pay(db, p, "300.00", "cash")
    _pay(db, p, "200.00", "qr")
    row = client.get("/admin/top-payers").json()[0]
    assert "Cash" in row["methods"] and "UPI / QR" in row["methods"]
    assert row["patientCode"] == f"MED-{p.id:04d}"


def test_top_payers_respects_the_limit(client, make_patient, db):
    for i in range(4):
        p = make_patient(name=f"Pat {i}", mobile=f"9{i}11111111")
        _pay(db, p, f"{100 * (i + 1)}.00", "cash")
    rows = client.get("/admin/top-payers", params={"limit": 2}).json()
    assert len(rows) == 2 and rows[0]["amount"] == 400.0


def test_top_payer_totals_never_exceed_the_collected_total(client, make_patient, db):
    for i in range(3):
        p = make_patient(name=f"Pat {i}", mobile=f"9{i}11111111")
        _pay(db, p, "500.00", "cash")
    total = client.get("/admin/payment-summary").json()["totalCollected"]
    assert sum(r["amount"] for r in client.get("/admin/top-payers").json()) == total


def test_revenue_endpoints_reject_a_bad_range(client):
    for path in ("/admin/payment-summary", "/admin/revenue-flow", "/admin/top-payers"):
        assert client.get(path, params={"days": 0}).status_code == 422
        assert client.get(path, params={"days": 91}).status_code == 422


# ── The funnel: checked in >= paid >= consulted ───────────────────────────────
# These three counts legitimately differ while a visit is in progress, because
# payment is taken at check-in and the consultation happens afterwards. The
# reports page states the funnel explicitly; these tests pin the arithmetic.

def _check_in(db, patient, when=None):
    patient.checkin_at = (when or time_utils.now()).isoformat(timespec="seconds")
    db.commit()


def _consult(db, patient, when=None):
    day = (when or time_utils.now()).date()
    db.add(models.Consultation(
        patient_id=patient.id, chief_complaint="fever",
        consultation_date=day, doctor_name="Dr. A",
        created_at=(when or time_utils.now()).isoformat(timespec="seconds"),
    ))
    db.commit()


def test_paid_can_exceed_consulted(client, make_patient, db):
    """The exact case that looked wrong: 2 paid, only 1 consulted so far."""
    a = make_patient(name="Pat A", mobile="9111111111")
    b = make_patient(name="Pat B", mobile="9222222222")
    _check_in(db, a); _check_in(db, b)
    _pay(db, a, "500.00", "cash")
    _pay(db, b, "500.00", "qr")
    _consult(db, a)                      # b has paid but is still waiting

    summary  = client.get("/admin/weekly-summary").json()
    payments = client.get("/admin/payment-summary").json()

    assert summary["patientsCheckedIn"] == 2
    assert payments["payingPatients"] == 2
    assert summary["totalPatients"] == 1          # consulted
    assert payments["transactionCount"] == 2


def test_funnel_counts_never_invert(client, make_patient, db):
    """checked in >= paid, and checked in >= consulted."""
    for i in range(3):
        p = make_patient(name=f"Pat {i}", mobile=f"9{i}11111111")
        _check_in(db, p)
        if i < 2:
            _pay(db, p, "500.00", "cash")
        if i < 1:
            _consult(db, p)

    summary  = client.get("/admin/weekly-summary").json()
    payments = client.get("/admin/payment-summary").json()
    assert summary["patientsCheckedIn"] == 3
    assert payments["payingPatients"] == 2
    assert summary["totalPatients"] == 1
    assert summary["patientsCheckedIn"] >= payments["payingPatients"]
    assert summary["patientsCheckedIn"] >= summary["totalPatients"]


def test_unpaid_plus_paid_equals_checked_in(client, make_patient, db):
    paid  = make_patient(name="Paid Pat", mobile="9111111111", payment_status="Paid")
    owing = make_patient(name="Owing Pat", mobile="9222222222", payment_status="Pending")
    _check_in(db, paid); _check_in(db, owing)
    _pay(db, paid, "500.00", "cash")

    summary  = client.get("/admin/weekly-summary").json()
    payments = client.get("/admin/payment-summary").json()
    assert payments["payingPatients"] + payments["outstandingVisits"] \
        == summary["patientsCheckedIn"]


# ── "No baseline" must not be reported as +100% ───────────────────────────────

def test_no_previous_activity_reports_null_not_100pct(client, make_patient, db):
    """
    A previous window with nothing in it has no percentage. Returning 100
    implied the figure had merely doubled.
    """
    p = make_patient()
    _check_in(db, p)
    _pay(db, p, "500.00", "cash")
    _consult(db, p)

    assert client.get("/admin/payment-summary").json()["collectedChange"] is None
    summary = client.get("/admin/weekly-summary").json()
    assert summary["patientsChange"] is None
    assert summary["consultationsChange"] is None


def test_a_real_baseline_still_yields_a_percentage(client, make_patient, db):
    p = make_patient()
    _pay(db, p, "400.00", "cash", when=time_utils.now() - timedelta(days=8))
    _pay(db, p, "600.00", "cash")
    assert client.get("/admin/payment-summary").json()["collectedChange"] == 50.0


def test_zero_in_both_windows_is_zero_not_null(client):
    s = client.get("/admin/weekly-summary").json()
    assert s["patientsChange"] == 0 and s["consultationsChange"] == 0
    assert client.get("/admin/payment-summary").json()["collectedChange"] == 0
