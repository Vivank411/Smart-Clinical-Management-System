"""
Reference data for the Clinical Safety Engine.

This is a STARTER dataset covering common Indian outpatient prescribing, not a
complete drug-interaction database. Before clinical use it should be replaced
with, or validated against, a maintained pharmacological source. Every entry is
additive and idempotent — re-running the seed never overwrites edits made
through the admin screens.
"""

from sqlalchemy.orm import Session

import clinical_safety
import models

# medicine name -> (drug_class, max_single_dose_mg, max_daily_dose_mg)
MEDICINE_CLASSES = {
    "amoxicillin":      ("Penicillin Antibiotics", 1000, 3000),
    "amoxycillin":      ("Penicillin Antibiotics", 1000, 3000),
    "ampicillin":       ("Penicillin Antibiotics", 1000, 4000),
    "penicillin":       ("Penicillin Antibiotics", 1000, 4000),
    "cloxacillin":      ("Penicillin Antibiotics", 500, 2000),
    "azithromycin":     ("Macrolide Antibiotics", 500, 500),
    "clarithromycin":   ("Macrolide Antibiotics", 500, 1000),
    "erythromycin":     ("Macrolide Antibiotics", 500, 2000),
    "doxycycline":      ("Tetracycline Antibiotics", 200, 200),
    "cephalexin":       ("Cephalosporin Antibiotics", 500, 2000),
    "cefixime":         ("Cephalosporin Antibiotics", 400, 400),
    "ceftriaxone":      ("Cephalosporin Antibiotics", 2000, 4000),
    "ciprofloxacin":    ("Fluoroquinolone Antibiotics", 750, 1500),
    "levofloxacin":     ("Fluoroquinolone Antibiotics", 750, 750),
    "paracetamol":      ("Analgesic - Paracetamol", 1000, 4000),
    "acetaminophen":    ("Analgesic - Paracetamol", 1000, 4000),
    "ibuprofen":        ("NSAID", 800, 2400),
    "diclofenac":       ("NSAID", 100, 150),
    "naproxen":         ("NSAID", 500, 1000),
    "aceclofenac":      ("NSAID", 100, 200),
    "aspirin":          ("NSAID", 650, 4000),
    "warfarin":         ("Anticoagulant", 10, 10),
    "heparin":          ("Anticoagulant", None, None),
    "clopidogrel":      ("Antiplatelet", 75, 75),
    "metformin":        ("Biguanide Antidiabetic", 1000, 2550),
    "glimepiride":      ("Sulfonylurea Antidiabetic", 4, 8),
    "atorvastatin":     ("Statin", 80, 80),
    "simvastatin":      ("Statin", 40, 40),
    "rosuvastatin":     ("Statin", 40, 40),
    "amlodipine":       ("Calcium Channel Blocker", 10, 10),
    "atenolol":         ("Beta Blocker", 100, 100),
    "metoprolol":       ("Beta Blocker", 200, 400),
    "propranolol":      ("Beta Blocker", 80, 320),
    "enalapril":        ("ACE Inhibitor", 20, 40),
    "ramipril":         ("ACE Inhibitor", 10, 10),
    "lisinopril":       ("ACE Inhibitor", 40, 40),
    "losartan":         ("ARB", 100, 100),
    "telmisartan":      ("ARB", 80, 80),
    "omeprazole":       ("Proton Pump Inhibitor", 40, 40),
    "pantoprazole":     ("Proton Pump Inhibitor", 40, 80),
    "rabeprazole":      ("Proton Pump Inhibitor", 20, 40),
    "ranitidine":       ("H2 Blocker", 300, 600),
    "cetirizine":       ("Antihistamine", 10, 10),
    "levocetirizine":   ("Antihistamine", 5, 5),
    "loratadine":       ("Antihistamine", 10, 10),
    "montelukast":      ("Leukotriene Antagonist", 10, 10),
    "prednisolone":     ("Corticosteroid", 60, 60),
    "dexamethasone":    ("Corticosteroid", 8, 16),
    "salbutamol":       ("Bronchodilator", None, None),
    "sertraline":       ("SSRI Antidepressant", 200, 200),
    "fluoxetine":       ("SSRI Antidepressant", 80, 80),
    "escitalopram":     ("SSRI Antidepressant", 20, 20),
    "tramadol":         ("Opioid Analgesic", 100, 400),
    "codeine":          ("Opioid Analgesic", 60, 240),
    "metronidazole":    ("Nitroimidazole Antibiotic", 800, 2400),
    "ondansetron":      ("Antiemetic", 8, 24),
}

