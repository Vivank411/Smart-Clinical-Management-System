from sqlalchemy import Column, Integer, String, Date, Text, Boolean
from database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(20), nullable=False)
    dob = Column(Date, nullable=False)
    age = Column(Integer, nullable=False)
    mobile_number = Column(String(15), nullable=True)
    email = Column(String(150), nullable=True)
    insurance_company = Column(String(150), nullable=True)
    address_line1 = Column(String(200), nullable=True)
    address_line2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    pin_code = Column(String(10), nullable=True)
    status = Column(String(30), nullable=False, default="Registered")
    doctor = Column(String(200), nullable=True)
    medical_history = Column(Text, nullable=True)
    allergies = Column(String(500), nullable=True)
    reason_for_visit = Column(Text, nullable=True)
    queue_token = Column(String(10), nullable=True)
    # Date the current queue token was issued — the sequence restarts daily.
    token_issued_on = Column(String(12), nullable=True)
    checkin_time = Column(String(10), nullable=True)
    # Pending until the registration fee is settled. Rows predating the payment
    # feature stay NULL and are treated as already settled.
    payment_status = Column(String(20), nullable=True, default="Pending")
    id_proof_type = Column(String(50), nullable=True)
    id_proof_number = Column(String(30), nullable=True)

    # Full ISO-8601 timestamps (with offset) backing the analytics screens.
    # `checkin_time` is kept as the display-only clock label it always was.
    registered_at = Column(String(40), nullable=True)
    checkin_at = Column(String(40), nullable=True)


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    specialization = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(150), nullable=True)
    password = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="Doctor")
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    available_from = Column(String(10), nullable=True, default="09:00 AM")
    available_to   = Column(String(10), nullable=True, default="05:00 PM")


class Receptionist(Base):
    __tablename__ = "receptionists"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False)
    password = Column(String(255), nullable=False, default="reception123")
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)


class InsuranceCompany(Base):
    __tablename__ = "insurance_companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    contact_number = Column(String(20), nullable=True)
    email = Column(String(150), nullable=True)


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False)
    chief_complaint = Column(Text, nullable=False)
    consultation_date = Column(Date, nullable=False)
    doctor_name = Column(String(200), nullable=True)
    created_at = Column(String(40), nullable=True)


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False)
    medications = Column(Text, nullable=False)
    doctor_name = Column(String(200), nullable=True)
    prescription_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(String(40), nullable=True)
    # Delivery trail — when the prescription was pushed to the patient.
    sent_email_at = Column(String(40), nullable=True)
    sent_whatsapp_at = Column(String(40), nullable=True)


class Payment(Base):
    """
    One row per payment taken at the counter. Kept even when abandoned — the
    day's takings have to reconcile, and an abandoned attempt is evidence that
    nothing was collected.

    All three methods are confirmed by the person on the desk: the patient
    scans the clinic's QR, taps a card on the clinic's own machine, or hands
    over cash. No card or bank credentials pass through this system.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    txnid = Column(String(60), nullable=False, unique=True, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    amount = Column(String(20), nullable=False)
    currency = Column(String(10), nullable=False, default="INR")
    purpose = Column(String(150), nullable=True)
    status = Column(String(20), nullable=False, default="Pending")   # Pending|Success|Cancelled
    method = Column(String(20), nullable=False, default="cash")      # qr | card | cash

    # Reconciliation trail. Deliberately narrow: a UPI UTR or a card-machine
    # approval code identifies the transaction on the bank statement without
    # this system ever holding anything that could be used to charge a card.
    reference = Column(String(60), nullable=True)
    card_last4 = Column(String(4), nullable=True)
    notes = Column(String(300), nullable=True)

    # Who took the money — every payment is somebody's responsibility.
    collected_by = Column(String(120), nullable=True)

    queue_token = Column(String(10), nullable=True)
    created_at = Column(String(40), nullable=True)
    completed_at = Column(String(40), nullable=True)


class AppSetting(Base):
    """
    Small key/value store for settings that must be shared across machines —
    the payment QR belongs to the clinic, not to whichever browser uploaded it.
    """
    __tablename__ = "app_settings"

    key = Column(String(60), primary_key=True, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(String(40), nullable=True)
    updated_by = Column(String(120), nullable=True)


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)
    default_dosage = Column(String(50), nullable=True)

    # ── Clinical safety fields ────────────────────────────────────────────
    # drug_class is the join key for both allergy and interaction checking:
    # allergy_mapping maps an allergen to a drug_class, and drug_interactions
    # pairs two drug_class values.
    drug_class = Column(String(120), nullable=True, index=True)
    max_single_dose_mg = Column(Integer, nullable=True)
    max_daily_dose_mg = Column(Integer, nullable=True)


class PatientAllergy(Base):
    """
    Normalised replacement for the free-text `patients.allergies` column.
    That column is kept in sync so existing screens keep working, but every
    safety check reads from here — matching free text is not reliable enough
    to base a missed-allergy alert on.
    """
    __tablename__ = "patient_allergies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False, index=True)
    allergen = Column(String(120), nullable=False, index=True)   # normalised, uppercase
    display_name = Column(String(120), nullable=False)           # as entered, for display
    severity = Column(String(20), nullable=False, default="High")
    notes = Column(String(300), nullable=True)


class AllergyMapping(Base):
    """Maps a normalised allergen to the drug class it contraindicates."""
    __tablename__ = "allergy_mapping"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    allergen = Column(String(120), nullable=False, index=True)
    drug_class = Column(String(120), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="High")


class DrugInteraction(Base):
    """Class-to-class interaction pairs. Stored once; matched in both directions."""
    __tablename__ = "drug_interactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    drug_class_a = Column(String(120), nullable=False, index=True)
    drug_class_b = Column(String(120), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="Moderate")
    description = Column(String(400), nullable=False)


class SafetyCheckLog(Base):
    """
    Audit trail. Every check is recorded — including the AI-generated text and
    the doctor's decision — because an AI-influenced prescribing decision has to
    be reconstructable after the fact.
    """
    __tablename__ = "safety_check_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False, index=True)
    doctor_name = Column(String(200), nullable=True)
    medicine = Column(String(200), nullable=False)
    dosage = Column(String(50), nullable=True)
    frequency = Column(String(50), nullable=True)
    conflicts_json = Column(Text, nullable=True)
    ai_explanation = Column(Text, nullable=True)
    ai_suggestion = Column(Text, nullable=True)
    ai_model = Column(String(60), nullable=True)
    checked_at = Column(String(30), nullable=False)


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False)
    password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(30), nullable=False)
    user_name = Column(String(100), nullable=True)
    user_email = Column(String(150), nullable=True)
    action = Column(String(100), nullable=False)
    module = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="Success")
    action_type = Column(String(20), nullable=False)
