from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date
from typing import Optional, List
import re


_ID_PATTERNS = {
    'Aadhaar Card':    re.compile(r'^\d{12}$'),
    'PAN Card':        re.compile(r'^[A-Z]{5}\d{4}[A-Z]$'),
    'Passport':        re.compile(r'^[A-Z]\d{7}$'),
    'Voter ID':        re.compile(r'^[A-Z]{3}\d{7}$'),
    'Driving Licence': re.compile(r'^[A-Z]{2}\d{2}[A-Z0-9]{5,13}$'),
}


class PatientCreate(BaseModel):
    firstName: str = Field(..., min_length=1, max_length=50)
    lastName: str = Field(..., min_length=1, max_length=50)
    gender: str
    dob: date
    age: int = Field(..., ge=0, le=150)
    mobileNumber: str = Field(..., min_length=10, max_length=10)
    idProofType:   Optional[str] = Field(None, max_length=50)
    idProofNumber: Optional[str] = Field(None, max_length=30)
    # Optional legacy / extra fields
    insuranceCompany: Optional[str] = None
    medicalHistory: Optional[str] = None
    allergies: Optional[str] = None
    allowDuplicateMobile: bool = False

    @field_validator('idProofNumber')
    @classmethod
    def normalise_id_number(cls, v):
        return v.strip().upper() if v else v

    @model_validator(mode='after')
    def validate_id_format(self):
        if self.idProofType and self.idProofNumber:
            pattern = _ID_PATTERNS.get(self.idProofType)
            if pattern and not pattern.match(self.idProofNumber):
                raise ValueError(f"Invalid {self.idProofType} number format")
        return self

    @field_validator("firstName", "lastName")
    @classmethod
    def validate_name_part(cls, v):
        if not re.match(r"^[A-Za-z\s\-']+$", v.strip()):
            raise ValueError("Name must contain only letters, spaces, hyphens or apostrophes")
        return v.strip()

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v not in {"Male", "Female", "Other"}:
            raise ValueError("Gender must be one of: Male, Female, Other")
        return v

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v):
        today = date.today()
        if v > today:
            raise ValueError("Date of birth cannot be in the future")
        if (today - v).days > 150 * 365:
            raise ValueError("Date of birth is too far in the past")
        return v

    @field_validator("mobileNumber")
    @classmethod
    def validate_mobile(cls, v):
        digits = re.sub(r"[\s\-\+]", "", v)
        if not digits.isdigit() or len(digits) != 10:
            raise ValueError("Mobile number must be exactly 10 digits")
        return digits

    @model_validator(mode="after")
    def validate_age_matches_dob(self):
        if self.dob and self.age is not None:
            today = date.today()
            calculated_age = today.year - self.dob.year - (
                (today.month, today.day) < (self.dob.month, self.dob.day)
            )
            if abs(calculated_age - self.age) > 1:
                raise ValueError(
                    f"Age {self.age} does not match date of birth (expected {calculated_age})"
                )
        return self

    model_config = {"json_schema_extra": {"example": {
        "firstName": "John", "lastName": "Doe",
        "gender": "Male", "dob": "1990-05-15", "age": 35,
        "mobileNumber": "9876543210"
    }}}


class PatientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    gender: Optional[str] = None
    dob: Optional[date] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    insuranceCompany: Optional[str] = Field(None, max_length=150)
    addressLine1: Optional[str] = Field(None, min_length=1, max_length=200)
    addressLine2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    pinCode: Optional[str] = Field(None, min_length=4, max_length=10)
    status: Optional[str] = None
    doctor: Optional[str] = None
    medicalHistory: Optional[str] = None
    allergies: Optional[str] = None
    reasonForVisit: Optional[str] = None
    queueToken: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None and not re.match(r"^[A-Za-z\s]+$", v.strip()):
            raise ValueError("Name must contain only letters and spaces")
        return v.strip() if v else v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is not None and v not in {"Male", "Female", "Other"}:
            raise ValueError("Gender must be one of: Male, Female, Other")
        return v

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v):
        if v is not None:
            today = date.today()
            if v > today:
                raise ValueError("Date of birth cannot be in the future")
        return v

    @field_validator("pinCode")
    @classmethod
    def validate_pin_code(cls, v):
        if v is not None and not v.isdigit():
            raise ValueError("Pin code must contain only digits")
        return v

    @field_validator("city")
    @classmethod
    def validate_city(cls, v):
        if v is not None and not re.match(r"^[A-Za-z\s]+$", v.strip()):
            raise ValueError("City must contain only letters and spaces")
        return v.strip() if v else v


class PatientResponse(BaseModel):
    id: int
    patientId: str
    name: str
    gender: str
    dob: date
    age: int
    mobileNumber: Optional[str]
    insuranceCompany: Optional[str]
    addressLine1: Optional[str]
    addressLine2: Optional[str]
    city: Optional[str]
    pinCode: Optional[str]
    status: str
    doctor: Optional[str]
    medicalHistory: Optional[str]
    allergies: Optional[str]
    reasonForVisit: Optional[str]
    queueToken: Optional[str]
    checkinTime: Optional[str]
    idProofType:   Optional[str] = None
    idProofNumber: Optional[str] = None


    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_patient(cls, patient):
        return cls(
            id=patient.id,
            patientId=f"MED-{patient.id:04d}",
            name=patient.name,
            gender=patient.gender,
            dob=patient.dob,
            age=patient.age,
            mobileNumber=patient.mobile_number,
            insuranceCompany=patient.insurance_company,
            addressLine1=patient.address_line1,
            addressLine2=patient.address_line2,
            city=patient.city,
            pinCode=patient.pin_code,
            status=patient.status or "Registered",
            doctor=patient.doctor,
            medicalHistory=patient.medical_history,
            allergies=patient.allergies,
            reasonForVisit=patient.reason_for_visit,
            queueToken=patient.queue_token,
            checkinTime=patient.checkin_time,
            idProofType=patient.id_proof_type,
            idProofNumber=patient.id_proof_number,
        )


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    name: str
    email: str
    role: str
    specialization: Optional[str] = None
    mustChangePassword: bool = False


