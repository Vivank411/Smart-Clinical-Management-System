"""
Reporting calculations for the admin analytics screen.

Every figure on that screen is derived here from one shared definition of a
"visit" so the charts cannot disagree with each other:

    visit = one Consultation row, dated by `consultation_date`.

From that single base:
  * Daily patient count  = visits per day                 -> sums to Total Consultations
  * Consultation status  = visits split by whether a prescription followed
  * Doctor workload      = visits grouped by doctor        -> sums to Total Consultations
  * By department        = visits grouped by the doctor's specialisation
  * Patients seen        = distinct patients across those visits
  * Waiting time         = check-in -> consultation, per visit, averaged
  * Peak hours           = check-ins bucketed by hour of day

Anything that cannot be measured from recorded data (e.g. cancellations, which
the system has no way to record) is reported as zero rather than estimated.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

import models
import time_utils

# Two-hour buckets covering a normal clinic day.
PEAK_BUCKETS: List[Tuple[int, str]] = [
    (8, "8 AM"), (10, "10 AM"), (12, "12 PM"),
    (14, "2 PM"), (16, "4 PM"), (18, "6 PM"), (20, "8 PM"),
]


# ── Range helpers ────────────────────────────────────────────────────────────

def range_bounds(days: int) -> Tuple[date, date]:
    """Inclusive [start, end] window ending today, in clinic-local dates."""
    end = time_utils.today()
    return end - timedelta(days=days - 1), end


def previous_bounds(days: int) -> Tuple[date, date]:
    """The equally-long window immediately before `range_bounds(days)`."""
    start, _ = range_bounds(days)
    prev_end = start - timedelta(days=1)
    return prev_end - timedelta(days=days - 1), prev_end


def day_label(d: date, days: int) -> str:
    if days == 1:
        return "Today"
    return d.strftime("%a") if days <= 7 else d.strftime("%d %b")


# ── Base data set ────────────────────────────────────────────────────────────

def visits(db: Session, start: date, end: date) -> List[models.Consultation]:
    return (
        db.query(models.Consultation)
        .filter(
            models.Consultation.consultation_date >= start,
            models.Consultation.consultation_date <= end,
        )
        .all()
    )


def _patients_by_id(db: Session, ids) -> Dict[int, models.Patient]:
    ids = list({i for i in ids if i is not None})
    if not ids:
        return {}
    rows = db.query(models.Patient).filter(models.Patient.id.in_(ids)).all()
    return {p.id: p for p in rows}


# ── Individual metrics ───────────────────────────────────────────────────────

def patient_flow(db: Session, days: int) -> List[dict]:
    """Visits per day across the window. Sums to total consultations."""
    start, end = range_bounds(days)
    per_day: Dict[date, int] = {}
    for v in visits(db, start, end):
        per_day[v.consultation_date] = per_day.get(v.consultation_date, 0) + 1

    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        out.append({"day": day_label(d, days), "count": per_day.get(d, 0)})
    return out


def _visit_wait_minutes(
    visit: models.Consultation, patient: Optional[models.Patient]
) -> Optional[float]:
    """
    Minutes the patient waited: check-in through to the consultation being
    recorded. Only counted when both timestamps exist and fall on the visit's
    own date — a stale check-in from an earlier visit would otherwise produce a
    multi-day "wait".
    """
    if not patient or not visit.created_at or not patient.checkin_at:
        return None
    checkin = time_utils.parse(patient.checkin_at)
    if not checkin or checkin.date() != visit.consultation_date:
        return None
    return time_utils.minutes_between(patient.checkin_at, visit.created_at)


def waiting_time(db: Session, days: int) -> List[dict]:
    """Average wait per day. Days with no measurable visit report 0."""
    start, end = range_bounds(days)
    rows = visits(db, start, end)
    patients = _patients_by_id(db, [v.patient_id for v in rows])

    per_day: Dict[date, List[float]] = {}
    for v in rows:
        mins = _visit_wait_minutes(v, patients.get(v.patient_id))
        if mins is not None:
            per_day.setdefault(v.consultation_date, []).append(mins)

    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        samples = per_day.get(d, [])
        avg = round(sum(samples) / len(samples), 1) if samples else 0.0
        out.append({"day": day_label(d, days), "mins": avg})
    return out


def average_wait(db: Session, days: int) -> int:
    """
    Mean wait across every measurable visit in the window — the weighted
    counterpart of `waiting_time`, so the summary card and the chart agree.
    """
    start, end = range_bounds(days)
    rows = visits(db, start, end)
    patients = _patients_by_id(db, [v.patient_id for v in rows])
    samples = [
        m for m in (_visit_wait_minutes(v, patients.get(v.patient_id)) for v in rows)
        if m is not None
    ]
    return int(round(sum(samples) / len(samples))) if samples else 0


def consultation_stats(db: Session, days: int) -> List[dict]:
    """
    Visits split by outcome. Completed means a prescription was issued for that
    patient on the same day; everything else is still pending. Cancellations
    are not recordable anywhere in the system, so they are always zero.
    """
    start, end = range_bounds(days)
    rows = visits(db, start, end)
    total = len(rows)
    if total == 0:
        return [
            {"label": "Completed", "count": 0, "percentage": 0.0},
            {"label": "Pending",   "count": 0, "percentage": 0.0},
            {"label": "Cancelled", "count": 0, "percentage": 0.0},
        ]

    issued = {
        (p.patient_id, p.prescription_date)
        for p in db.query(models.Prescription)
        .filter(
            models.Prescription.prescription_date >= start,
            models.Prescription.prescription_date <= end,
        )
        .all()
    }
    completed = sum(1 for v in rows if (v.patient_id, v.consultation_date) in issued)
    pending = total - completed

    pct = lambda n: round(n / total * 100, 1)
    return [
        {"label": "Completed", "count": completed, "percentage": pct(completed)},
        {"label": "Pending",   "count": pending,   "percentage": pct(pending)},
        {"label": "Cancelled", "count": 0,         "percentage": 0.0},
    ]


def doctor_workload(db: Session, days: int, limit: int = 5) -> List[dict]:
    """Visits per doctor in the window, busiest first."""
    start, end = range_bounds(days)
    counts: Dict[str, int] = {}
    for v in visits(db, start, end):
        name = (v.doctor_name or "").strip() or "Unassigned"
        counts[name] = counts.get(name, 0) + 1
    if not counts:
        return []

    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    max_count = ordered[0][1]
    return [{"name": n, "count": c, "maxCount": max_count} for n, c in ordered]


def department_stats(db: Session, days: int, limit: int = 5) -> List[dict]:
    """
    Visits grouped by the treating doctor's specialisation. Everything past the
    top `limit` is folded into "Other" so the percentages still total 100 and
    the donut matches the visit count the rest of the page reports.
    """
    start, end = range_bounds(days)
    rows = visits(db, start, end)
    total = len(rows)
    if total == 0:
        return []

    spec_by_doctor = {
        d.name: d.specialization for d in db.query(models.Doctor).all()
    }
    counts: Dict[str, int] = {}
    for v in rows:
        dept = spec_by_doctor.get((v.doctor_name or "").strip(), "Unassigned")
        counts[dept] = counts.get(dept, 0) + 1

    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    head, tail = ordered[:limit], ordered[limit:]
    if tail:
        head.append(("Other", sum(c for _, c in tail)))

    return [
        {"department": name, "count": c, "percentage": round(c / total * 100, 1)}
        for name, c in head
    ]


def _peak_bucket(hour: int) -> int:
    """
    Bucket start for a given hour. Early-morning and late-night check-ins fall
    into the nearest charted bucket rather than being dropped from the total.
    """
    first, last = PEAK_BUCKETS[0][0], PEAK_BUCKETS[-1][0]
    if hour < first:
        return first
    if hour >= last + 2:
        return last
    return hour - ((hour - first) % 2)


def peak_hours(db: Session, days: int) -> List[dict]:
    """Check-ins per two-hour bucket — how busy the clinic gets, and when."""
    start, end = range_bounds(days)
    counts = {h: 0 for h, _ in PEAK_BUCKETS}

    for (stamp,) in db.query(models.Patient.checkin_at).filter(
        models.Patient.checkin_at.isnot(None)
    ).all():
        dt = time_utils.parse(stamp)
        if not dt or not (start <= dt.date() <= end):
            continue
        counts[_peak_bucket(dt.hour)] += 1

    return [{"hour": label, "count": counts[h]} for h, label in PEAK_BUCKETS]


def patients_seen(db: Session, start: date, end: date) -> int:
    """Distinct patients a doctor actually consulted."""
    return len({v.patient_id for v in visits(db, start, end)})


def patients_checked_in(db: Session, start: date, end: date) -> int:
    """
    Distinct patients who arrived at the desk.

    Always >= patients_seen: a patient checks in, pays, then waits for the
    doctor. Reporting only the consulted figure made the payment counts look
    contradictory, because money is taken before the consultation happens.
    """
    count = 0
    for (stamp,) in db.query(models.Patient.checkin_at).filter(
        models.Patient.checkin_at.isnot(None)
    ).all():
        when = time_utils.parse_date(stamp)
        if when and start <= when <= end:
            count += 1
    return count


def summary(db: Session, days: int) -> dict:
    """Headline figures for the window, each compared to the window before it."""
    start, end = range_bounds(days)
    prev_start, prev_end = previous_bounds(days)

    seen = patients_seen(db, start, end)
    prev_seen = patients_seen(db, prev_start, prev_end)
    consults = len(visits(db, start, end))
    prev_consults = len(visits(db, prev_start, prev_end))

    avg_wait = average_wait(db, days)
    prev_wait = _average_wait_between(db, prev_start, prev_end)

    return {
        "totalPatients": seen,
        "patientsCheckedIn": patients_checked_in(db, start, end),
        "totalConsultations": consults,
        "avgWaitingTime": avg_wait,
        "cancelledConsultations": 0,
        "patientsChange": _pct_change(seen, prev_seen),
        "consultationsChange": _pct_change(consults, prev_consults),
        "waitingTimeChange": avg_wait - prev_wait,
        "cancelledChange": 0.0,
    }


def _average_wait_between(db: Session, start: date, end: date) -> int:
    rows = visits(db, start, end)
    patients = _patients_by_id(db, [v.patient_id for v in rows])
    samples = [
        m for m in (_visit_wait_minutes(v, patients.get(v.patient_id)) for v in rows)
        if m is not None
    ]
    return int(round(sum(samples) / len(samples))) if samples else 0


# ── Money ────────────────────────────────────────────────────────────────────
# Revenue is counted from payments actually collected, dated by when they were
# confirmed rather than when they were started — an abandoned attempt from
# yesterday that is settled today belongs in today's takings.

METHOD_LABELS = {"qr": "UPI / QR", "card": "Card", "cash": "Cash"}


def _amount(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def collected_payments(db: Session, start: date, end: date) -> List[models.Payment]:
    """Successful payments confirmed inside the window."""
    rows = db.query(models.Payment).filter(models.Payment.status == "Success").all()
    out = []
    for p in rows:
        # Fall back to created_at for rows written before completed_at existed.
        when = time_utils.parse_date(p.completed_at or p.created_at)
        if when and start <= when <= end:
            out.append(p)
    return out


def revenue_flow(db: Session, days: int) -> List[dict]:
    """Amount collected per day. Sums to `payment_summary.totalCollected`."""
    start, end = range_bounds(days)
    per_day: Dict[date, float] = {}
    for p in collected_payments(db, start, end):
        when = time_utils.parse_date(p.completed_at or p.created_at)
        per_day[when] = per_day.get(when, 0.0) + _amount(p.amount)

    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        out.append({"day": day_label(d, days), "amount": round(per_day.get(d, 0.0), 2)})
    return out


def payment_summary(db: Session, days: int) -> dict:
    """Takings for the window, split by how the money came in."""
    start, end = range_bounds(days)
    rows = collected_payments(db, start, end)
    prev_start, prev_end = previous_bounds(days)
    prev_total = sum(_amount(p.amount) for p in collected_payments(db, prev_start, prev_end))

    total = sum(_amount(p.amount) for p in rows)
    payers = {p.patient_id for p in rows}

    by_method = []
    for key, label in METHOD_LABELS.items():
        subset = [p for p in rows if p.method == key]
        amount = sum(_amount(p.amount) for p in subset)
        by_method.append({
            "method": key,
            "label": label,
            "count": len(subset),
            "amount": round(amount, 2),
            "percentage": round(amount / total * 100, 1) if total else 0.0,
        })

    change = _pct_change(total, prev_total)

    # Unpaid visits: consultations in the window whose patient never settled.
    unpaid = db.query(models.Patient).filter(
        models.Patient.payment_status == "Pending",
        models.Patient.checkin_at.isnot(None),
    ).all()
    outstanding = 0
    for patient in unpaid:
        when = time_utils.parse_date(patient.checkin_at)
        if when and start <= when <= end:
            outstanding += 1

    return {
        "totalCollected": round(total, 2),
        "transactionCount": len(rows),
        "payingPatients": len(payers),
        "averagePerPatient": round(total / len(payers), 2) if payers else 0.0,
        "collectedChange": change,
        "outstandingVisits": outstanding,
        "byMethod": by_method,
    }


def top_payers(db: Session, days: int, limit: int = 8) -> List[dict]:
    """Patients ranked by what they actually paid in the window."""
    start, end = range_bounds(days)
    rows = collected_payments(db, start, end)
    if not rows:
        return []

    totals: Dict[int, dict] = {}
    for p in rows:
        entry = totals.setdefault(p.patient_id, {"amount": 0.0, "count": 0, "methods": set()})
        entry["amount"] += _amount(p.amount)
        entry["count"] += 1
        entry["methods"].add(METHOD_LABELS.get(p.method, p.method))

    patients = _patients_by_id(db, totals.keys())
    ranked = sorted(totals.items(), key=lambda kv: kv[1]["amount"], reverse=True)[:limit]
    top_amount = ranked[0][1]["amount"] if ranked else 0.0

    return [
        {
            "patientId": pid,
            "patientCode": f"MED-{pid:04d}",
            "name": patients[pid].name if pid in patients else f"Patient #{pid}",
            "amount": round(entry["amount"], 2),
            "payments": entry["count"],
            "methods": ", ".join(sorted(entry["methods"])),
            "maxAmount": round(top_amount, 2),
        }
        for pid, entry in ranked
    ]


def _pct_change(current: float, previous: float) -> Optional[float]:
    """
    Percentage change, or None when the previous window had nothing to compare
    against. Reporting "+100%" against a baseline of zero implied the figure
    had merely doubled, when in fact there was no prior activity at all.
    """
    if previous > 0:
        return round((current - previous) / previous * 100, 1)
    return None if current > 0 else 0.0
