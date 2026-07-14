from contextlib import asynccontextmanager
from datetime import date, datetime
from fastapi import FastAPI, Depends, HTTPException, Request, status, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional

import models
import schemas
import email_service
from database import engine, SessionLocal, get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _is_hashed(pw: str) -> bool:
    return bool(pw) and (pw.startswith("$2b$") or pw.startswith("$2a$"))

def _hash(pw: str) -> str:
    return pwd_context.hash(pw)

def _verify(plain: str, stored: str) -> bool:
    if not stored:
        return False
    if _is_hashed(stored):
        return pwd_context.verify(plain, stored)
    return plain == stored  # fallback for any remaining plaintext passwords

def _gen_temp_password(length: int = 10) -> str:
    import secrets, string
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(length))


def log_audit(
    db: Session,
    request: Request,
    action: str,
    module: str,
    details: str,
    action_type: str,
    log_status: str = "Success",
    user_name: Optional[str] = None,
    user_email: Optional[str] = None,
) -> None:
    name  = user_name  or request.headers.get("x-user-name",  "System")
    email = user_email or request.headers.get("x-user-email", "")
    ip    = request.client.host if request.client else "127.0.0.1"
    try:
        db.add(models.AuditLog(
            timestamp   = datetime.now().strftime("%b %d, %Y %I:%M %p"),
            user_name   = (name  or "System")[:100],
            user_email  = (email or "")[:150],
            action      = action,
            module      = module,
            details     = details,
            ip_address  = ip,
            status      = log_status,
            action_type = action_type,
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[AuditLog] Failed to write: {exc}")


models.Base.metadata.create_all(bind=engine)

SEED_DOCTORS = [
    {"name": "Dr. Rajesh Sharma",    "specialization": "General Medicine", "email": "dr.rajesh.sharma@mediclinic.com",    "password": "rajesh@123",   "role": "Doctor"},
    {"name": "Dr. Amit Verma",       "specialization": "General Medicine", "email": "dr.amit.verma@mediclinic.com",       "password": "amit@123",     "role": "Junior Doctor"},
    {"name": "Dr. Priya Gupta",      "specialization": "Dermatology",      "email": "dr.priya.gupta@mediclinic.com",      "password": "priya@123",    "role": "Doctor"},
    {"name": "Dr. Neha Singh",       "specialization": "Dermatology",      "email": "dr.neha.singh@mediclinic.com",       "password": "neha@123",     "role": "Doctor"},
    {"name": "Dr. Arjun Patel",      "specialization": "Cardiology",       "email": "dr.arjun.patel@mediclinic.com",      "password": "arjun@123",    "role": "Doctor"},
    {"name": "Dr. Vivek Mehta",      "specialization": "Cardiology",       "email": "dr.vivek.mehta@mediclinic.com",      "password": "vivek@123",    "role": "Doctor"},
    {"name": "Dr. Sandeep Kumar",    "specialization": "Orthopedic",       "email": "dr.sandeep.kumar@mediclinic.com",    "password": "sandeep@123",  "role": "Doctor"},
    {"name": "Dr. Pooja Jain",       "specialization": "Orthopedic",       "email": "dr.pooja.jain@mediclinic.com",       "password": "pooja@123",    "role": "Doctor"},
    {"name": "Dr. Rakesh Yadav",     "specialization": "ENT",              "email": "dr.rakesh.yadav@mediclinic.com",     "password": "rakesh@123",   "role": "Doctor"},
    {"name": "Dr. Anjali Agarwal",   "specialization": "ENT",              "email": "dr.anjali.agarwal@mediclinic.com",   "password": "anjali@123",   "role": "Doctor"},
    {"name": "Dr. Nitin Bansal",     "specialization": "Neurology",        "email": "dr.nitin.bansal@mediclinic.com",     "password": "nitin@123",    "role": "Doctor"},
    {"name": "Dr. Rohit Saxena",     "specialization": "Neurology",        "email": "dr.rohit.saxena@mediclinic.com",     "password": "rohit@123",    "role": "Doctor"},
    {"name": "Dr. Sneha Kapoor",     "specialization": "Pediatrics",       "email": "dr.sneha.kapoor@mediclinic.com",     "password": "sneha@123",    "role": "Doctor"},
    {"name": "Dr. Deepak Mishra",    "specialization": "Pediatrics",       "email": "dr.deepak.mishra@mediclinic.com",    "password": "deepak@123",   "role": "Doctor"},
    {"name": "Dr. Kunal Srivastava", "specialization": "Ophthalmology",    "email": "dr.kunal.srivastava@mediclinic.com", "password": "kunal@123",    "role": "Doctor"},
    {"name": "Dr. Shweta Tiwari",    "specialization": "Gynecology",       "email": "dr.shweta.tiwari@mediclinic.com",    "password": "shweta@123",   "role": "Doctor"},
]

SEED_RECEPTIONISTS = [
    {"name": "Sarah Williams", "email": "sarah.williams@mediclinic.com", "password": "sarah@123"},
]

SEED_ADMINS = [
    {"name": "Administrator", "email": "admin@mediclinic.com", "password": "admin@123"},
]

SEED_MEDICATIONS = [
    {"name": "Amoxicillin",      "category": "Antibiotic",      "default_dosage": "500mg"},
    {"name": "Ibuprofen",        "category": "Pain Relief",      "default_dosage": "400mg"},
    {"name": "Metformin",        "category": "Diabetes",         "default_dosage": "500mg"},
    {"name": "Azithromycin",     "category": "Antibiotic",      "default_dosage": "250mg"},
    {"name": "Sulfa Drugs",      "category": "Antibiotic",      "default_dosage": "800mg"},
    {"name": "Lisinopril",       "category": "Blood Pressure",  "default_dosage": "10mg"},
    {"name": "Paracetamol",      "category": "Pain Relief",      "default_dosage": "500mg"},
    {"name": "Aspirin",          "category": "Blood Thinner",   "default_dosage": "75mg"},
    {"name": "Omeprazole",       "category": "Gastric",          "default_dosage": "20mg"},
    {"name": "Atorvastatin",     "category": "Cholesterol",     "default_dosage": "20mg"},
    {"name": "Amlodipine",       "category": "Blood Pressure",  "default_dosage": "5mg"},
    {"name": "Metoprolol",       "category": "Heart",            "default_dosage": "50mg"},
    {"name": "Cetirizine",       "category": "Antihistamine",   "default_dosage": "10mg"},
    {"name": "Ciprofloxacin",    "category": "Antibiotic",      "default_dosage": "500mg"},
    {"name": "Doxycycline",      "category": "Antibiotic",      "default_dosage": "100mg"},
    {"name": "Prednisolone",     "category": "Steroid",          "default_dosage": "10mg"},
    {"name": "Salbutamol",       "category": "Bronchodilator",  "default_dosage": "100mcg"},
    {"name": "Vitamin D3",       "category": "Supplement",      "default_dosage": "1000IU"},
    {"name": "Iron Tablets",     "category": "Supplement",      "default_dosage": "325mg"},
    {"name": "Calcium Carbonate","category": "Supplement",      "default_dosage": "500mg"},
    {"name": "Penicillin V",     "category": "Antibiotic",      "default_dosage": "500mg"},
    {"name": "Clopidogrel",      "category": "Blood Thinner",   "default_dosage": "75mg"},
    {"name": "Sertraline",       "category": "Antidepressant",  "default_dosage": "50mg"},
    {"name": "Losartan",         "category": "Blood Pressure",  "default_dosage": "50mg"},
    {"name": "Pantoprazole",     "category": "Gastric",          "default_dosage": "40mg"},
    {"name": "Ranitidine",       "category": "Gastric",          "default_dosage": "150mg"},
    {"name": "Domperidone",      "category": "Gastric",          "default_dosage": "10mg"},
    {"name": "Ondansetron",      "category": "Anti-nausea",     "default_dosage": "4mg"},
    {"name": "Diclofenac",       "category": "Pain Relief",      "default_dosage": "50mg"},
    {"name": "Naproxen",         "category": "Pain Relief",      "default_dosage": "500mg"},
]

SEED_INSURANCE = [
    "LIC", "Tata AIG", "Star Health", "HDFC Ergo", "ICICI Lombard",
    "Bajaj Allianz", "Care Health", "Niva Bupa", "Reliance General", "New India Assurance",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema migrations — add columns to existing tables without dropping them
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS id_proof_type VARCHAR(50)"))
        conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS id_proof_number VARCHAR(30)"))
        conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS password VARCHAR(255)"))
        conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'Doctor'"))
        conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS available_from VARCHAR(10) DEFAULT '09:00 AM'"))
        conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS available_to   VARCHAR(10) DEFAULT '05:00 PM'"))
        conn.execute(text("ALTER TABLE receptionists ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE receptionists ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE admins ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE admins ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.commit()

    # Create any new tables (e.g. receptionists) that don't exist yet
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(models.Doctor).count() == 0:
            for d in SEED_DOCTORS:
                db.add(models.Doctor(**{**d, "password": _hash(d["password"])}))
        else:
            # Sync email and role; re-hash plaintext seed passwords if not already hashed
            for d in SEED_DOCTORS:
                doc = db.query(models.Doctor).filter(models.Doctor.name == d["name"]).first()
                if doc:
                    doc.email = d["email"]
                    doc.role  = d["role"]
                    if not _is_hashed(doc.password or ""):
                        doc.password = _hash(d["password"])

        if db.query(models.InsuranceCompany).count() == 0:
            for name in SEED_INSURANCE:
                db.add(models.InsuranceCompany(name=name))

        if db.query(models.Medication).count() == 0:
            for m in SEED_MEDICATIONS:
                db.add(models.Medication(**m))

        if db.query(models.Receptionist).count() == 0:
            for r in SEED_RECEPTIONISTS:
                db.add(models.Receptionist(**{**r, "password": _hash(r["password"])}))
        else:
            for r in SEED_RECEPTIONISTS:
                rec = db.query(models.Receptionist).filter(models.Receptionist.email == r["email"]).first()
                if rec and not _is_hashed(rec.password or ""):
                    rec.password = _hash(r["password"])

        if db.query(models.Admin).count() == 0:
            for a in SEED_ADMINS:
                db.add(models.Admin(**{**a, "password": _hash(a["password"])}))
        else:
            for a in SEED_ADMINS:
                adm = db.query(models.Admin).filter(models.Admin.email == a["email"]).first()
                if adm and not _is_hashed(adm.password or ""):
                    adm.password = _hash(a["password"])

        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="MediClinic Patient API",
    description="API for managing patient records",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        message = error["msg"].replace("Value error, ", "")
        errors.append({"field": field, "message": message})
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "errors": errors},
    )


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post(
    "/auth/login",
    response_model=schemas.LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate a user and return their profile",
    tags=["Auth"],
)
def login(credentials: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = credentials.email.strip().lower()
    password = credentials.password

    # Search doctors table first (covers "Doctor" and "Junior Doctor")
    doctor = db.query(models.Doctor).filter(
        models.Doctor.email.ilike(email)
    ).first()
    if doctor:
        if not doctor.is_active:
            log_audit(db, request, "Failed Login", "Authentication",
                      f"Login blocked — account deactivated: {email}", "error", "Failed",
                      user_name=doctor.name, user_email=email)
            raise HTTPException(status_code=403, detail="Your account has been deactivated. Please contact the administrator.")
        if not _verify(password, doctor.password or ""):
            log_audit(db, request, "Failed Login", "Authentication",
                      f"Incorrect password for {email}", "error", "Failed",
                      user_name="Unknown", user_email=email)
            raise HTTPException(status_code=401, detail="Incorrect password")
        log_audit(db, request, "Login", "Authentication",
                  f"{doctor.name} logged in as {doctor.role}", "login",
                  user_name=doctor.name, user_email=doctor.email or email)
        return schemas.LoginResponse(
            name=doctor.name,
            email=doctor.email,
            role=doctor.role,
            specialization=doctor.specialization,
            mustChangePassword=doctor.must_change_password,
        )

    # Search receptionists table
    receptionist = db.query(models.Receptionist).filter(
        models.Receptionist.email.ilike(email)
    ).first()
    if receptionist:
        if not receptionist.is_active:
            log_audit(db, request, "Failed Login", "Authentication",
                      f"Login blocked — account deactivated: {email}", "error", "Failed",
                      user_name=receptionist.name, user_email=email)
            raise HTTPException(status_code=403, detail="Your account has been deactivated. Please contact the administrator.")
        if not _verify(password, receptionist.password or ""):
            log_audit(db, request, "Failed Login", "Authentication",
                      f"Incorrect password for {email}", "error", "Failed",
                      user_name="Unknown", user_email=email)
            raise HTTPException(status_code=401, detail="Incorrect password")
        log_audit(db, request, "Login", "Authentication",
                  f"{receptionist.name} logged in as Receptionist", "login",
                  user_name=receptionist.name, user_email=receptionist.email)
        return schemas.LoginResponse(
            name=receptionist.name,
            email=receptionist.email,
            role="Receptionist",
            mustChangePassword=receptionist.must_change_password,
        )

    # Search admins table
    admin = db.query(models.Admin).filter(
        models.Admin.email.ilike(email)
    ).first()
    if admin:
        if not admin.is_active:
            log_audit(db, request, "Failed Login", "Authentication",
                      f"Login blocked — account deactivated: {email}", "error", "Failed",
                      user_name=admin.name, user_email=email)
            raise HTTPException(status_code=403, detail="Your account has been deactivated. Please contact the administrator.")
        if not _verify(password, admin.password or ""):
            log_audit(db, request, "Failed Login", "Authentication",
                      f"Incorrect password for {email}", "error", "Failed",
                      user_name="Unknown", user_email=email)
            raise HTTPException(status_code=401, detail="Incorrect password")
        log_audit(db, request, "Login", "Authentication",
                  f"{admin.name} logged in as Admin", "login",
                  user_name=admin.name, user_email=admin.email)
        return schemas.LoginResponse(
            name=admin.name,
            email=admin.email,
            role="Admin",
            mustChangePassword=admin.must_change_password,
        )

    log_audit(db, request, "Failed Login", "Authentication",
              f"Login attempt for unknown account: {email}", "error", "Failed",
              user_name="Unknown", user_email=email)
    raise HTTPException(status_code=401, detail="No account found with this email address")


@app.get(
    "/auth/users",
    response_model=List[schemas.AuthUserResponse],
    status_code=status.HTTP_200_OK,
    summary="Fetch login-form users (with password) for a given role",
    tags=["Auth"],
)
def get_auth_users(role: str = Query(default=""), db: Session = Depends(get_db)):
    if not role.strip():
        doctors = db.query(models.Doctor).all()
        receptionists = db.query(models.Receptionist).all()
        admins = db.query(models.Admin).all()
        return [
            schemas.AuthUserResponse(
                id=d.id, name=d.name, email=d.email or "",
                password="", role=d.role, specialization=d.specialization,
            )
            for d in doctors
        ] + [
            schemas.AuthUserResponse(
                id=r.id, name=r.name, email=r.email,
                password="", role="Receptionist",
            )
            for r in receptionists
        ] + [
            schemas.AuthUserResponse(
                id=a.id, name=a.name, email=a.email,
                password="", role="Admin",
            )
            for a in admins
        ]
    if role in ("Doctor", "Junior Doctor"):
        doctors = db.query(models.Doctor).filter(models.Doctor.role == role).all()
        return [
            schemas.AuthUserResponse(
                id=d.id, name=d.name, email=d.email or "",
                password="", role=d.role, specialization=d.specialization,
            )
            for d in doctors
        ]
    if role == "Receptionist":
        receptionists = db.query(models.Receptionist).all()
        return [
            schemas.AuthUserResponse(
                id=r.id, name=r.name, email=r.email,
                password="", role="Receptionist",
            )
            for r in receptionists
        ]
    raise HTTPException(status_code=400, detail="Invalid role specified")


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.get(
    "/admin/stats",
    response_model=schemas.AdminStats,
    tags=["Admin"],
    summary="Aggregated system statistics for admin dashboard",
)
def get_admin_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    total_doctors      = db.query(models.Doctor).count()
    total_receptionists = db.query(models.Receptionist).count()
    total_admins       = db.query(models.Admin).count()
    active_doctors     = db.query(models.Doctor).filter(models.Doctor.role == "Doctor").count()
    total_patients     = db.query(models.Patient).count()
    total_consultations = db.query(models.Consultation).count()
    return schemas.AdminStats(
        totalUsers=total_doctors + total_receptionists + total_admins,
        activeDoctors=active_doctors,
        totalPatients=total_patients,
        avgWaitingTime=14,
        consultationsTotal=total_consultations,
    )


@app.get(
    "/admin/patient-flow",
    response_model=List[schemas.PatientFlowDay],
    tags=["Admin"],
    summary="Consultation count per day for the last N days",
)
def get_patient_flow(days: int = Query(default=7, ge=7, le=30), db: Session = Depends(get_db)):
    from datetime import timedelta
    today = date.today()
    result = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        count = db.query(models.Consultation).filter(
            models.Consultation.consultation_date == d
        ).count()
        label = d.strftime("%a") if days <= 7 else d.strftime("%d %b")
        result.append(schemas.PatientFlowDay(day=label, count=count))
    return result


@app.get(
    "/admin/consultation-stats",
    response_model=List[schemas.ConsultationStat],
    tags=["Admin"],
    summary="Patient status breakdown for donut chart",
)
def get_consultation_stats(db: Session = Depends(get_db)):
    total     = db.query(models.Patient).count()
    completed = db.query(models.Patient).filter(models.Patient.status == "Consulted").count()
    checked   = db.query(models.Patient).filter(models.Patient.status == "Checked-In").count()
    registered = db.query(models.Patient).filter(models.Patient.status == "Registered").count()
    if total == 0:
        return [
            schemas.ConsultationStat(label="Completed", count=0, percentage=0),
            schemas.ConsultationStat(label="Pending",   count=0, percentage=0),
            schemas.ConsultationStat(label="Cancelled", count=0, percentage=0),
        ]
    pending = checked + registered
    return [
        schemas.ConsultationStat(label="Completed", count=completed, percentage=round(completed / total * 100, 1)),
        schemas.ConsultationStat(label="Pending",   count=pending,   percentage=round(pending   / total * 100, 1)),
        schemas.ConsultationStat(label="Cancelled", count=0,         percentage=0),
    ]


@app.get(
    "/admin/doctor-workload",
    response_model=List[schemas.DoctorWorkloadItem],
    tags=["Admin"],
    summary="Top doctors by assigned patient count",
)
def get_doctor_workload(db: Session = Depends(get_db)):
    from sqlalchemy import func
    rows = (
        db.query(models.Patient.doctor, func.count(models.Patient.id).label("cnt"))
        .filter(models.Patient.doctor.isnot(None))
        .group_by(models.Patient.doctor)
        .order_by(func.count(models.Patient.id).desc())
        .limit(5)
        .all()
    )
    if not rows:
        return []
    max_cnt = rows[0].cnt
    return [
        schemas.DoctorWorkloadItem(name=r.doctor, count=r.cnt, maxCount=max_cnt)
        for r in rows
    ]


@app.get(
    "/admin/audit-logs",
    response_model=List[schemas.AuditLogItem],
    tags=["Admin"],
    summary="Recent system activities derived from existing records",
)
def get_audit_logs(db: Session = Depends(get_db)):
    entries = []

    # Recent prescriptions
    for p in db.query(models.Prescription).order_by(models.Prescription.id.desc()).limit(2).all():
        pat = db.query(models.Patient).filter(models.Patient.id == p.patient_id).first()
        entries.append({
            "time": str(p.prescription_date),
            "user": p.doctor_name or "Doctor",
            "action": "Prescription Added",
            "module": "Consultation",
            "details": f"Prescription #{p.id:04d} created",
            "_sort": p.id + 30000,
        })

    # Recent consultations
    for c in db.query(models.Consultation).order_by(models.Consultation.id.desc()).limit(3).all():
        pat = db.query(models.Patient).filter(models.Patient.id == c.patient_id).first()
        entries.append({
            "time": str(c.consultation_date),
            "user": c.doctor_name or "Doctor",
            "action": "Consultation Added",
            "module": "Consultation",
            "details": f"Consultation for {pat.name if pat else 'patient'} recorded",
            "_sort": c.id + 20000,
        })

    # Recent check-ins
    for p in (
        db.query(models.Patient)
        .filter(models.Patient.checkin_time.isnot(None))
        .order_by(models.Patient.id.desc())
        .limit(2)
        .all()
    ):
        entries.append({
            "time": p.checkin_time or "—",
            "user": "Receptionist",
            "action": "Patient Check-in",
            "module": "Queue",
            "details": f"Patient MED-{p.id:04d} checked in",
            "_sort": p.id + 10000,
        })

    entries.sort(key=lambda x: x["_sort"], reverse=True)
    for e in entries:
        e.pop("_sort", None)
    return [schemas.AuditLogItem(**e) for e in entries[:6]]


# ── Admin User Management ─────────────────────────────────────────────────────

@app.get("/admin/users", response_model=List[schemas.AdminUserItem], tags=["Admin"])
def get_admin_users(
    role: str = Query(default=""),
    search: str = Query(default=""),
    db: Session = Depends(get_db),
):
    items: List[schemas.AdminUserItem] = []
    if not role or role in ("Doctor", "Junior Doctor"):
        for d in db.query(models.Doctor).all():
            if role and d.role != role:
                continue
            items.append(schemas.AdminUserItem(
                id=d.id, name=d.name, email=d.email or "", role=d.role,
                isActive=d.is_active, source="doctor",
                specialization=d.specialization, phone=d.phone,
            ))
    if not role or role == "Receptionist":
        for r in db.query(models.Receptionist).all():
            items.append(schemas.AdminUserItem(
                id=r.id, name=r.name, email=r.email, role="Receptionist",
                isActive=r.is_active, source="receptionist",
            ))
    if not role or role == "Admin":
        for a in db.query(models.Admin).all():
            items.append(schemas.AdminUserItem(
                id=a.id, name=a.name, email=a.email, role="Admin",
                isActive=a.is_active, source="admin",
            ))
    if search:
        q = search.lower()
        items = [i for i in items if q in i.name.lower() or q in i.email.lower()]
    return items


@app.post("/admin/users", response_model=schemas.AdminUserItem, status_code=201, tags=["Admin"])
def create_admin_user(data: schemas.AdminUserCreate, request: Request, db: Session = Depends(get_db)):
    import secrets, string
    chars = string.ascii_letters + string.digits + "!@#$"
    temp_pw = "".join(secrets.choice(chars) for _ in range(10))
    hashed_pw = _hash(temp_pw)
    full_name = f"{data.firstName} {data.lastName}".strip()

    if data.role in ("Doctor", "Junior Doctor"):
        doc = models.Doctor(
            name=full_name, specialization=data.specialization or "General Medicine",
            email=data.email, phone=data.phone,
            password=hashed_pw, role=data.role, is_active=True, must_change_password=True,
        )
        db.add(doc); db.commit(); db.refresh(doc)
        log_audit(db, request, "User Created", "User Management",
                  f"New {data.role} created: {full_name} ({data.email})", "create")
        if data.sendWelcomeEmail and data.email:
            email_service.send_welcome_email(data.email, full_name, temp_pw, data.role)
        return schemas.AdminUserItem(
            id=doc.id, name=doc.name, email=doc.email or "", role=doc.role,
            isActive=doc.is_active, source="doctor", specialization=doc.specialization,
        )
    if data.role == "Receptionist":
        rec = models.Receptionist(
            name=full_name, email=data.email,
            password=hashed_pw, is_active=True, must_change_password=True,
        )
        db.add(rec); db.commit(); db.refresh(rec)
        log_audit(db, request, "User Created", "User Management",
                  f"New Receptionist created: {full_name} ({data.email})", "create")
        if data.sendWelcomeEmail and data.email:
            email_service.send_welcome_email(data.email, full_name, temp_pw, data.role)
        return schemas.AdminUserItem(
            id=rec.id, name=rec.name, email=rec.email, role="Receptionist",
            isActive=rec.is_active, source="receptionist",
        )
    if data.role == "Admin":
        adm = models.Admin(
            name=full_name, email=data.email,
            password=hashed_pw, is_active=True, must_change_password=True,
        )
        db.add(adm); db.commit(); db.refresh(adm)
        log_audit(db, request, "User Created", "User Management",
                  f"New Admin created: {full_name} ({data.email})", "create")
        if data.sendWelcomeEmail and data.email:
            email_service.send_welcome_email(data.email, full_name, temp_pw, data.role)
        return schemas.AdminUserItem(
            id=adm.id, name=adm.name, email=adm.email, role="Admin",
            isActive=adm.is_active, source="admin",
        )
    raise HTTPException(status_code=400, detail="Invalid role")


@app.put("/admin/users/{source}/{user_id}/toggle", tags=["Admin"])
def toggle_user_status(source: str, user_id: int, request: Request, db: Session = Depends(get_db)):
    if source == "doctor":
        user = db.query(models.Doctor).filter(models.Doctor.id == user_id).first()
    elif source == "receptionist":
        user = db.query(models.Receptionist).filter(models.Receptionist.id == user_id).first()
    elif source == "admin":
        user = db.query(models.Admin).filter(models.Admin.id == user_id).first()
    else:
        raise HTTPException(status_code=400, detail="Invalid source")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    user_email = getattr(user, "email", "") or ""

    password_emailed = False
    if user.is_active:
        # Reactivating: issue a fresh temporary password and require a reset on next login.
        temp_pw = _gen_temp_password()
        user.password = _hash(temp_pw)
        user.must_change_password = True
        db.commit()
        if user_email:
            password_emailed = email_service.send_reactivation_email(user_email, user.name, temp_pw)
        log_audit(db, request, "User Enabled", "User Management",
                  f"{user.name} ({user_email}) reactivated — new temporary password "
                  f"{'emailed' if password_emailed else 'generated'}", "edit")
    else:
        db.commit()
        log_audit(db, request, "User Disabled", "User Management",
                  f"{user.name} ({user_email}) disabled", "edit")

    return {"isActive": user.is_active, "passwordEmailed": password_emailed}


@app.put("/admin/users/{source}/{user_id}", response_model=schemas.AdminUserItem, tags=["Admin"])
def update_admin_user_info(source: str, user_id: int, data: schemas.AdminUserUpdate, request: Request, db: Session = Depends(get_db)):
    def _apply_name(user, first, last):
        cur = (user.name or "").split(" ", 1)
        f = first if first is not None else (cur[0] if cur else "")
        l = last  if last  is not None else (cur[1] if len(cur) > 1 else "")
        user.name = f"{f} {l}".strip()

    if source == "doctor":
        user = db.query(models.Doctor).filter(models.Doctor.id == user_id).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        _apply_name(user, data.firstName, data.lastName)
        if data.email is not None:         user.email         = data.email
        if data.phone is not None:         user.phone         = data.phone
        if data.role  is not None:         user.role          = data.role
        if data.specialization is not None: user.specialization = data.specialization
        db.commit(); db.refresh(user)
        log_audit(db, request, "User Updated", "User Management",
                  f"Profile updated: {user.name} ({user.email or ''})", "edit")
        return schemas.AdminUserItem(id=user.id, name=user.name, email=user.email or "", role=user.role,
                                     isActive=user.is_active, source="doctor", specialization=user.specialization, phone=user.phone)

    if source == "receptionist":
        user = db.query(models.Receptionist).filter(models.Receptionist.id == user_id).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        _apply_name(user, data.firstName, data.lastName)
        if data.email is not None: user.email = data.email
        db.commit(); db.refresh(user)
        log_audit(db, request, "User Updated", "User Management",
                  f"Profile updated: {user.name} ({user.email})", "edit")
        return schemas.AdminUserItem(id=user.id, name=user.name, email=user.email, role="Receptionist",
                                     isActive=user.is_active, source="receptionist")

    if source == "admin":
        user = db.query(models.Admin).filter(models.Admin.id == user_id).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        _apply_name(user, data.firstName, data.lastName)
        if data.email is not None: user.email = data.email
        db.commit(); db.refresh(user)
        log_audit(db, request, "User Updated", "User Management",
                  f"Profile updated: {user.name} ({user.email})", "edit")
        return schemas.AdminUserItem(id=user.id, name=user.name, email=user.email, role="Admin",
                                     isActive=user.is_active, source="admin")

    raise HTTPException(status_code=400, detail="Invalid source")


@app.delete("/admin/users/{source}/{user_id}", tags=["Admin"])
def delete_admin_user(source: str, user_id: int, request: Request, db: Session = Depends(get_db)):
    if source == "doctor":
        user = db.query(models.Doctor).filter(models.Doctor.id == user_id).first()
    elif source == "receptionist":
        user = db.query(models.Receptionist).filter(models.Receptionist.id == user_id).first()
    elif source == "admin":
        user = db.query(models.Admin).filter(models.Admin.id == user_id).first()
    else:
        raise HTTPException(status_code=400, detail="Invalid source")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    deleted_name  = user.name
    deleted_email = getattr(user, "email", "") or ""
    db.delete(user)
    db.commit()
    log_audit(db, request, "User Deleted", "User Management",
              f"User account deleted: {deleted_name} ({deleted_email})", "delete")
    return {"deleted": True}


@app.post("/auth/change-password", tags=["Auth"])
def change_password(data: schemas.ChangePasswordRequest, request: Request, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    doctor = db.query(models.Doctor).filter(models.Doctor.email.ilike(email)).first()
    if doctor:
        if not _verify(data.currentPassword, doctor.password or ""):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        if len(data.newPassword) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        doctor.password = _hash(data.newPassword)
        doctor.must_change_password = False
        db.commit()
        log_audit(db, request, "Password Changed", "User Management",
                  f"Password changed for {doctor.name} ({email})", "security",
                  user_name=doctor.name, user_email=doctor.email or email)
        return {"success": True}

    receptionist = db.query(models.Receptionist).filter(models.Receptionist.email.ilike(email)).first()
    if receptionist:
        if not _verify(data.currentPassword, receptionist.password or ""):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        if len(data.newPassword) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        receptionist.password = _hash(data.newPassword)
        receptionist.must_change_password = False
        db.commit()
        log_audit(db, request, "Password Changed", "User Management",
                  f"Password changed for {receptionist.name} ({email})", "security",
                  user_name=receptionist.name, user_email=receptionist.email)
        return {"success": True}

    admin = db.query(models.Admin).filter(models.Admin.email.ilike(email)).first()
    if admin:
        if not _verify(data.currentPassword, admin.password or ""):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        if len(data.newPassword) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        admin.password = _hash(data.newPassword)
        admin.must_change_password = False
        db.commit()
        log_audit(db, request, "Password Changed", "User Management",
                  f"Password changed for {admin.name} ({email})", "security",
                  user_name=admin.name, user_email=admin.email)
        return {"success": True}

    raise HTTPException(status_code=404, detail="User not found")


# ── Admin Doctor Management ───────────────────────────────────────────────────

@app.get("/admin/doctor-stats", response_model=schemas.DoctorStats, tags=["Admin"])
def get_doctor_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    total = db.query(models.Doctor).count()
    active = db.query(models.Doctor).filter(models.Doctor.is_active == True).count()
    specializations = db.query(func.count(func.distinct(models.Doctor.specialization))).scalar() or 0
    return schemas.DoctorStats(total=total, active=active, inactive=total - active, specializations=specializations)


@app.post("/admin/doctors", response_model=schemas.DoctorResponse, status_code=201, tags=["Admin"])
def create_admin_doctor(data: schemas.AdminDoctorCreate, request: Request, db: Session = Depends(get_db)):
    first = data.name.replace("Dr.", "").strip().split()[0].lower()
    password = f"{first}@123"
    doc = models.Doctor(
        name=data.name, specialization=data.specialization,
        email=data.email, phone=data.phone,
        password=password, role=data.role, is_active=True,
        available_from=data.available_from or "09:00 AM",
        available_to=data.available_to   or "05:00 PM",
    )
    db.add(doc); db.commit(); db.refresh(doc)
    log_audit(db, request, "Doctor Added", "Doctor Management",
              f"New doctor added: {data.name} ({data.specialization})", "create")
    return doc


@app.put("/admin/doctors/{doctor_id}/toggle", tags=["Admin"])
def toggle_doctor_status(doctor_id: int, request: Request, db: Session = Depends(get_db)):
    doc = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
    doc.is_active = not doc.is_active
    db.commit()
    action = "Doctor Enabled" if doc.is_active else "Doctor Disabled"
    log_audit(db, request, action, "Doctor Management",
              f"{doc.name} ({doc.specialization}) {'enabled' if doc.is_active else 'disabled'}", "edit")
    return {"isActive": doc.is_active}


@app.put("/admin/doctors/{doctor_id}", response_model=schemas.DoctorResponse, tags=["Admin"])
def update_admin_doctor(doctor_id: int, data: schemas.DoctorUpdate, request: Request, db: Session = Depends(get_db)):
    doc = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
    if data.name is not None:           doc.name = data.name
    if data.specialization is not None: doc.specialization = data.specialization
    if data.email is not None:          doc.email = data.email
    if data.phone is not None:          doc.phone = data.phone
    if data.role is not None:           doc.role = data.role
    if data.available_from is not None: doc.available_from = data.available_from
    if data.available_to   is not None: doc.available_to   = data.available_to
    db.commit(); db.refresh(doc)
    log_audit(db, request, "Doctor Updated", "Doctor Management",
              f"Profile updated: {doc.name} ({doc.specialization})", "edit")
    return doc


@app.delete("/admin/doctors/{doctor_id}", tags=["Admin"])
def delete_admin_doctor(doctor_id: int, request: Request, db: Session = Depends(get_db)):
    doc = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
    deleted_name = doc.name
    deleted_spec = doc.specialization
    db.delete(doc)
    db.commit()
    log_audit(db, request, "Doctor Deleted", "Doctor Management",
              f"Doctor removed: {deleted_name} ({deleted_spec})", "delete")
    return {"deleted": True}


@app.get("/admin/waiting-time", response_model=List[schemas.WaitingTimeDay], tags=["Admin"])
def get_waiting_time(days: int = Query(default=7, ge=7, le=30), db: Session = Depends(get_db)):
    from datetime import timedelta
    today = date.today()
    result = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        count = db.query(models.Consultation).filter(
            models.Consultation.consultation_date == d
        ).count()
        # Derive approximate average waiting time: each consultation adds ~2 min of queue
        mins = round(min(45.0, max(0.0, count * 2.0 + (3.0 if count > 0 else 0.0))), 1)
        label = d.strftime("%a") if days <= 7 else d.strftime("%d %b")
        result.append(schemas.WaitingTimeDay(day=label, mins=mins))
    return result


@app.get("/admin/department-stats", response_model=List[schemas.DepartmentStat], tags=["Admin"])
def get_department_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    rows = (
        db.query(models.Doctor.specialization, func.count(models.Patient.id).label("cnt"))
        .join(models.Patient, models.Doctor.name == models.Patient.doctor)
        .group_by(models.Doctor.specialization)
        .order_by(func.count(models.Patient.id).desc())
        .limit(5)
        .all()
    )
    if not rows:
        return []
    total = sum(r.cnt for r in rows)
    if total == 0:
        return []
    return [
        schemas.DepartmentStat(
            department=r.specialization,
            count=r.cnt,
            percentage=round(r.cnt / total * 100, 1),
        )
        for r in rows
    ]


@app.get("/admin/peak-hours", response_model=List[schemas.PeakHour], tags=["Admin"])
def get_peak_hours(db: Session = Depends(get_db)):
    from datetime import datetime as _dt
    rows = db.query(models.Patient.checkin_time).filter(
        models.Patient.checkin_time.isnot(None)
    ).all()
    hour_counts: dict = {}
    for (t_str,) in rows:
        try:
            t = _dt.strptime(t_str.strip(), "%I:%M %p")
            hour_counts[t.hour] = hour_counts.get(t.hour, 0) + 1
        except Exception:
            pass
    # 2-hour buckets across typical clinic hours
    buckets = [(8, "8 AM"), (10, "10 AM"), (12, "12 PM"), (14, "2 PM"), (16, "4 PM"), (18, "6 PM"), (20, "8 PM")]
    result = []
    for start_h, label in buckets:
        count = sum(hour_counts.get(h, 0) for h in range(start_h, start_h + 2))
        mins = round(min(45.0, max(0.0, count * 3.0)), 1)
        result.append(schemas.PeakHour(hour=label, mins=mins))
    return result


@app.get("/admin/weekly-summary", response_model=schemas.WeeklySummary, tags=["Admin"])
def get_weekly_summary(db: Session = Depends(get_db)):
    from datetime import timedelta
    today = date.today()
    week_start      = today - timedelta(days=6)
    last_week_start = today - timedelta(days=13)
    last_week_end   = today - timedelta(days=7)

    total_patients      = db.query(models.Patient).count()
    total_consultations = db.query(models.Consultation).count()

    this_week_consults = db.query(models.Consultation).filter(
        models.Consultation.consultation_date >= week_start
    ).count()
    last_week_consults = db.query(models.Consultation).filter(
        models.Consultation.consultation_date >= last_week_start,
        models.Consultation.consultation_date <= last_week_end,
    ).count()

    consult_change = 0.0
    if last_week_consults > 0:
        consult_change = round((this_week_consults - last_week_consults) / last_week_consults * 100, 1)
    elif this_week_consults > 0:
        consult_change = 100.0

    # Derive average waiting time from this week's consultation density
    days_this_week = max(1, this_week_consults)
    avg_wait = min(45, max(0, round(days_this_week * 2)))

    return schemas.WeeklySummary(
        totalPatients=total_patients,
        totalConsultations=total_consultations,
        avgWaitingTime=avg_wait,
        cancelledConsultations=0,
        patientsChange=0.0,
        consultationsChange=consult_change,
        waitingTimeChange=0,
        cancelledChange=0.0,
    )


@app.get("/admin/audit-logs-full", response_model=schemas.AuditLogsResponse, tags=["Admin"])
def get_audit_logs_full(
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    search: str = Query(default=""),
    module: str = Query(default=""),
    action: str = Query(default=""),
    status_filter: str = Query(default="", alias="status"),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_
    query = db.query(models.AuditLog).order_by(models.AuditLog.id.desc())
    if search:
        q = f"%{search}%"
        query = query.filter(or_(
            models.AuditLog.user_name.ilike(q),
            models.AuditLog.action.ilike(q),
            models.AuditLog.module.ilike(q),
            models.AuditLog.details.ilike(q),
        ))
    if module:
        query = query.filter(models.AuditLog.module == module)
    if action:
        query = query.filter(models.AuditLog.action == action)
    if status_filter:
        query = query.filter(models.AuditLog.status == status_filter)
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    return schemas.AuditLogsResponse(
        total=total,
        logs=[
            schemas.AuditLogFull(
                id=log.id,
                time=log.timestamp,
                user=log.user_name or "System",
                userEmail=log.user_email or "",
                action=log.action,
                module=log.module,
                details=log.details or "",
                ipAddress=log.ip_address or "",
                status=log.status,
                actionType=log.action_type,
            )
            for log in logs
        ],
    )


# ── Receptionists ─────────────────────────────────────────────────────────────

@app.get(
    "/receptionists",
    response_model=List[schemas.ReceptionistResponse],
    status_code=status.HTTP_200_OK,
    summary="Get list of all receptionists",
    tags=["Receptionists"],
)
def get_receptionists(db: Session = Depends(get_db)):
    return db.query(models.Receptionist).all()


# ── Patients ──────────────────────────────────────────────────────────────────

@app.post(
    "/patients",
    response_model=schemas.PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient",
    tags=["Patients"],
)
def create_patient(patient: schemas.PatientCreate, request: Request, db: Session = Depends(get_db)):
    full_name = f"{patient.firstName} {patient.lastName}".strip()

    # Name + DOB duplicate check (always enforced)
    existing_name_dob = db.query(models.Patient).filter(
        models.Patient.name.ilike(full_name),
        models.Patient.dob == patient.dob
    ).first()
    if existing_name_dob:
        raise HTTPException(
            status_code=409,
            detail=f"Patient '{full_name}' with this date of birth is already registered (ID: MED-{existing_name_dob.id:04d})"
        )

    # Mobile duplicate check — skipped when registering a family member
    if patient.mobileNumber and not patient.allowDuplicateMobile:
        existing_mobile = db.query(models.Patient).filter(
            models.Patient.mobile_number == patient.mobileNumber
        ).first()
        if existing_mobile:
            raise HTTPException(
                status_code=409,
                detail=f"Mobile number {patient.mobileNumber} is already linked to {existing_mobile.name} (ID: MED-{existing_mobile.id:04d})"
            )
    db_patient = models.Patient(
        name=full_name,
        gender=patient.gender,
        dob=patient.dob,
        age=patient.age,
        mobile_number=patient.mobileNumber,
        insurance_company=patient.insuranceCompany,
        address_line1=None,
        address_line2=None,
        city=None,
        pin_code=None,
        status="Registered",
        medical_history=patient.medicalHistory,
        allergies=patient.allergies,
        id_proof_type=patient.idProofType,
        id_proof_number=patient.idProofNumber,
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    log_audit(db, request, "Patient Registered", "Patient Management",
              f"New patient registered: {db_patient.name} (MED-{db_patient.id:04d})", "create")
    return schemas.PatientResponse.from_orm_patient(db_patient)


@app.get(
    "/patients",
    response_model=List[schemas.PatientResponse],
    status_code=status.HTTP_200_OK,
    summary="Get list of all patients",
    tags=["Patients"],
)
def get_patients(
    skip: int = 0,
    limit: int = 100,
    search: str = "",
    patient_status: str = Query(default="", alias="status"),
    dob: str = Query(default=""),
    doctor: str = Query(default=""),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_
    from datetime import datetime as dt
    query = db.query(models.Patient)
    if search.strip():
        q = f"%{search.strip()}%"
        query = query.filter(
            or_(
                models.Patient.name.ilike(q),
                models.Patient.mobile_number.ilike(q),
            )
        )
    if patient_status.strip():
        query = query.filter(models.Patient.status == patient_status.strip())
    if doctor.strip():
        query = query.filter(models.Patient.doctor == doctor.strip())
    if dob.strip():
        try:
            dob_date = dt.strptime(dob.strip(), "%Y-%m-%d").date()
            query = query.filter(models.Patient.dob == dob_date)
        except ValueError:
            pass
    patients = query.order_by(models.Patient.id.desc()).offset(skip).limit(limit).all()
    return [schemas.PatientResponse.from_orm_patient(p) for p in patients]


@app.get(
    "/patients/check-duplicate",
    status_code=status.HTTP_200_OK,
    summary="Check if a patient with same name+DOB or mobile already exists",
    tags=["Patients"],
)
def check_duplicate_patient(
    name: str = "",
    dob: str = "",
    mobile: str = "",
    db: Session = Depends(get_db),
):
    from datetime import datetime as dt
    result = {
        "nameDobExists": False, "nameDobPatientId": None,
        "mobileExists": False, "mobilePatientName": None, "mobilePatientId": None,
    }
    if name.strip() and dob.strip():
        try:
            dob_date = dt.strptime(dob.strip(), "%Y-%m-%d").date()
            p = db.query(models.Patient).filter(
                models.Patient.name.ilike(name.strip()),
                models.Patient.dob == dob_date
            ).first()
            if p:
                result["nameDobExists"] = True
                result["nameDobPatientId"] = f"MED-{p.id:04d}"
        except ValueError:
            pass
    if mobile.strip():
        p = db.query(models.Patient).filter(
            models.Patient.mobile_number == mobile.strip()
        ).first()
        if p:
            result["mobileExists"] = True
            result["mobilePatientName"] = p.name
            result["mobilePatientId"] = f"MED-{p.id:04d}"
    return result


@app.get(
    "/patients/by-id-proof",
    response_model=schemas.PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Look up a patient by ID proof type and number",
    tags=["Patients"],
)
def get_patient_by_id_proof(
    id_proof_type: str,
    id_proof_number: str,
    db: Session = Depends(get_db),
):
    patient = db.query(models.Patient).filter(
        models.Patient.id_proof_type == id_proof_type,
        models.Patient.id_proof_number == id_proof_number.strip().upper(),
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="No patient found with this ID proof")
    return schemas.PatientResponse.from_orm_patient(patient)


@app.get(
    "/patients/{patient_id}",
    response_model=schemas.PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Get details of a selected patient",
    tags=["Patients"],
)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return schemas.PatientResponse.from_orm_patient(patient)


@app.put(
    "/patients/{patient_id}",
    response_model=schemas.PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Update patient details",
    tags=["Patients"],
)
def update_patient(patient_id: int, patient_data: schemas.PatientUpdate, request: Request, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    update_map = {
        "name": "name",
        "gender": "gender",
        "dob": "dob",
        "age": "age",
        "insuranceCompany": "insurance_company",
        "addressLine1": "address_line1",
        "addressLine2": "address_line2",
        "city": "city",
        "pinCode": "pin_code",
        "status": "status",
        "doctor": "doctor",
        "medicalHistory": "medical_history",
        "allergies": "allergies",
        "reasonForVisit": "reason_for_visit",
        "queueToken": "queue_token",
    }
    for schema_field, model_field in update_map.items():
        value = getattr(patient_data, schema_field, None)
        if value is not None:
            setattr(patient, model_field, value)

    # Capture check-in time
    if patient_data.status == "Checked-In" and not patient.checkin_time:
        from datetime import datetime as _dt
        patient.checkin_time = _dt.now().strftime("%I:%M %p")

    # Auto-generate doctor-wise queue token when checking in for the first time
    if patient_data.status == "Checked-In" and not patient.queue_token:
        assigned_doctor = patient_data.doctor or patient.doctor
        existing = db.query(models.Patient).filter(
            models.Patient.doctor == assigned_doctor,
            models.Patient.queue_token.isnot(None),
        ).count()
        patient.queue_token = f"Q-{existing + 1:03d}"

    db.commit()
    db.refresh(patient)
    if patient_data.status == "Checked-In":
        log_audit(db, request, "Patient Checked In", "Queue",
                  f"Patient checked in: {patient.name} (MED-{patient_id:04d}), token {patient.queue_token}", "checkin")
    elif patient_data.status:
        log_audit(db, request, "Patient Updated", "Patient Management",
                  f"Status → {patient_data.status}: {patient.name} (MED-{patient_id:04d})", "edit")
    else:
        log_audit(db, request, "Patient Updated", "Patient Management",
                  f"Record updated: {patient.name} (MED-{patient_id:04d})", "edit")
    return schemas.PatientResponse.from_orm_patient(patient)


# ── Doctors ───────────────────────────────────────────────────────────────────

@app.post(
    "/doctors",
    response_model=schemas.DoctorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new doctor",
    tags=["Doctors"],
)
def create_doctor(doctor: schemas.DoctorCreate, db: Session = Depends(get_db)):
    db_doctor = models.Doctor(
        name=doctor.name,
        specialization=doctor.specialization,
        phone=doctor.phone,
        email=doctor.email,
    )
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    return db_doctor


@app.get(
    "/doctors",
    response_model=List[schemas.DoctorResponse],
    status_code=status.HTTP_200_OK,
    summary="Get list of all doctors",
    tags=["Doctors"],
)
def get_doctors(
    skip: int = 0,
    limit: int = 100,
    role: str = Query(default=""),
    db: Session = Depends(get_db),
):
    query = db.query(models.Doctor)
    if role.strip():
        query = query.filter(models.Doctor.role == role.strip())
    return query.offset(skip).limit(limit).all()


# ── Insurance Companies ───────────────────────────────────────────────────────

@app.post(
    "/insurance-companies",
    response_model=schemas.InsuranceCompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new insurance company",
    tags=["Insurance"],
)
def create_insurance_company(company: schemas.InsuranceCompanyCreate, db: Session = Depends(get_db)):
    db_company = models.InsuranceCompany(
        name=company.name,
        contact_number=company.contactNumber,
        email=company.email,
    )
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return schemas.InsuranceCompanyResponse.from_orm_company(db_company)


@app.get(
    "/insurance-companies",
    response_model=List[schemas.InsuranceCompanyResponse],
    status_code=status.HTTP_200_OK,
    summary="Get list of all insurance companies",
    tags=["Insurance"],
)
def get_insurance_companies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    companies = db.query(models.InsuranceCompany).offset(skip).limit(limit).all()
    return [schemas.InsuranceCompanyResponse.from_orm_company(c) for c in companies]


# ── Consultations ─────────────────────────────────────────────────────────────

@app.post(
    "/consultations",
    response_model=schemas.ConsultationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a consultation record",
    tags=["Consultations"],
)
def create_consultation(consultation: schemas.ConsultationCreate, request: Request, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == consultation.patientId).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    db_consult = models.Consultation(
        patient_id=consultation.patientId,
        chief_complaint=consultation.chiefComplaint,
        consultation_date=date.today(),
        doctor_name=consultation.doctorName,
    )
    db.add(db_consult)
    # Set patient status to Waiting for Prescription
    patient.status = "Consulted"
    db.commit()
    db.refresh(db_consult)
    log_audit(db, request, "Consultation Added", "Consultation",
              f"Consultation for {patient.name} (MED-{consultation.patientId:04d}) by {consultation.doctorName or 'Doctor'}", "create")
    return schemas.ConsultationResponse.from_orm_consultation(db_consult)


@app.get(
    "/consultations/patient/{patient_id}",
    response_model=List[schemas.ConsultationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all consultations for a patient by ID",
    tags=["Consultations"],
)
def get_patient_consultations(patient_id: int, db: Session = Depends(get_db)):
    consultations = (
        db.query(models.Consultation)
        .filter(models.Consultation.patient_id == patient_id)
        .all()
    )
    return [schemas.ConsultationResponse.from_orm_consultation(c) for c in consultations]


# ── Medications ──────────────────────────────────────────────────────────────

@app.get(
    "/medications",
    response_model=List[schemas.MedicationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all medications",
    tags=["Medications"],
)
def get_medications(search: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Medication)
    if search.strip():
        query = query.filter(models.Medication.name.ilike(f"%{search.strip()}%"))
    return [schemas.MedicationResponse.from_orm_medication(m) for m in query.all()]


# ── Prescriptions ────────────────────────────────────────────────────────────

@app.post(
    "/prescriptions",
    response_model=schemas.PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a prescription and mark patient as Completed",
    tags=["Prescriptions"],
)
def create_prescription(prescription: schemas.PrescriptionCreate, request: Request, db: Session = Depends(get_db)):
    import json
    patient = db.query(models.Patient).filter(models.Patient.id == prescription.patientId).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    meds_json = json.dumps([m.model_dump() for m in prescription.medications])
    db_prescription = models.Prescription(
        patient_id=prescription.patientId,
        medications=meds_json,
        doctor_name=prescription.doctorName,
        prescription_date=date.today(),
        notes=prescription.notes,
    )
    db.add(db_prescription)
    patient.status = "Completed"
    db.commit()
    db.refresh(db_prescription)
    log_audit(db, request, "Prescription Added", "Consultation",
              f"Prescription #{db_prescription.id:04d} for {patient.name} (MED-{prescription.patientId:04d}) by {prescription.doctorName or 'Doctor'}", "edit")
    return schemas.PrescriptionResponse.from_orm_prescription(db_prescription)


@app.get(
    "/prescriptions/patient/{patient_id}",
    response_model=List[schemas.PrescriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get prescriptions for a patient",
    tags=["Prescriptions"],
)
def get_patient_prescriptions(patient_id: int, db: Session = Depends(get_db)):
    prescriptions = (
        db.query(models.Prescription)
        .filter(models.Prescription.patient_id == patient_id)
        .order_by(models.Prescription.prescription_date.desc())
        .all()
    )
    return [schemas.PrescriptionResponse.from_orm_prescription(p) for p in prescriptions]


@app.get(
    "/dashboard/stats",
    status_code=status.HTTP_200_OK,
    summary="Get dashboard statistics",
    tags=["Dashboard"],
)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(models.Patient).count()
    checked_in = db.query(models.Patient).filter(models.Patient.status == "Checked-In").count()
    in_consultation = db.query(models.Patient).filter(models.Patient.status == "Consulted").count()
    completed = db.query(models.Patient).filter(models.Patient.status == "Completed").count()
    doctor_count = db.query(models.Doctor).count()
    return {
        "totalPatients": total,
        "checkedIn": checked_in,
        "inConsultation": in_consultation,
        "completed": completed,
        "doctorsOnDuty": doctor_count,
    }


@app.get(
    "/consultations/count-by-patient",
    status_code=status.HTTP_200_OK,
    summary="Count consultations matched by name + DOB + insurance company",
    tags=["Consultations"],
)
def count_consultations_by_patient(
    name: str,
    dob: str,
    insurance: str = "",
    db: Session = Depends(get_db),
):
    from datetime import datetime as dt
    query = db.query(models.Patient).filter(
        models.Patient.name.ilike(name.strip())
    )
    try:
        dob_date = dt.strptime(dob.strip(), "%Y-%m-%d").date()
        query = query.filter(models.Patient.dob == dob_date)
    except ValueError:
        pass
    if insurance.strip():
        query = query.filter(
            models.Patient.insurance_company.ilike(insurance.strip())
        )
    matching_patients = query.all()
    patient_ids = [p.id for p in matching_patients]
    count = 0
    if patient_ids:
        count = (
            db.query(models.Consultation)
            .filter(models.Consultation.patient_id.in_(patient_ids))
            .count()
        )
    return {"count": count}