# (allergen, contraindicated drug class, severity)
ALLERGY_MAPPINGS = [
    ("PENICILLIN",      "Penicillin Antibiotics",     "High"),
    ("PENICILLIN",      "Cephalosporin Antibiotics",  "Moderate"),  # cross-reactivity
    ("AMOXICILLIN",     "Penicillin Antibiotics",     "High"),
    ("CEPHALOSPORIN",   "Cephalosporin Antibiotics",  "High"),
    ("SULFA",           "Sulfonylurea Antidiabetic",  "Moderate"),
    ("SULPHA",          "Sulfonylurea Antidiabetic",  "Moderate"),
    ("ASPIRIN",         "NSAID",                      "High"),
    ("NSAID",           "NSAID",                      "High"),
    ("IBUPROFEN",       "NSAID",                      "High"),
    ("DICLOFENAC",      "NSAID",                      "High"),
    ("PARACETAMOL",     "Analgesic - Paracetamol",    "High"),
    ("MACROLIDE",       "Macrolide Antibiotics",      "High"),
    ("ERYTHROMYCIN",    "Macrolide Antibiotics",      "High"),
    ("AZITHROMYCIN",    "Macrolide Antibiotics",      "High"),
    ("TETRACYCLINE",    "Tetracycline Antibiotics",   "High"),
    ("DOXYCYCLINE",     "Tetracycline Antibiotics",   "High"),
    ("CIPROFLOXACIN",   "Fluoroquinolone Antibiotics", "High"),
    ("QUINOLONE",       "Fluoroquinolone Antibiotics", "High"),
    ("CODEINE",         "Opioid Analgesic",           "High"),
    ("MORPHINE",        "Opioid Analgesic",           "High"),
    ("STATIN",          "Statin",                     "High"),
    ("METRONIDAZOLE",   "Nitroimidazole Antibiotic",  "High"),
]

# (class A, class B, severity, description)
DRUG_INTERACTIONS = [
    ("Anticoagulant", "NSAID", "High",
     "Combining an anticoagulant with an NSAID substantially increases the risk of "
     "gastrointestinal and other bleeding."),
    ("Anticoagulant", "Antiplatelet", "High",
     "Concurrent anticoagulant and antiplatelet therapy markedly increases bleeding risk."),
    ("Anticoagulant", "Macrolide Antibiotics", "Moderate",
     "Macrolides can inhibit warfarin metabolism, raising INR and bleeding risk."),
    ("Statin", "Macrolide Antibiotics", "High",
     "Macrolides inhibit statin metabolism, increasing the risk of myopathy and "
     "rhabdomyolysis."),
    ("ACE Inhibitor", "ARB", "High",
     "Dual renin-angiotensin blockade increases the risk of hyperkalaemia, hypotension "
     "and acute kidney injury without added benefit."),
    ("ACE Inhibitor", "NSAID", "Moderate",
     "NSAIDs reduce the antihypertensive effect of ACE inhibitors and increase the risk "
     "of renal impairment."),
    ("ARB", "NSAID", "Moderate",
     "NSAIDs reduce the antihypertensive effect of ARBs and increase the risk of renal "
     "impairment."),
    ("Beta Blocker", "Calcium Channel Blocker", "Moderate",
     "Combined use can cause excessive bradycardia, hypotension and heart block."),
    ("SSRI Antidepressant", "NSAID", "Moderate",
     "SSRIs combined with NSAIDs increase the risk of upper gastrointestinal bleeding."),
    ("SSRI Antidepressant", "Opioid Analgesic", "Moderate",
     "Combined use raises the risk of serotonin syndrome, particularly with tramadol."),
    ("SSRI Antidepressant", "Antiplatelet", "Moderate",
     "SSRIs impair platelet function and add to antiplatelet bleeding risk."),
    ("Corticosteroid", "NSAID", "Moderate",
     "Corticosteroids with NSAIDs significantly increase the risk of peptic ulceration "
     "and gastrointestinal bleeding."),
    ("Biguanide Antidiabetic", "Corticosteroid", "Moderate",
     "Corticosteroids raise blood glucose and can oppose the effect of metformin."),
    ("Sulfonylurea Antidiabetic", "Beta Blocker", "Moderate",
     "Beta blockers can mask the adrenergic warning signs of hypoglycaemia."),
    ("Proton Pump Inhibitor", "Antiplatelet", "Moderate",
     "Some proton pump inhibitors reduce the antiplatelet effect of clopidogrel."),
    ("Nitroimidazole Antibiotic", "Anticoagulant", "High",
     "Metronidazole potentiates warfarin, raising INR and bleeding risk."),
    ("Fluoroquinolone Antibiotics", "Corticosteroid", "Moderate",
     "Combined use increases the risk of tendinitis and tendon rupture."),
]


