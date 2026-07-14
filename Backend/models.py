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
    checkin_time = Column(String(10), nullable=True)
    id_proof_type = Column(String(50), nullable=True)
    id_proof_number = Column(String(30), nullable=True)


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


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False)
    medications = Column(Text, nullable=False)
    doctor_name = Column(String(200), nullable=True)
    prescription_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)
    default_dosage = Column(String(50), nullable=True)


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
