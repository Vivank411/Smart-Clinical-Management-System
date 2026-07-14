# MedClinic — Backend

> **FastAPI + PostgreSQL + SQLAlchemy**
> REST API for a hospital outpatient management system covering patient registration, check-in queues, doctor consultations, e-prescriptions, and a full administrative control plane.

---

## Table of Contents

1. [Technology Stack](#1-technology-stack)
2. [Architecture Overview](#2-architecture-overview)
3. [Project File Map](#3-project-file-map)
4. [Database Models](#4-database-models)
5. [API Endpoints — Full Reference](#5-api-endpoints--full-reference)
6. [Core Features & How They Work](#6-core-features--how-they-work)
   - 6.1 Multi-Role Authentication & Deactivation Guard
   - 6.2 Role-Based Access Control (RBAC)
   - 6.3 Patient Registration & Duplicate Detection
   - 6.4 ID Proof Validation
   - 6.5 Patient Check-In & Queue Token System
   - 6.6 Consultation & E-Prescription Workflow
   - 6.7 Audit Logging
   - 6.8 Admin Analytics Engine
   - 6.9 User & Doctor Management
   - 6.10 Email Notifications
7. [Key Concepts & Patterns Used](#7-key-concepts--patterns-used)
8. [Frontend ↔ Backend Connection Map](#8-frontend--backend-connection-map)
9. [Environment & Configuration](#9-environment--configuration)
10. [CTO-Level Interview Questions](#10-cto-level-interview-questions)

---

## 1. Technology Stack

| Layer | Technology | Version | Why |
|---|---|---|---|
| Web Framework | **FastAPI** | 0.110+ | Async-first, auto OpenAPI docs, Pydantic integration |
| ORM | **SQLAlchemy** | 2.x | Declarative models, session management, raw-SQL escape hatch |
| Database | **PostgreSQL** | 15+ | ACID compliance, JSONB support, robust indexing |
| Data Validation | **Pydantic v2** | 2.x | Schema-enforced request/response, field validators, model validators |
| Password Security | **bcrypt** (via passlib) | — | One-way adaptive hash, resistant to brute-force |
| Email | **smtplib** (stdlib) | — | Zero-dependency SMTP; HTML welcome/reset emails |
| Server | **Uvicorn** | — | ASGI server for FastAPI |
| Python | **3.11+** | — | Pattern matching, `tomllib`, faster CPython |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI App                          │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌─────────────┐              │
│  │  Schemas │  │  Models  │  │ email_service│              │
│  │(Pydantic)│  │(SQLAlch.)│  │  (SMTP)      │              │
│  └────┬─────┘  └────┬─────┘  └──────┬──────┘              │
│       │              │               │                      │
│  ┌────▼──────────────▼───────────────▼──────┐              │
│  │               main.py                    │              │
│  │   (Routes · Business Logic · log_audit)  │              │
│  └──────────────────┬───────────────────────┘              │
│                     │                                       │
│  ┌──────────────────▼───────────────────────┐              │
│  │              database.py                 │              │
│  │   (Engine · SessionLocal · get_db)        │              │
│  └──────────────────┬───────────────────────┘              │
└─────────────────────┼───────────────────────────────────────┘
                      │ SQLAlchemy ORM / psycopg2
                      ▼
             ┌─────────────────┐
             │   PostgreSQL    │
             └─────────────────┘
```

All requests flow through FastAPI route handlers in `main.py`. There is no separate service layer — business logic lives in route functions, kept intentionally thin. Pydantic schemas enforce contract on ingress and egress. SQLAlchemy sessions are injected per-request via `Depends(get_db)`.

---

## 3. Project File Map

### `database.py`
Creates the SQLAlchemy engine from the `DATABASE_URL` environment variable, defines `SessionLocal` (a factory for DB sessions), and exposes the `get_db()` generator used as a FastAPI dependency injector. Every route that touches the database receives a fresh session and guarantees it is closed after the response is sent.

**Why a generator?** FastAPI's `Depends()` supports generator-style dependencies — the `yield` hands the session to the route, and everything after `yield` runs as cleanup (close session), even if an exception is thrown.

---

### `models.py`
Defines the SQLAlchemy ORM classes that map directly to PostgreSQL tables. Each class inherits from `Base = declarative_base()`. No FK relationships between `Patient.doctor` and `Doctor.name` are enforced at the DB level; the join is done via a string equality filter (`Doctor.name == Patient.doctor`) to allow flexibility in renaming doctors without cascading patient record updates.

---

### `schemas.py`
Contains 38+ Pydantic models split into three categories:
- **Request bodies** (`PatientCreate`, `LoginRequest`, `AdminDoctorCreate`, …) — validate incoming JSON, reject invalid data before it reaches the database.
- **Response models** (`PatientResponse`, `LoginResponse`, `AuditLogFull`, …) — control exactly what is returned to the client; no internal fields leak.
- **Cross-cutting** (`MedicationItem` embedded in `PrescriptionCreate`) — shared sub-models reused across multiple endpoints.

Field validators (`@field_validator`) handle complex rules (mobile digit count, name character set, age vs DOB cross-check). Model validators (`@model_validator(mode='after')`) enforce multi-field invariants.

---

### `main.py`
The application entry point. Contains:
- `lifespan()` context manager — runs DB migrations (`ALTER TABLE … ADD COLUMN IF NOT EXISTS`) on startup so the app is self-healing without a separate migration tool.
- `_verify()` — password check function supporting both bcrypt hashes and plaintext (legacy fallback for seeded users).
- `log_audit()` — central audit writer used by every mutating endpoint.
- All 35+ route handlers organized by domain tag.

---

### `email_service.py`
Provides `send_welcome_email()` and `send_password_reset_email()` using Python's `smtplib`. Reads SMTP credentials from environment variables. Sends HTML-formatted emails. Called only from admin user creation and password-reset endpoints. If email sending fails, the error is caught and logged but does not roll back the DB operation (fire-and-forget pattern — the account is created regardless of email delivery).

---

## 4. Database Models

### `Patient`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | Auto-increment |
| name | String(100) | Full name |
| gender | String(10) | Male / Female / Other |
| dob | Date | Used for age cross-validation |
| age | Integer | Stored redundantly for quick display |
| mobile_number | String(10) | Digits only, unique-ish (soft check) |
| insurance_company | String(150) | Free text, matches InsuranceCompany.name |
| address_line1/2, city, pin_code | String | Address fields |
| status | String(50) | Registered / Checked-In / In-Consultation / Completed / Cancelled |
| doctor | String(100) | Assigned doctor name (non-FK) |
| medical_history, allergies | Text | Clinical notes |
| reason_for_visit | Text | Chief complaint summary |
| queue_token | String(20) | e.g. `CARD-001` |
| checkin_time | String(10) | `HH:MM AM/PM` string |
| id_proof_type, id_proof_number | String | Aadhaar, PAN, etc. |

### `Doctor`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | — |
| name, specialization | String | — |
| phone, email | String | email used for login |
| password | String(255) | bcrypt hash |
| role | String(50) | Doctor / Junior Doctor |
| is_active | Boolean | Login blocked when False |
| must_change_password | Boolean | Forces change on first login |
| available_from, available_to | String(10) | `09:00 AM` format |

### `Receptionist`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | — |
| name, email, password | String | Login credentials |
| is_active | Boolean | Login blocked when False |
| must_change_password | Boolean | — |

### `Admin`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | — |
| name, email, password | String | — |
| is_active | Boolean | Login blocked when False |
| must_change_password | Boolean | — |

### `InsuranceCompany`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | — |
| name | String(150) | Unique company name |
| contact_number, email | String | — |

### `Consultation`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | — |
| patient_id | Integer | Soft FK to Patient.id |
| chief_complaint | Text | — |
| consultation_date | Date | Auto-set to today |
| doctor_name | String(100) | Name at time of consult |

### `Prescription`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | — |
| patient_id | Integer | Soft FK to Patient.id |
| medications | Text | JSON array of `{name, dosage, frequency, duration}` |
| doctor_name | String(100) | — |
| prescription_date | Date | Auto-set to today |
| notes | Text | Free-form clinical notes |

### `Medication`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | — |
| name | String(200) | Drug name |
| category | String(100) | E.g. Antibiotic, Analgesic |
| default_dosage | String(100) | Pre-filled suggestion |

### `AuditLog`
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | Auto-increment, immutable |
| timestamp | String(30) | `Jun 28, 2025 02:30 PM` |
| user_name, user_email | String | Extracted from request headers |
| action | String(100) | `Login`, `User Created`, `Prescription Created`, … |
| module | String(50) | `Authentication`, `Patient Management`, … |
| details | Text | Human-readable event description |
| ip_address | String(50) | From `request.client.host` |
| status | String(20) | `Success` / `Failed` |
| action_type | String(20) | `login`, `create`, `edit`, `delete`, `error` |

---

## 5. API Endpoints — Full Reference

### Authentication
| Method | Path | Request Body | Response | Use Case |
|---|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | `LoginResponse` | Authenticate any user type |
| GET | `/auth/users` | `?role=Doctor` | `AuthUserResponse[]` | Populate login autocomplete |
| POST | `/auth/change-password` | `{email, currentPassword, newPassword}` | `{success}` | First-login or voluntary change |

### Patient Management
| Method | Path | Notes |
|---|---|---|
| POST | `/patients` | Create patient; runs duplicate check |
| GET | `/patients` | Paginated, filterable by search/status/dob/doctor |
| GET | `/patients/check-duplicate` | Returns `nameDobExists` and `mobileExists` flags |
| GET | `/patients/by-id-proof` | Lookup by ID type + number |
| GET | `/patients/{id}` | Single patient detail |
| PUT | `/patients/{id}` | Update status, doctor, check-in time, clinical notes |

### Doctor / Receptionist / Insurance
| Method | Path | Notes |
|---|---|---|
| GET | `/doctors` | List with optional role filter |
| GET | `/receptionists` | All receptionists |
| GET | `/insurance-companies` | All companies |

### Consultation & Clinical
| Method | Path | Notes |
|---|---|---|
| POST | `/consultations` | Record consultation; auto-sets today's date |
| GET | `/consultations/patient/{id}` | History for patient |
| GET | `/medications` | Search by name substring |
| POST | `/prescriptions` | Save JSON medication array |
| GET | `/prescriptions/patient/{id}` | Prescription history |

### Dashboard
| Method | Path | Notes |
|---|---|---|
| GET | `/dashboard/stats` | Live counts: checked-in, in-consultation, completed |

### Admin — Analytics
| Method | Path | Notes |
|---|---|---|
| GET | `/admin/stats` | System-wide KPIs |
| GET | `/admin/patient-flow` | `?days=7` — consultation count per day |
| GET | `/admin/waiting-time` | `?days=7` — derived average wait per day |
| GET | `/admin/department-stats` | Patient count by doctor specialization |
| GET | `/admin/peak-hours` | Check-in time distribution in 2-hr buckets |
| GET | `/admin/weekly-summary` | This-week vs last-week delta metrics |
| GET | `/admin/consultation-stats` | Status breakdown (Completed, Pending, Cancelled) |
| GET | `/admin/doctor-workload` | Top 5 doctors by assigned patient count |
| GET | `/admin/audit-logs` | Short-form recent activity feed |
| GET | `/admin/audit-logs-full` | Paginated, searchable, filterable full audit trail |

### Admin — User & Doctor Management
| Method | Path | Notes |
|---|---|---|
| GET | `/admin/users` | Merged list: doctors + receptionists + admins |
| POST | `/admin/users` | Create any role; sends welcome email |
| PUT | `/admin/users/{source}/{id}/toggle` | Enable / Disable account. On **enable**, a new temp password is generated, `must_change_password` is set, and the password is emailed to the user |
| PUT | `/admin/users/{source}/{id}` | Update profile |
| DELETE | `/admin/users/{source}/{id}` | Hard delete |
| GET | `/admin/doctor-stats` | Doctor KPIs |
| POST | `/admin/doctors` | Create doctor (separate from user management) |
| PUT | `/admin/doctors/{id}/toggle` | Enable / Disable doctor |
| PUT | `/admin/doctors/{id}` | Update doctor including availability |
| DELETE | `/admin/doctors/{id}` | Hard delete doctor |

---

## 6. Core Features & How They Work

### 6.1 Multi-Role Authentication & Deactivation Guard

**What:** Single login endpoint (`POST /auth/login`) authenticates three user types: Doctor (and Junior Doctor), Receptionist, Admin.

**How:**
1. Normalize email to lowercase.
2. Query `doctors` table first, then `receptionists`, then `admins`.
3. **Deactivation check first**: if `is_active == False`, return HTTP 403 with `"Your account has been deactivated. Please contact the administrator."` — password is never evaluated.
4. If active, verify password using `_verify()` which tries bcrypt first, then falls back to plaintext comparison (for legacy seeded accounts).
5. On success, return role, name, email, specialization, and `mustChangePassword` flag.
6. Every outcome (success, wrong password, deactivated, not found) is written to `AuditLog`.

**Why deactivation before password?** Prevents timing attacks that could leak whether a deactivated account exists by always returning 403 (not a credential error) without doing the expensive bcrypt computation.

**Why check `is_active` before password hash?** Computationally: bcrypt is intentionally slow (cost factor 12 = ~300ms). Checking a boolean first is O(1) and avoids wasting CPU on blocked accounts.

---

### 6.2 Role-Based Access Control (RBAC)

**What:** The backend does not have auth middleware — RBAC is enforced at the frontend routing layer. The API itself is accessible to any caller with valid credentials because this is an internal clinic LAN application.

**How:**
- Login response includes `role` field (`"Doctor"`, `"Junior Doctor"`, `"Receptionist"`, `"Admin"`).
- Frontend stores this in `sessionStorage` and routes the user to their designated landing page via `AuthService.homeRoute`.
- Angular `authGuard` blocks unauthenticated access to all non-login routes.

**Why no backend JWT/RBAC?** The application runs on a closed hospital intranet. Adding token validation on every request adds latency without meaningful security gain in a trusted network. This is a deliberate trade-off documented as a known future enhancement.

---

### 6.3 Patient Registration & Duplicate Detection

**What:** Patient registration runs two independent checks before writing to the database.

**How:**
1. `GET /patients/check-duplicate?name=X&dob=Y&mobile=Z` returns two flags: `nameDobExists` and `mobileExists`.
2. Frontend calls this inline as the user types and shows warnings.
3. If `mobileExists` and the user still submits, the `allowDuplicateMobile: true` flag in the request body bypasses that specific check.
4. The `PatientCreate` Pydantic schema uses `@model_validator(mode='after')` to cross-check that `age` matches `dob` within ±1 year tolerance.
5. Patient ID is auto-generated as `MED-{id:04d}` (e.g., `MED-0042`) in the response schema, not stored in the DB.

**Why not enforce unique mobile at DB level?** Family members sometimes share a phone number. Soft duplicate detection with user override is more practical in a clinical setting.

---

### 6.4 ID Proof Validation

**What:** When registering a patient with an ID proof (Aadhaar, PAN, Passport, Voter ID, Driving Licence), the number format is validated server-side.

**How:** `schemas.py` defines a `_ID_PATTERNS` dictionary mapping each proof type to a compiled regex. The `@model_validator` on `PatientCreate` applies the regex and raises a `ValueError` if it doesn't match. Pydantic converts this to a 422 Unprocessable Entity response automatically.

```python
_ID_PATTERNS = {
    'Aadhaar Card':    re.compile(r'^\d{12}$'),
    'PAN Card':        re.compile(r'^[A-Z]{5}\d{4}[A-Z]$'),
    'Passport':        re.compile(r'^[A-Z]\d{7}$'),
    ...
}
```

**Why server-side?** Frontend validation is UX sugar; server-side validation is the real contract. Any API call bypassing the browser still hits the rule.

---

### 6.5 Patient Check-In & Queue Token System

**What:** When a patient arrives, the receptionist checks them in, which sets `status = "Checked-In"`, records `checkin_time`, and assigns a `queue_token`.

**How:**
- `PUT /patients/{id}` with body `{status: "Checked-In", queueToken: "CARD-001", checkinTime: "10:30 AM"}`.
- Queue tokens are generated client-side in the check-in component based on doctor specialization prefix + sequential number.
- The `checkin_time` string is later parsed by the analytics engine for peak-hour bucketing.

**Why string time format?** PostgreSQL `TIME` type would require timezone handling. Storing `"10:30 AM"` as a string simplifies display and avoids timezone conversion bugs in a single-clinic context.

---

### 6.6 Consultation & E-Prescription Workflow

**What:** Doctors record consultations and generate electronic prescriptions linked to a patient.

**How:**
1. `POST /consultations` — records chief complaint, auto-sets `consultation_date = date.today()`, links to patient.
2. Doctor searches medications via `GET /medications?search=parac`.
3. `POST /prescriptions` — stores an array of `{name, dosage, frequency, duration}` objects as JSON string in `medications` column.
4. Prescription retrieval parses the JSON string back to objects in `PrescriptionResponse.from_orm_prescription()`.

**Why JSON in a Text column for medications?** A prescription is a point-in-time document. Normalizing into a `prescription_medications` junction table would complicate retrieval and make historic prescriptions sensitive to drug name changes in the master `medications` table. JSON snapshot preserves exactly what was prescribed.

---

### 6.7 Audit Logging

**What:** Every write operation (create, update, delete, login, toggle) writes one row to `audit_logs`. The table is append-only — no update or delete endpoint exists for audit logs.

**How:**
- `log_audit(db, request, action, module, details, action_type, status, user_name, user_email)` is a helper function called inside every mutating route handler.
- User identity comes from two custom HTTP headers: `X-User-Name` and `X-User-Email`, set by the Angular interceptor on every request.
- IP address is read from `request.client.host`.
- If the audit write itself fails (e.g., DB connection drop), it rolls back only the audit insert and logs to stdout — the main business operation is not rolled back.

**Why custom headers instead of a JWT claim?** Simpler to implement in this intranet context. The frontend uses a functional interceptor (`HttpInterceptorFn`) that reads the stored session user and adds the headers transparently to every outgoing HTTP request.

**Why `module` and `action_type` as separate columns?** Enables multi-dimension filtering in the audit viewer: filter by module (e.g., show only Authentication events), by action type (e.g., show only deletes), by status (Success vs Failed), or combine.

---

### 6.8 Admin Analytics Engine

**What:** Eight endpoints provide real-time analytics from the live database.

**How each works:**

| Endpoint | Data Source | Derivation |
|---|---|---|
| `/admin/patient-flow` | `consultations.consultation_date` | Count rows per date in last N days |
| `/admin/waiting-time` | `consultations.consultation_date` | Derived: `min(45, count × 2.0 + 3.0)` mins |
| `/admin/department-stats` | String-join `Doctor.name == Patient.doctor` | Group by `Doctor.specialization`, compute % |
| `/admin/peak-hours` | `patients.checkin_time` | Parse time string, bucket into 2-hr slots, derive wait mins |
| `/admin/weekly-summary` | `consultations` | Compare this ISO-week vs last ISO-week |
| `/admin/consultation-stats` | `patients.status` | Count by status, compute % |
| `/admin/doctor-workload` | `patients.doctor` | Group by doctor name, top 5 |
| `/admin/audit-logs` | `audit_logs` | Last 10 rows ordered by id DESC |

**Why derived wait time?** The schema has no explicit wait-time column. The formula approximates real-world queuing: more consultations in a day correlates with longer waits. This is explicitly a model, not a measurement.

---

### 6.9 User & Doctor Management

**What:** Admins can create, update, toggle (enable/disable), and delete users across all roles. Password reset generates a random temporary password.

**How:**
- `source` path parameter (`doctor`, `receptionist`, `admin`) routes the operation to the correct SQLAlchemy model.
- Toggle checks current `is_active` and flips it with `not user.is_active`.
- Deactivated accounts are immediately blocked from login (no session invalidation needed — sessions are stateless).
- Password reset: generates an 8-character temp password, bcrypt-hashes it, stores it, sets `must_change_password = True`, and emails the user.

**Why no hard delete with cascade?** Doctors and receptionists may have patient records, consultations, and prescriptions referencing their names. Hard delete is allowed because those are string references (not FKs), so no cascade risk — referenced names persist in other tables.

---

### 6.10 Email Notifications

**What:** Welcome emails on user creation and password-reset emails are sent via SMTP.

**How:** `email_service.py` uses `smtplib.SMTP_SSL` with credentials from environment variables. Emails contain HTML-formatted content with temporary passwords. Called asynchronously (fire-and-forget in the same thread) — the HTTP response is sent after DB commit regardless of email success.

**Why not async email sending?** In a small clinic deployment, SMTP latency (~100ms) is acceptable inline. A proper production system would use a task queue (Celery + Redis).

---

## 7. Key Concepts & Patterns Used

### Pydantic v2 Schema Validation
- All HTTP request bodies are validated before the function body executes.
- Field-level validators run first, then model-level validators for cross-field rules.
- Invalid input returns HTTP 422 with detailed field-level error messages — no manual try/except needed.

### SQLAlchemy Dependency Injection
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
FastAPI's `Depends(get_db)` injects a fresh DB session per request and guarantees cleanup. This is the Repository Pattern without an explicit repository class.

### Self-Healing Migrations via `lifespan`
```python
conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS available_from VARCHAR(10)"))
```
`IF NOT EXISTS` makes each migration idempotent. No migration tool (Alembic) is needed for additive changes. This approach only works for `ADD COLUMN` — destructive changes still require manual intervention.

### Soft FK Pattern
`Patient.doctor` stores the doctor's name as a string. Analytics joins use:
```python
db.query(Doctor, func.count(Patient.id)).join(Patient, Doctor.name == Patient.doctor)
```
Trade-off: renaming a doctor does not cascade, but it avoids complex FK constraint management in a schema that evolves frequently.

### Audit Log Separation of Concerns
`log_audit()` is isolated — it has its own `try/except` with `db.rollback()` scoped only to the audit insert. The main transaction is committed before `log_audit()` is called, so a broken audit write never rolls back the business operation.

### Derived Analytics (No Dedicated Metrics Store)
Wait time, peak hours, and weekly deltas are computed on-the-fly from the operational database. Acceptable at clinic scale (~1,000 records). At scale, these would be pre-computed into a time-series store (InfluxDB, TimescaleDB).

### CORS Configuration
The app exposes `*` for allowed origins (suitable for intranet). Production hardening would restrict to the Angular app's specific origin.

---

## 8. Frontend ↔ Backend Connection Map

| Frontend Component | Angular Service Method | Backend Endpoint |
|---|---|---|
| `LoginComponent` | `api.login()` | `POST /auth/login` |
| `LoginComponent` | `api.getAuthUsers()` | `GET /auth/users` |
| `ChangePasswordComponent` | `api.changePassword()` | `POST /auth/change-password` |
| `DashboardComponent` | `api.getDashboardStats()` | `GET /dashboard/stats` |
| `PatientRegistrationComponent` | `api.createPatient()` | `POST /patients` |
| `PatientRegistrationComponent` | `api.checkDuplicate()` | `GET /patients/check-duplicate` |
| `PatientRegistrationComponent` | `api.getInsuranceCompanies()` | `GET /insurance-companies` |
| `SearchPatientComponent` | `api.getPatients()` | `GET /patients` |
| `CheckInComponent` | `api.getPatients()` | `GET /patients` |
| `CheckInComponent` | `api.updatePatient()` | `PUT /patients/{id}` |
| `DoctorQueueComponent` | `api.getPatients()` | `GET /patients?doctor=X&status=Checked-In` |
| `ConsultationComponent` | `api.createConsultation()` | `POST /consultations` |
| `ConsultationComponent` | `api.updatePatient()` | `PUT /patients/{id}` |
| `DoctorEprescriptionComponent` | `api.getMedications()` | `GET /medications` |
| `DoctorEprescriptionComponent` | `api.createPrescription()` | `POST /prescriptions` |
| `DoctorPatientRecordsComponent` | `api.getPatientConsultations()` | `GET /consultations/patient/{id}` |
| `DoctorPatientRecordsComponent` | `api.getPatientPrescriptions()` | `GET /prescriptions/patient/{id}` |
| `AdminDashboardComponent` | `api.getAdminStats()` | `GET /admin/stats` |
| `AdminUsersComponent` | `api.getAdminUsers()` | `GET /admin/users` |
| `AdminUsersComponent` | `api.createAdminUser()` | `POST /admin/users` |
| `AdminUsersComponent` | `api.toggleUserStatus()` | `PUT /admin/users/{source}/{id}/toggle` |
| `AdminDoctorsComponent` | `api.getDoctors()` | `GET /doctors` |
| `AdminDoctorsComponent` | `api.createAdminDoctor()` | `POST /admin/doctors` |
| `AdminDoctorsComponent` | `api.updateAdminDoctor()` | `PUT /admin/doctors/{id}` |
| `AdminDoctorsComponent` | `api.deleteAdminDoctor()` | `DELETE /admin/doctors/{id}` |
| `AdminReportsComponent` | `api.getPatientFlow()` | `GET /admin/patient-flow?days=N` |
| `AdminReportsComponent` | `api.getWaitingTime()` | `GET /admin/waiting-time?days=N` |
| `AdminReportsComponent` | `api.getDepartmentStats()` | `GET /admin/department-stats` |
| `AdminReportsComponent` | `api.getPeakHours()` | `GET /admin/peak-hours` |
| `AdminReportsComponent` | `api.getWeeklySummary()` | `GET /admin/weekly-summary` |
| `AdminAuditComponent` | `api.getAuditLogsFull()` | `GET /admin/audit-logs-full` |

**Header injection:** Every HTTP call above automatically carries `X-User-Name` and `X-User-Email` headers via the Angular `authHeaderInterceptor`, which reads from `AuthService` (sessionStorage). The backend's `log_audit()` reads these headers to identify who performed each action.

---

## 9. Environment & Configuration

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/medclinic
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=noreply@clinic.com
SMTP_PASSWORD=app-specific-password
```

The app reads `DATABASE_URL` in `database.py` and SMTP config in `email_service.py`. No `.env` file loader is bundled — the OS environment is the source of truth.

---

## 10. CTO-Level Interview Questions

> Acting as CTO — these are the questions you'd ask a backend developer in a technical review of this system.

---

**Q1. The login endpoint queries three separate tables sequentially. What is the performance implication at scale, and how would you fix it?**

*Expected answer:* Each login attempt does up to three DB round-trips (doctor → receptionist → admin). At scale, this should be unified into a single `users` view or abstract user table that all roles join to. Alternatively, cache the email-to-role mapping in Redis with a short TTL so the first lookup is O(1). Also, adding a database index on `email` in all three tables (currently missing) eliminates sequential scans.

---

**Q2. Audit logs are written in the same request-response cycle as the business operation. What failure modes exist, and how would you make the audit trail more resilient?**

*Expected answer:* If the audit write fails after the main commit, the business operation succeeds but leaves no audit trace — a silent gap. A resilient approach uses an outbox pattern: write the audit event to a `pending_audit` queue table in the same DB transaction as the business operation, then have a background worker drain it to the `audit_logs` table (or ship to a dedicated log store like ELK). This guarantees at-least-once delivery without coupling audit to the request latency.

---

**Q3. Passwords for seeded/legacy users are stored in plaintext. The `_verify()` function falls back to plaintext comparison. How do you migrate those users to bcrypt without forcing them all to reset?**

*Expected answer:* Use a lazy migration: when a plaintext password matches, immediately re-hash it with bcrypt and persist the hash, then remove the plaintext. On the next login, the bcrypt path is taken. This is transparent to users and completes the migration organically over time. A deadline can be enforced by setting `must_change_password = True` for any account still holding a plaintext password after a cutoff date.

---

**Q4. `Patient.doctor` is stored as a plain string (no FK). What happens to all patient records if a doctor's name is corrected (typo fix) in the `doctors` table?**

*Expected answer:* Nothing automatically — patient records still hold the old name string. Queries that join `Doctor.name == Patient.doctor` will stop matching those patients. A correction requires an explicit bulk `UPDATE patients SET doctor = 'New Name' WHERE doctor = 'Old Name'`. This is the core risk of the soft-FK pattern. The fix is a proper FK with `ON UPDATE CASCADE`, or using `doctor_id` instead of `doctor` name.

---

**Q5. The `medications` column in `prescriptions` stores a JSON array as a text string. What are the risks and what would a production-grade schema look like?**

*Expected answer:* Risks: no DB-level validation of the JSON structure, no ability to query individual medications efficiently (e.g., "how many patients were prescribed Drug X"), and `json.loads()` can raise exceptions if data is corrupt. Production schema: a separate `prescription_items` table with columns `(prescription_id, medication_id, dosage, frequency, duration)`. This enables medication analytics, drug interaction audits, and referential integrity. The prescription-as-snapshot argument is valid but better served by a separate `snapshot_medications` TEXT column alongside the normalized form.

---

**Q6. The analytics endpoints compute stats on-the-fly using SQLAlchemy queries against the operational database. At what patient volume does this become a problem, and what's your scaling strategy?**

*Expected answer:* At roughly 50,000+ patient records, aggregation queries (GROUP BY, COUNT, date range scans) start impacting response time and competing with write transactions. The strategy: (1) add indexes on frequently filtered columns (`consultation_date`, `status`, `doctor`); (2) pre-compute rolling aggregates via a scheduled job into a `daily_stats` materialized table; (3) for real-time dashboards, use PostgreSQL's materialized views refreshed every 5 minutes; (4) at very high scale, separate the OLAP (analytics) workload onto a read replica.

---

**Q7. There is no rate limiting or brute-force protection on `POST /auth/login`. How would you add it, and what would you throttle on?**

*Expected answer:* Add rate limiting per IP address using a middleware layer (FastAPI's `slowapi` library wrapping `limits`). Throttle on: (a) IP address — max 10 attempts/minute; (b) email address — max 5 failures before temporary lock (store failure count in Redis with TTL). After 5 failures for an email, return HTTP 429 with `Retry-After` header. Log each throttle trigger to audit logs. Add CAPTCHA on the frontend after 3 failures.

---

**Q8. The `lifespan()` function runs `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` on every application startup. What are the risks of this approach in a multi-instance deployment?**

*Expected answer:* In a single instance, it's safe and elegant. In a multi-instance setup (e.g., 3 replicas behind a load balancer), all instances execute the migration simultaneously on startup — PostgreSQL's DDL locks the table briefly, and all three instances compete. `ADD COLUMN IF NOT EXISTS` is idempotent so data is safe, but there's a brief table lock per `ALTER`. The fix: use a proper migration tool (Alembic) with a migration lock (advisory lock on a migrations table), run migrations as a pre-deploy step (not in the app process), and use `--check` mode in CI.

---

**Q9. Email sending happens synchronously inside the request handler. A slow SMTP server causes a 5-second timeout on user creation. How do you fix this without adding infrastructure?**

*Expected answer:* Without a task queue, use Python's `concurrent.futures.ThreadPoolExecutor` to fire the email in a background thread (fire-and-forget). FastAPI supports `BackgroundTasks` natively — inject `background_tasks: BackgroundTasks` into the route and call `background_tasks.add_task(email_service.send_welcome_email, ...)`. This returns the HTTP response immediately and sends the email after the response is sent. The trade-off: if the server crashes after the response, the email is lost (at-most-once delivery).

---

**Q10. The application uses `sessionStorage` on the frontend for authentication state, and there is no token expiry or session invalidation mechanism. What are the security implications, and how would you improve this for a healthcare setting?**

*Expected answer:* `sessionStorage` is cleared on tab close but not on inactivity. A malicious actor with physical access to an unattended workstation can use the open tab indefinitely. In a healthcare setting (HIPAA/DPDP compliance requirements), this is a critical gap. Improvements: (1) Issue short-lived JWTs (15-min expiry) with refresh tokens; (2) Add an inactivity timeout on the frontend (detect mouse/keyboard events, auto-logout after 5 minutes idle); (3) Maintain a server-side session blacklist so admins can invalidate active sessions when they disable an account (currently, a deactivated user's open session persists until browser close); (4) Log all session activity via audit logs; (5) Enforce HTTPS to prevent header sniffing.