class ChangePasswordRequest(BaseModel):
    email: str
    currentPassword: str
    newPassword: str


class AuthUserResponse(BaseModel):
    """Returned by /auth/users — used to populate the login form (includes password for auto-fill)."""
    id: int
    name: str
    email: str
    password: str
    role: str
    specialization: Optional[str] = None


class ReceptionistResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = {"from_attributes": True}


class AdminStats(BaseModel):
    totalUsers: int
    activeDoctors: int
    totalPatients: int
    avgWaitingTime: int
    consultationsTotal: int


class PatientFlowDay(BaseModel):
    day: str
    count: int


class ConsultationStat(BaseModel):
    label: str
    count: int
    percentage: float


class DoctorWorkloadItem(BaseModel):
    name: str
    count: int
    maxCount: int


class AuditLogItem(BaseModel):
    time: str
    user: str
    action: str
    module: str
    details: str


class DoctorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    specialization: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=150)


class DoctorResponse(BaseModel):
    id: int
    name: str
    specialization: str
    phone: Optional[str] = None
    email: Optional[str] = None
    role: str = "Doctor"
    is_active: bool = True
    available_from: Optional[str] = None
    available_to: Optional[str] = None

    model_config = {"from_attributes": True}


class AdminUserItem(BaseModel):
    id: int
    name: str
    email: str
    role: str
    isActive: bool
    source: str
    specialization: Optional[str] = None
    phone: Optional[str] = None


class AdminUserCreate(BaseModel):
    firstName: str
    lastName: str
    email: str
    phone: Optional[str] = None
    role: str
    specialization: Optional[str] = None
    sendWelcomeEmail: bool = True


class AdminUserUpdate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    specialization: Optional[str] = None


class TempPasswordResponse(BaseModel):
    tempPassword: str
    userId: int
    source: str


class DoctorStats(BaseModel):
    total: int
    active: int
    inactive: int
    specializations: int


class AdminDoctorCreate(BaseModel):
    name: str
    specialization: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "Doctor"
    available_from: Optional[str] = None
    available_to: Optional[str] = None


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    specialization: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    available_from: Optional[str] = None
    available_to: Optional[str] = None


class WaitingTimeDay(BaseModel):
    day: str
    mins: float


class DepartmentStat(BaseModel):
    department: str
    count: int
    percentage: float


class PeakHour(BaseModel):
    hour: str
    mins: float


class WeeklySummary(BaseModel):
    totalPatients: int
    totalConsultations: int
    avgWaitingTime: int
    cancelledConsultations: int
    patientsChange: float
    consultationsChange: float
    waitingTimeChange: int
    cancelledChange: float


class AuditLogFull(BaseModel):
    id: int
    time: str
    user: str
    userEmail: str
    action: str
    module: str
    details: str
    ipAddress: str
    status: str
    actionType: str


class AuditLogsResponse(BaseModel):
    logs: List[AuditLogFull]
    total: int


class InsuranceCompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    contactNumber: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=150)


class InsuranceCompanyResponse(BaseModel):
    id: int
    name: str
    contactNumber: Optional[str]
    email: Optional[str]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_company(cls, company):
        return cls(
            id=company.id,
            name=company.name,
            contactNumber=company.contact_number,
            email=company.email,
        )


class ConsultationCreate(BaseModel):
    patientId: int
    chiefComplaint: str = Field(..., min_length=1)
    doctorName: Optional[str] = None


class ConsultationResponse(BaseModel):
    id: int
    patientId: int
    chiefComplaint: str
    consultationDate: date
    doctorName: Optional[str]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_consultation(cls, c):
        return cls(
            id=c.id,
            patientId=c.patient_id,
            chiefComplaint=c.chief_complaint,
            consultationDate=c.consultation_date,
            doctorName=c.doctor_name,
        )


class MedicationResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    defaultDosage: Optional[str]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_medication(cls, m):
        return cls(id=m.id, name=m.name, category=m.category, defaultDosage=m.default_dosage)


class MedicationItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: Optional[str] = None


class PrescriptionCreate(BaseModel):
    patientId: int
    medications: List[MedicationItem]
    doctorName: Optional[str] = None
    notes: Optional[str] = None


class PrescriptionResponse(BaseModel):
    id: int
    patientId: int
    medications: List[MedicationItem]
    doctorName: Optional[str]
    prescriptionDate: date
    notes: Optional[str]

    @classmethod
    def from_orm_prescription(cls, p):
        import json
        meds = json.loads(p.medications) if isinstance(p.medications, str) else p.medications
        return cls(
            id=p.id,
            patientId=p.patient_id,
            medications=[MedicationItem(**m) for m in meds],
            doctorName=p.doctor_name,
            prescriptionDate=p.prescription_date,
            notes=p.notes,
        )
