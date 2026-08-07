"""
Clinical Safety Engine — rule-based conflict detection.

Detection is deliberately deterministic and AI-free: every conflict raised here
is traceable to a database row. The AI layer (ai_service) only explains what
this module has already found; it never decides whether a conflict exists.
"""

import re
from typing import List, Optional

from sqlalchemy.orm import Session

import models

# Frequency label -> administrations per day. Keys match the frontend's
# FREQUENCIES list; anything unrecognised is treated as once daily so a
# dosage check never silently disappears.
FREQUENCY_PER_DAY = {
    "OD": 1, "BD": 2, "TDS": 3, "QID": 4, "SOS": 1,
    "AT NIGHT": 1, "BEFORE MEAL": 3, "AFTER MEAL": 3,
}

SEVERITY_RANK = {"High": 3, "Moderate": 2, "Low": 1}


def normalise_allergen(text: str) -> str:
    """Uppercase, strip punctuation and any parenthetical note ('Penicillin (rash)')."""
    text = re.sub(r"\(.*?\)", " ", text or "")
    return re.sub(r"[^A-Z0-9 ]", " ", text.upper()).strip()


def parse_dose_mg(dosage: str) -> Optional[float]:
    """
    '500mg' -> 500.0, '250mg/5ml' -> 250.0, '2 tablets' -> None.
    Returns None when the strength isn't expressed in mg — the dosage rule is
    then skipped rather than guessed at.
    """
    if not dosage:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg", dosage, re.IGNORECASE)
    return float(m.group(1)) if m else None


def doses_per_day(frequency: str) -> int:
    if not frequency:
        return 1
    head = frequency.split("(")[0].strip().upper()
    return FREQUENCY_PER_DAY.get(head, 1)


def _conflict(kind: str, severity: str, title: str, detail: str, **extra) -> dict:
    return {"type": kind, "severity": severity, "title": title, "detail": detail, **extra}


# ── Individual checks ─────────────────────────────────────────────────────────

def check_allergy(db: Session, patient_id: int, med: Optional[models.Medication],
                  medicine_name: str) -> List[dict]:
    """Patient allergen -> allergy_mapping -> drug class of the selected medicine."""
    allergies = db.query(models.PatientAllergy).filter(
        models.PatientAllergy.patient_id == patient_id
    ).all()
    if not allergies or med is None or not med.drug_class:
        return []

    conflicts = []
    for allergy in allergies:
        mappings = db.query(models.AllergyMapping).filter(
            models.AllergyMapping.allergen == allergy.allergen,
            models.AllergyMapping.drug_class == med.drug_class,
        ).all()
        for mapping in mappings:
            severity = allergy.severity or mapping.severity
            conflicts.append(_conflict(
                "allergy", severity,
                "Allergy Conflict Detected",
                "The selected medicine may cause an allergic reaction in this patient.",
                allergen=allergy.display_name,
                allergenSeverity=severity,
                drugClass=med.drug_class,
                medicine=medicine_name,
            ))
    return conflicts


def check_interactions(db: Session, med: Optional[models.Medication],
                       medicine_name: str, current: List[dict],
                       db_meds: dict) -> List[dict]:
    """Selected medicine's class vs the class of every other medicine on the script."""
    if med is None or not med.drug_class:
        return []

    conflicts = []
    for other in current:
        other_name = (other.get("name") or "").strip()
        if not other_name or other_name.lower() == medicine_name.lower():
            continue
        other_med = db_meds.get(other_name.lower())
        if other_med is None or not other_med.drug_class:
            continue

        a, b = med.drug_class, other_med.drug_class
        rows = db.query(models.DrugInteraction).filter(
            ((models.DrugInteraction.drug_class_a == a) & (models.DrugInteraction.drug_class_b == b))
            | ((models.DrugInteraction.drug_class_a == b) & (models.DrugInteraction.drug_class_b == a))
        ).all()
        for row in rows:
            conflicts.append(_conflict(
                "interaction", row.severity,
                "Drug Interaction Detected",
                row.description,
                medicine=medicine_name,
                interactsWith=other_name,
                drugClass=a,
                otherDrugClass=b,
            ))
    return conflicts