def seed_clinical_safety(db: Session) -> None:
    """Idempotent. Safe to run on every startup."""

    # 1. Classify medicines already in the master, without overwriting curated values.
    for med in db.query(models.Medication).all():
        if med.drug_class:
            continue
        key = (med.name or "").strip().lower()
        entry = MEDICINE_CLASSES.get(key)
        if entry is None:
            entry = next(
                (v for k, v in MEDICINE_CLASSES.items() if k in key), None
            )
        if entry:
            med.drug_class, med.max_single_dose_mg, med.max_daily_dose_mg = entry

    # 2. Allergen -> drug class mappings.
    existing_maps = {
        (m.allergen, m.drug_class) for m in db.query(models.AllergyMapping).all()
    }
    for allergen, drug_class, severity in ALLERGY_MAPPINGS:
        if (allergen, drug_class) not in existing_maps:
            db.add(models.AllergyMapping(
                allergen=allergen, drug_class=drug_class, severity=severity))

    # 3. Interaction pairs.
    existing_pairs = {
        frozenset((i.drug_class_a, i.drug_class_b))
        for i in db.query(models.DrugInteraction).all()
    }
    for a, b, severity, description in DRUG_INTERACTIONS:
        if frozenset((a, b)) not in existing_pairs:
            db.add(models.DrugInteraction(
                drug_class_a=a, drug_class_b=b,
                severity=severity, description=description))

    db.commit()
    migrate_patient_allergies(db)


def sync_patient_allergies(db: Session, patient: models.Patient) -> None:
    """
    Rebuild a patient's structured allergy rows from the free-text
    `patients.allergies` column, which is what the registration and edit screens
    write. Must be called on EVERY write to that column.

    Comparison is per allergen, not per patient: an allergen appended to the
    free text later must still produce a row. Getting this wrong means the
    allergy check silently has nothing to match on — a missed alert, which is
    the most dangerous way this feature can fail.

    Does not commit; the caller commits with the rest of its transaction.
    """
    desired = {}
    for raw in (patient.allergies or "").split(","):
        display = raw.strip()
        if not display:
            continue
        allergen = resolve_allergen(clinical_safety.normalise_allergen(display))
        if allergen:
            desired[allergen] = display

    existing = db.query(models.PatientAllergy).filter(
        models.PatientAllergy.patient_id == patient.id
    ).all()
    existing_by_allergen = {row.allergen: row for row in existing}

    for allergen, display in desired.items():
        row = existing_by_allergen.get(allergen)
        if row is None:
            db.add(models.PatientAllergy(
                patient_id=patient.id, allergen=allergen,
                display_name=display, severity="High",
            ))
        elif row.display_name != display:
            row.display_name = display

    # Free text is the source of truth, so an allergen removed there is removed here.
    for allergen, row in existing_by_allergen.items():
        if allergen not in desired:
            db.delete(row)


def migrate_patient_allergies(db: Session) -> None:
    """Backfill every patient at startup. Idempotent — safe on each boot."""
    for patient in db.query(models.Patient).all():
        sync_patient_allergies(db, patient)
    db.commit()


KNOWN_ALLERGENS = sorted({a for a, _, _ in ALLERGY_MAPPINGS})


def resolve_allergen(normalised: str) -> str:
    """
    Snap a legacy free-text allergen onto a known allergen when it is an obvious
    misspelling ('PENICILIN' -> 'PENICILLIN'). Without this, migrated free text
    silently fails to match any mapping and the allergy check never fires — a
    missed alert is the worst failure mode this feature has.
    """
    import difflib

    if not normalised or normalised in KNOWN_ALLERGENS:
        return normalised
    for known in KNOWN_ALLERGENS:
        if known in normalised or normalised in known:
            return known
    match = difflib.get_close_matches(normalised, KNOWN_ALLERGENS, n=1, cutoff=0.85)
    return match[0] if match else normalised