def check_duplicate(med: Optional[models.Medication], medicine_name: str,
                    current: List[dict], db_meds: dict) -> List[dict]:
    """Same medicine twice, or two medicines from the same therapeutic class."""
    conflicts = []
    for other in current:
        other_name = (other.get("name") or "").strip()
        if not other_name:
            continue

        if other_name.lower() == medicine_name.lower():
            conflicts.append(_conflict(
                "duplicate", "Moderate",
                "Duplicate Medicine",
                "This medicine is already on the prescription.",
                medicine=medicine_name, duplicateOf=other_name,
            ))
            continue

        other_med = db_meds.get(other_name.lower())
        if med is not None and other_med is not None and med.drug_class \
                and med.drug_class == other_med.drug_class:
            conflicts.append(_conflict(
                "duplicate", "Moderate",
                "Therapeutic Duplication",
                f"Both medicines belong to {med.drug_class} — prescribing both may "
                f"result in an unintended double dose.",
                medicine=medicine_name, duplicateOf=other_name, drugClass=med.drug_class,
            ))
    return conflicts


def check_dosage(med: Optional[models.Medication], medicine_name: str,
                 dosage: str, frequency: str) -> List[dict]:
    """Single-dose and computed daily-dose ceilings from medicine_master."""
    if med is None:
        return []
    single = parse_dose_mg(dosage)
    if single is None:
        return []   # strength not in mg — nothing reliable to compare against

    conflicts = []
    per_day = doses_per_day(frequency)
    daily = single * per_day

    if med.max_single_dose_mg and single > med.max_single_dose_mg:
        conflicts.append(_conflict(
            "dosage", "High",
            "Dosage Above Recommended Limit",
            f"A single dose of {single:g}mg exceeds the maximum recommended single "
            f"dose of {med.max_single_dose_mg}mg for {medicine_name}.",
            medicine=medicine_name, prescribedDose=f"{single:g}mg",
            maxDose=f"{med.max_single_dose_mg}mg",
        ))

    if med.max_daily_dose_mg and daily > med.max_daily_dose_mg:
        conflicts.append(_conflict(
            "dosage", "High",
            "Daily Dose Above Recommended Limit",
            f"{single:g}mg {frequency or 'once daily'} totals {daily:g}mg per day, "
            f"above the maximum recommended {med.max_daily_dose_mg}mg per day.",
            medicine=medicine_name, prescribedDose=f"{daily:g}mg/day",
            maxDose=f"{med.max_daily_dose_mg}mg/day",
        ))
    return conflicts


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_all_checks(db: Session, patient_id: int, medicine_name: str,
                   dosage: str, frequency: str, current: List[dict]) -> List[dict]:
    """Run all four checks and return conflicts ordered most-severe first."""
    medicine_name = (medicine_name or "").strip()
    if not medicine_name:
        return []

    names = {medicine_name.lower()} | {
        (m.get("name") or "").strip().lower() for m in current if (m.get("name") or "").strip()
    }
    db_meds = {
        m.name.lower(): m
        for m in db.query(models.Medication).filter(
            models.Medication.name.ilike(medicine_name)
        ).all()
    }
    for row in db.query(models.Medication).all():
        if row.name.lower() in names:
            db_meds[row.name.lower()] = row

    med = db_meds.get(medicine_name.lower())

    conflicts = (
        check_allergy(db, patient_id, med, medicine_name)
        + check_interactions(db, med, medicine_name, current, db_meds)
        + check_duplicate(med, medicine_name, current, db_meds)
        + check_dosage(med, medicine_name, dosage, frequency)
    )
    conflicts.sort(key=lambda c: SEVERITY_RANK.get(c["severity"], 0), reverse=True)
    return conflicts


def suggest_alternatives(db: Session, med: Optional[models.Medication],
                         patient_id: int, current: List[dict], limit: int = 4) -> List[dict]:
    """
    Candidate replacements: same therapeutic category, and clean when run back
    through the full check for THIS patient and THIS prescription.

    Filtering by "not the class that caused this conflict" is not enough — a
    patient with two allergies would be offered a medicine matching the second
    one. Every candidate is therefore re-checked in full, so an alternative can
    never be something the system would immediately alert on.
    """
    if med is None or not med.category:
        return []

    rows = db.query(models.Medication).filter(
        models.Medication.category == med.category,
        models.Medication.id != med.id,
    ).all()

    out = []
    for row in rows:
        # Unclassified medicines can't be allergy- or interaction-checked, so
        # offering one would swap a known conflict for an unverifiable choice.
        if not row.drug_class:
            continue
        conflicts = run_all_checks(
            db, patient_id, row.name,
            row.default_dosage or "", "OD (Once daily)", current,
        )
        if conflicts:
            continue
        out.append({
            "name": row.name,
            "drugClass": row.drug_class,
            "defaultDosage": row.default_dosage,
        })
        if len(out) >= limit:
            break
    return out
