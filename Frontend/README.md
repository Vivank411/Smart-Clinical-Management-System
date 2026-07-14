# MedClinic — Frontend

> **Angular 19 + PrimeNG + SCSS**
> Single-Page Application for a hospital outpatient management system serving three user roles: Receptionist, Doctor/Junior Doctor, and Admin.

---

## Table of Contents

1. [Technology Stack](#1-technology-stack)
2. [Architecture Overview](#2-architecture-overview)
3. [Project File Map](#3-project-file-map)
   - 3.1 Core Configuration
   - 3.2 Services
   - 3.3 Guards & Interceptors
   - 3.4 Layouts
   - 3.5 Pages (Components)
4. [Routing & Role-Based Navigation](#4-routing--role-based-navigation)
5. [Authentication Flow](#5-authentication-flow)
6. [Feature Deep-Dives](#6-feature-deep-dives)
   - 6.1 Login with Autocomplete
   - 6.2 Force-Change Password
   - 6.3 Patient Registration & Duplicate Detection
   - 6.4 Patient Search & Filtering
   - 6.5 Patient Check-In & Queue Token
   - 6.6 Doctor Queue & Consultation
   - 6.7 E-Prescription
   - 6.8 Admin Dashboard
   - 6.9 Admin User Management
   - 6.10 Admin Doctor Management
   - 6.11 Admin Reports & Analytics
   - 6.12 Audit Log Viewer
7. [Key Concepts & Patterns Used](#7-key-concepts--patterns-used)
8. [Frontend ↔ Backend Connection Map](#8-frontend--backend-connection-map)
9. [Environment & Configuration](#9-environment--configuration)
10. [CTO-Level Interview Questions](#10-cto-level-interview-questions)

---

## 1. Technology Stack

| Layer | Technology | Version | Why |
|---|---|---|---|
| Framework | **Angular** | 19 | Component-based SPA, standalone components, signals-ready |
| UI Library | **PrimeNG** | 17+ | Production-grade component set (AutoComplete, dialogs, icons) |
| Styling | **SCSS** | — | BEM-like scoped styles, CSS variables, media queries |
| HTTP | **Angular HttpClient** | — | Observable-based, interceptor pipeline, typed responses |
| Forms | **Angular FormsModule (ngModel)** | — | Two-way binding for rapid form development |
| Icons | **PrimeIcons** | — | Consistent icon set via `pi pi-*` classes |
| Charts | **Custom SVG** | — | Zero-dependency; polylines, circles, donut arcs drawn in template |
| Build | **Angular CLI + esbuild** | — | Fast incremental builds, tree-shaking |
| Language | **TypeScript** | 5.x | Type safety across all service interfaces and component state |

---

## 2. Architecture Overview

```
Browser
  │
  └── Angular SPA (index.html)
        │
        ├── app.config.ts          ← Providers: HttpClient, Router, PrimeNG
        ├── app.routes.ts          ← Route definitions with lazy loading + authGuard
        │
        ├── layout/
        │   ├── main-layout/       ← Shell for authenticated pages (sidebar + topbar)
        │   ├── sidebar/           ← Role-aware navigation links
        │   └── topbar/            ← User info, logout
        │
        ├── pages/                 ← 21 feature pages (standalone components)
        │
        ├── services/
        │   ├── api.service.ts     ← All HTTP calls to FastAPI backend (44+ methods)
        │   ├── auth.service.ts    ← Session state: login/logout/role/homeRoute
        │   └── config.service.ts  ← Loads config.json (API base URL)
        │
        ├── guards/
        │   └── auth.guard.ts      ← Blocks unauthenticated route access
        │
        └── interceptors/
            └── auth-header.interceptor.ts  ← Injects X-User-Name/X-User-Email headers
```

**Data flow pattern:**
```
Page Component
  → calls ApiService method (returns Observable)
  → HttpClient sends request
  → authHeaderInterceptor adds user identity headers
  → FastAPI backend responds
  → Component subscribes and updates local state
  → Template re-renders via Angular change detection
```

---

## 3. Project File Map

### 3.1 Core Configuration

#### `app.config.ts`
The Angular application configuration file (replaces the old `AppModule`). Registers:
- `provideRouter(routes)` — enables the routing table
- `provideHttpClient(withInterceptors([authHeaderInterceptor]))` — HTTP client with the custom interceptor pipeline
- `provideAnimationsAsync()` — PrimeNG animation support
- `providePrimeNG(...)` — PrimeNG theme configuration

**Why standalone providers?** Angular 14+ promotes the standalone component model — no `NgModule` wrappers needed. `app.config.ts` is the single place to configure all global providers, making the bootstrap chain explicit and testable.

---

#### `app.routes.ts`
Defines all client-side routes. Every protected route uses:
```typescript
canActivate: [authGuard]
```
Routes use `loadComponent` for lazy loading — the browser only downloads a page's JavaScript bundle when that route is first visited, not on initial load. This reduces the initial bundle size and speeds up the first paint.

---

#### `src/assets/config.json`
```json
{ "apiUrl": "http://localhost:8000" }
```
Loaded by `ConfigService` at startup via `APP_INITIALIZER`. Decouples the API URL from the compiled bundle — the same build artifact can point to dev, staging, or production backends by swapping only this file, with no recompilation.

---

### 3.2 Services

#### `config.service.ts`
Reads `assets/config.json` once on app start. Provides `apiUrl` as a string property used by `ApiService` as `this.config.apiUrl`. The `APP_INITIALIZER` token ensures config is fully loaded before any component renders — no race condition where a component tries to call an API before the URL is known.

---

#### `auth.service.ts`
Central authentication state manager. Uses `sessionStorage` (automatically cleared when the browser tab is closed).

**Key methods:**
```typescript
setUser(user)     // Save user object after successful login
getUser()         // Read current user — used by interceptor and components
isLoggedIn()      // Boolean check — used by authGuard
logout()          // Clears sessionStorage, redirects to /login
get homeRoute()   // Returns role-specific landing page:
                  //   Admin        → /admin-dashboard
                  //   Doctor       → /doctor-dashboard
                  //   Junior Doctor → /doctor-dashboard
                  //   Receptionist → /dashboard
```

Role detection properties (`isAdmin`, `isDoctor`, `isReceptionist`) are read by the sidebar to conditionally show/hide navigation sections per role.

---

#### `api.service.ts`
The single HTTP client for all 44+ backend calls. Every method:
- Constructs `HttpParams` for query string parameters
- Returns a typed `Observable<T>`
- Is injected into components via Angular DI (`constructor(private api: ApiService)`)

All TypeScript interfaces for request/response shapes are defined in this file (mirroring the backend Pydantic schemas):
`ApiPatient`, `ApiDoctor`, `AdminDoctorCreate`, `AuditLogFull`, `WeeklySummary`, and 30+ others.

**Why one service for everything?** Centralizes API base URL, gives a single place to add global error handling, and keeps all type definitions in one discoverable location. Components never know the HTTP transport — they only subscribe to Observables.

---

### 3.3 Guards & Interceptors

#### `guards/auth.guard.ts`
A `CanActivateFn` (functional guard, Angular 15+) that checks `AuthService.isLoggedIn()`. If false, redirects to `/login` and returns `false`. Applied to every route except `/login` and `/change-password`.

```typescript
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  return auth.isLoggedIn() ? true : inject(Router).createUrlTree(['/login']);
};
```

**Why functional instead of class-based?** No `@Injectable()` boilerplate, no class to instantiate. `inject()` provides DI inside the function body. Registered directly in the route definition — no separate `providers` array needed.

---

#### `interceptors/auth-header.interceptor.ts`
An `HttpInterceptorFn` (functional interceptor) that reads the current user from `AuthService` and clones every outgoing HTTP request to add two custom headers:

```
X-User-Name:  "Dr. Sarah Khan"
X-User-Email: "sarah.khan@clinic.com"
```

The backend's `log_audit()` function reads these headers to attribute every database mutation to the performing user. This is completely transparent to all components — no component ever passes user identity manually.

```typescript
export const authHeaderInterceptor: HttpInterceptorFn = (req, next) => {
  const user = inject(AuthService).getUser();
  if (user) {
    req = req.clone({ setHeaders: {
      'X-User-Name':  user.name,
      'X-User-Email': user.email,
    }});
  }
  return next(req);
};
```

**Why clone the request?** HTTP requests in Angular are immutable. `.clone()` creates a new request object with the added headers while preserving all other properties (method, URL, body, existing headers).

---

### 3.4 Layouts

#### `layout/main-layout/`
The shell component rendered for all authenticated routes. Uses Angular's `<router-outlet>` to project the active page inside a persistent layout. The sidebar and topbar are never destroyed on navigation — only the content inside `<router-outlet>` changes. This prevents flickering and preserves sidebar scroll position across page transitions.

#### `layout/sidebar/`
Displays role-filtered navigation links. Reads `AuthService.isAdmin`, `isDoctor`, `isReceptionist` to conditionally show sections using `@if`. Uses PrimeIcons for link icons and `routerLinkActive` to apply an active-link highlight class to the current page.

#### `layout/topbar/`
Shows the current user's name and role from `AuthService.getUser()`. Provides a logout button that calls `AuthService.logout()`.

---

### 3.5 Pages (Components)

#### `pages/login/`
**Purpose:** Authenticate any user type (Doctor, Receptionist, Admin).

**What's inside:**
- PrimeNG `AutoComplete` bound to `selectedPerson` — suggests users matching typed text.
- On selection, `password` field activates.
- `onLogin()` calls `api.login()`, receives role in response, calls `auth.setUser()`, then navigates to `auth.homeRoute`.
- Error message (`this.error`) displays `err.error?.detail` from the backend (e.g., "Your account has been deactivated. Please contact the administrator.").
- Password show/hide toggle via `showPw` boolean and `[type]` binding.

---

#### `pages/change-password/`
**Purpose:** Forced on first login if `mustChangePassword` is true in the login response.

**What's inside:**
- Form: current password, new password, confirm password.
- Validates: new ≠ current, new === confirm, minimum length.
- On success, calls `api.changePassword()`, updates sessionStorage to clear `mustChangePassword`, redirects to home.

---

#### `pages/dashboard/`
**Purpose:** Receptionist home screen — live queue overview.

**What's inside:**
- Calls `api.getDashboardStats()` for real-time counts: total patients, checked-in, in-consultation, completed, doctors on duty.
- Displays five status cards with color-coded icons.

---

#### `pages/patient-registration/`
**Purpose:** Register a new patient into the system.

**What's inside:**
- Multi-field form: name, DOB, gender, age, mobile, ID proof type/number, insurance company.
- **Inline duplicate check:** `api.checkDuplicate()` fires on mobile `blur` — shows a warning banner if a duplicate mobile or name+DOB is found.
- **Age auto-calculation:** when DOB is entered, `age` is computed and pre-filled.
- `allowDuplicateMobile` checkbox unlocks submission if the receptionist confirms intentional registration.
- Insurance company dropdown populated from `api.getInsuranceCompanies()`.
- `api.createPatient()` submits; success shows the generated `MED-XXXX` patient ID.

---

#### `pages/search-patient/`
**Purpose:** Find and view existing patients.

**What's inside:**
- Search input calls `api.getPatients({search})`.
- Status filter dropdown re-fetches on change.
- Results table with click-to-expand detail panel.
- Shows full patient profile: demographics, clinical notes, doctor assignment, insurance.

---

#### `pages/check-in/`
**Purpose:** Process patient arrival — assign queue token and mark as Checked-In.

**What's inside:**
- Loads patients with `status=Registered`.
- Receptionist selects patient, selects doctor, enters reason for visit.
- Generates queue token: `{SPECIALIZATION_PREFIX}-{counter}` (e.g., `CARD-003`).
- Records `checkin_time` as current time string (`HH:MM AM/PM`).
- Calls `api.updatePatient()` with `{status: "Checked-In", queueToken, checkinTime, doctor, reasonForVisit}`.

---

#### `pages/doctor-dashboard/`
**Purpose:** Doctor/Junior Doctor home screen showing summary of assigned patients.

**What's inside:**
- Reads logged-in doctor name from `AuthService`.
- Calls `api.getPatients({doctor: name})` to show patient counts by status.

---

#### `pages/doctor-queue/`
**Purpose:** Doctor views and manages their live patient queue.

**What's inside:**
- Loads patients filtered by `doctor = currentUser.name` and `status = Checked-In`.
- Shows queue position, patient name, chief complaint, check-in time.
- "Start Consultation" button navigates to `/doctor-consultation/:patientId`.
- Updates patient status to "In-Consultation" via `api.updatePatient()`.

---

#### `pages/consultation/`
**Purpose:** Doctor records the consultation for a patient.

**What's inside:**
- Loads patient details via `api.getPatient(id)` from the route param (read via `ActivatedRoute`).
- Chief complaint form field.
- Calls `api.createConsultation()` — records complaint and today's date.
- Updates patient status to "Completed" or remains "In-Consultation".
- Navigation shortcut to e-prescription.

---

#### `pages/doctor-eprescription/`
**Purpose:** Generate and save an electronic prescription.

**What's inside:**
- Medication search: `api.getMedications({search})` with live suggestions.
- Add medication rows: each row has `{name, dosage, frequency, duration}`.
- Remove individual rows.
- Calls `api.createPrescription()` with the full medication array.
- Updates patient status to "Completed" via `api.updatePatient()`.

---

#### `pages/doctor-patient-records/`
**Purpose:** View a patient's full clinical history.

**What's inside:**
- Patient search or selection.
- `forkJoin` fires two parallel calls: `api.getPatientConsultations()` + `api.getPatientPrescriptions()`.
- Timeline view of consultations with date, complaint, and doctor name.
- Prescription history with expandable medication lists.

---

#### `pages/admin-dashboard/`
**Purpose:** Admin overview of the entire system.

**What's inside:**
- Five KPI cards loaded from `api.getAdminStats()`.
- Patient flow bar chart (7-day) from `api.getPatientFlow()`.
- Consultation status donut chart from `api.getConsultationStats()`.
- Doctor workload horizontal bars from `api.getDoctorWorkload()`.
- Recent audit log activity feed from `api.getAuditLogs()`.

---

#### `pages/admin-users/`
**Purpose:** Manage all user accounts (Doctors, Receptionists, Admins) in one unified place.

**What's inside:**
- Merged user list from `api.getAdminUsers()` showing role, status, email.
- Filter tabs: All / Doctor / Junior Doctor / Receptionist / Admin.
- Search by name or email.
- **Create User modal:** name, email, phone, role, specialization.
- **Edit User modal:** update name, email, phone, specialization.
- **Toggle status:** enable/disable with visual confirmation.
- **Reset password:** generates temp password and emails it.
- **Delete user:** with confirmation dialog.

---

#### `pages/admin-doctors/`
**Purpose:** Manage doctor profiles with clinical-specific attributes.

**What's inside:**
- Doctor table: name, specialization, status badge, available time slot (from DB).
- Click-to-expand detail panel: identity, contact info, availability, action buttons.
- **Add Doctor modal:** name, specialization, role, email, phone, `Available From` / `Available To` time selects (06:00 AM → 09:00 PM, 1-hour steps).
- **Edit Doctor modal:** same fields, pre-filled from current data.
- Toggle active/inactive status.
- "Manage Availability" button opens the Edit modal directly.
- Avatar initials and background color auto-generated from doctor name.

---

#### `pages/admin-reports/`
**Purpose:** Full analytics dashboard with date-range filtering and multi-format export.

**What's inside:**
- Date range selector: Last 7 / 14 / 30 Days.
- **Patient Flow chart:** custom SVG polyline with gradient fill and hover dot tooltips.
- **Waiting Time chart:** SVG line chart with dynamic Y-axis scaling.
- **Department Distribution:** donut chart built from SVG `stroke-dasharray` arcs.
- **Peak Hours bar chart:** 2-hour time buckets (6AM–10PM).
- **Weekly Summary cards:** 4 KPIs with trend arrows (up/down/neutral) and color coding.
- Export: CSV (Blob), Excel (TSV Blob with `.xls`), PDF (`window.print()` with `@media print`).
- All 5 data sources load in parallel via `forkJoin` on init and on range change.

---

#### `pages/admin-audit/`
**Purpose:** Compliance-ready audit log viewer.

**What's inside:**
- Table: timestamp, user, action, module, details, IP, status badge.
- Search bar (filters by user name, email, action, details — server-side).
- Filter dropdowns: Module, Action Type, Status.
- Server-side pagination (`page`, `page_size` sent to API).
- "Clear filters" resets all state.
- No create/edit/delete controls — read-only by design.
- Status badges: green `Success`, red `Failed`.

---

#### `pages/admin-settings/`
**Purpose:** Placeholder for system configuration (clinic name, operating hours, notifications).
Currently renders static UI; settings persistence is a planned backend enhancement.

---

## 4. Routing & Role-Based Navigation

```
/                           → redirect to /login
/login                      → LoginComponent (public)
/change-password            → ChangePasswordComponent (public)

Protected routes (authGuard blocks unauthenticated access):
/dashboard                  → DashboardComponent           [Receptionist]
/patient-registration       → PatientRegistrationComponent  [Receptionist]
/search-patient             → SearchPatientComponent        [Receptionist]
/check-in                   → CheckInComponent              [Receptionist]
/doctor-dashboard           → DoctorDashboardComponent      [Doctor / Junior Doctor]
/doctor-queue               → DoctorQueueComponent          [Doctor / Junior Doctor]
/doctor-consultation/:id    → ConsultationComponent         [Doctor / Junior Doctor]
/doctor-eprescription       → DoctorEprescriptionComponent  [Doctor / Junior Doctor]
/doctor-patient-records     → DoctorPatientRecordsComponent [Doctor / Junior Doctor]
/admin-dashboard            → AdminDashboardComponent       [Admin]
/admin-users                → AdminUsersComponent           [Admin]
/admin-doctors              → AdminDoctorsComponent         [Admin]
/admin-reports              → AdminReportsComponent         [Admin]
/admin-audit                → AdminAuditComponent           [Admin]
/admin-settings             → AdminSettingsComponent        [Admin]
/**                         → redirect to /login
```

**Role routing logic:** `AuthService.homeRoute` returns the correct landing page after login. The sidebar only renders links relevant to the current user's role. The `authGuard` checks only "is logged in" — full role-to-route enforcement is a planned enhancement (see Q2 in interview section).

---

## 5. Authentication Flow

```
1. User visits any URL
   └── authGuard checks sessionStorage
       ├── Not logged in → redirect to /login
       └── Logged in     → show requested page

2. On /login:
   a. getAuthUsers(role) → populates AutoComplete
   b. User selects name, enters password
   c. login() → backend returns { role, name, email, mustChangePassword }
   d. If account deactivated → backend returns 403, error message shown
   e. auth.setUser() → saves to sessionStorage
   f. mustChangePassword = true  → navigate to /change-password
      mustChangePassword = false → navigate to auth.homeRoute

3. On /change-password:
   a. changePassword() → backend hashes and stores new password
   b. auth.setUser(updated) → clears mustChangePassword flag in sessionStorage
   c. navigate to auth.homeRoute

4. On logout:
   a. auth.logout() → clears sessionStorage
   b. navigate to /login

5. On every HTTP request (via interceptor — transparent to all components):
   → Headers: X-User-Name, X-User-Email
   → Backend uses these for audit log attribution
```

---

## 6. Feature Deep-Dives

### 6.1 Login with Autocomplete

**Use case:** The receptionist doesn't need to remember email addresses — they type the first few letters of a name and get suggestions.

**How it works:**
- `api.getAuthUsers(role)` fetches all users for the selected role tab.
- PrimeNG `AutoComplete` filters locally against the fetched list.
- On selection, email is read from the selected `AuthUser` object.
- Password field uses `[type]="showPw ? 'text' : 'password'"` for show/hide toggle.
- Error `this.error` binds to `err.error?.detail` — backend error messages render directly.

**Technologies:** PrimeNG AutoComplete, `[(ngModel)]`, `HttpClient`.

---

### 6.2 Force-Change Password

**Use case:** On user creation, admin sets a temporary password. The user must change it before accessing any feature.

**How it works:**
- `LoginResponse.mustChangePassword` flag from backend drives the post-login redirect.
- `auth.setUser()` stores the flag; all subsequent route checks see it.
- On successful change, `mustChangePassword` is cleared from the stored user object.

**Technologies:** `Router.navigate()`, `sessionStorage`, `FormsModule`.

---

### 6.3 Patient Registration & Duplicate Detection

**Use case:** Prevent duplicate patient records for the same person in a busy reception environment.

**How it works:**
- On mobile field `(blur)`: `api.checkDuplicate(name, dob, mobile)` fires.
- Response includes `nameDobExists` and `mobileExists` flags with the matching patient's details.
- Warning banner shows the existing patient's name + ID so the receptionist can verify.
- `allowDuplicateMobile = true` checkbox overrides the mobile check (for family members sharing a number).
- Age auto-calculated: `new Date().getFullYear() - new Date(dob).getFullYear()` with birthday adjustment.

**Technologies:** `(blur)` event binding, `HttpParams`, `@if` conditional rendering.

---

### 6.4 Patient Search & Filtering

**Use case:** Receptionist quickly finds patients by name, ID number, or status.

**How it works:**
- `api.getPatients({search, status})` — both parameters sent to backend as query strings.
- Status filter dropdown re-calls on `(change)`.
- Results rendered with Angular 17+ `@for` control flow.

**Technologies:** `HttpParams`, Angular `@for`, `[(ngModel)]` on select.

---

### 6.5 Patient Check-In & Queue Token

**Use case:** Patient arrives at the clinic and gets a numbered position in a specific doctor's queue.

**How it works:**
- Queue token format: `{SPEC_PREFIX}-{counter}` — e.g., 3rd Cardiology patient gets `CARD-003`.
- Prefix: first 4 letters of specialization, uppercase.
- Counter increments per specialization per session (component memory).
- `checkin_time`: `new Date().toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit'})`.
- Sends `{status: "Checked-In", queueToken, checkinTime, doctor, reasonForVisit}` via `PUT /patients/{id}`.

**Technologies:** String slicing, `Date` API, `PUT` HTTP call.

---

### 6.6 Doctor Queue & Consultation

**Use case:** Doctor sees only their own patients, in check-in order, and moves each through the consultation workflow.

**How it works:**
- `api.getPatients({doctor: currentUserName, status: 'Checked-In'})` scopes the queue.
- "Start Consultation" navigates to `/doctor-consultation/:id` with patient ID as a route param.
- `ConsultationComponent` reads `:id` via `ActivatedRoute.snapshot.paramMap.get('id')`.
- `api.createConsultation()` records the complaint; `api.updatePatient()` updates status.

**Technologies:** `ActivatedRoute`, route params, status-based API filtering.

---

### 6.7 E-Prescription

**Use case:** Doctor creates a medication plan for the patient at end of consultation.

**How it works:**
- Medication typeahead: `api.getMedications({search})` — fires on input.
- Selecting a drug pre-fills `dosage` from `MedicationResponse.defaultDosage`.
- Multiple rows: each is a `MedicationItem = {name, dosage, frequency, duration}` in an array.
- `api.createPrescription({patientId, medications, doctorName, notes})` sends the full array.

**Technologies:** Array mutation (`push`/`splice`), `@for` with index, `ngModel` binding on array items.

---

### 6.8 Admin Dashboard

**Use case:** Admin gets a real-time clinic-wide snapshot at a glance.

**How it works:**
- `forkJoin` fires 5 API calls simultaneously; all charts update together after all resolve.
- Bar chart: `height = (count / maxCount) * 100 + '%'` as inline style.
- Donut chart: `stroke-dasharray = "X Y"` where X = `(percentage / 100) * 2πr`.
- Audit feed: last 10 events sorted by newest first.

**Technologies:** `forkJoin`, RxJS, custom SVG, `[style.height]`, `stroke-dasharray`.

---

### 6.9 Admin User Management

**Use case:** Admin controls who can access the system, at what role, and can immediately revoke access.

**How it works:**
- All three user tables are merged by the backend into one list; each entry carries a `source` field (`"doctor"`, `"receptionist"`, `"admin"`).
- `source` is passed back on every mutating call so the backend knows which table to target.
- Toggle deactivates the account immediately — the next login attempt is blocked at the backend with HTTP 403.
- Reset password: backend generates a temp password, emails it, sets `mustChangePassword = true`.

**Technologies:** Discriminator field pattern, `PUT`/`DELETE` HTTP calls, conditional modal rendering.

---

### 6.10 Admin Doctor Management

**Use case:** Admin manages doctor profiles with clinic-specific attributes separate from generic user management.

**How it works:**
- `timeSlots` array (`['06:00 AM', '07:00 AM', ..., '09:00 PM']`) drives both `<select>` dropdowns in Add/Edit modals.
- `available_from`/`available_to` are included in create and update payloads, persisted to DB.
- Detail panel reads `selected.available_from ?? '09:00 AM'` — null-safe with defaults.
- Avatar color: `name.charCodeAt(0) % palette.length` — deterministic color from name hash.

**Technologies:** Array-driven selects, null coalescing (`??`), `stopPropagation()` for nested click handlers.

---

### 6.11 Admin Reports & Analytics

**Use case:** Admin tracks trends over time to make staffing and scheduling decisions.

**How it works:**
- Range change (`7`/`14`/`30`) triggers `onRangeChange()` → `load()` → new `forkJoin` with updated `days` param.
- **Line chart geometry:** `x = (i / (n-1)) * 700`, `y = 200 - (val / max) * 180` — normalized to SVG viewport.
- **Donut arcs:** `stroke-dasharray = "${pct * circumference / 100} ${circumference}"` per segment.
- **Export CSV:** `new Blob([csvString], {type: 'text/csv'})` → `URL.createObjectURL()` → auto-click hidden `<a>`.
- **Export Excel:** Same but `text/tab-separated-values` MIME type, `.xls` extension.
- **Export PDF:** `window.print()` with `@media print` CSS hiding sidebar, header, and controls.

**Technologies:** `forkJoin`, SVG geometry, `Blob`, `URL.createObjectURL()`, `window.print()`, CSS `@media print`.

---

### 6.12 Audit Log Viewer

**Use case:** Admin reviews who did what, when, and from where — for compliance, investigation, and accountability.

**How it works:**
- All filtering happens server-side — component sends `{page, page_size, search, module, action, status}` as query params.
- `api.getAuditLogsFull()` returns `{logs: AuditLogFull[], total: number}`.
- `[ngClass]` toggles `.badge--success` / `.badge--failed` based on `log.status`.
- Pagination: `currentPage` tracked in component; `(page - 1) * pageSize` offset computed server-side.
- No write operations in the UI — the table is intentionally read-only.

**Technologies:** Server-side pagination, `[ngClass]`, `HttpParams`, `@for` with `$index`.

---

## 7. Key Concepts & Patterns Used

### Standalone Components (Angular 14+)
Every component uses `standalone: true`. No `NgModule` is needed. Each component explicitly declares its own `imports: [CommonModule, FormsModule, ...]`. This enables tree-shaking at the component level, makes components independently testable, and eliminates the module hierarchy confusion common in older Angular apps.

### Angular 17+ Control Flow Syntax
```html
@if (loading) { <spinner/> }
@for (item of list; track item.id) { <row/> }
@else { <empty-state/> }
```
Replaces `*ngIf`, `*ngFor`, and `*ngSwitch` structural directives. The `track` expression (replacing `trackBy` functions) tells Angular which property uniquely identifies each item, enabling efficient DOM recycling during list updates.

### Functional Guards & Interceptors (Angular 15+)
Function-based (not class-based) guards and interceptors. `inject()` provides DI inside the function body. Registered in `app.config.ts` via `withInterceptors([...])`. Simpler than the class-based alternatives — no `@Injectable()`, no `implements HttpInterceptor`.

### forkJoin for Parallel API Calls
```typescript
forkJoin({
  flow:    this.api.getPatientFlow(days),
  wait:    this.api.getWaitingTime(days),
  dept:    this.api.getDepartmentStats(),
  peak:    this.api.getPeakHours(),
  summary: this.api.getWeeklySummary(),
}).subscribe(({ flow, wait, dept, peak, summary }) => { ... });
```
Fires all HTTP requests simultaneously. Waits for all to complete before updating the view. Total load time = slowest single request, not sum of all. Used in Admin Reports and Admin Dashboard.

### Observable-Based HTTP
All API calls return `Observable<T>`. Components subscribe in `ngOnInit()` or event handlers. No `async/await` is used — the RxJS Observable pattern integrates natively with Angular's change detection and enables RxJS operators (`switchMap`, `catchError`, `debounceTime`).

### `stopPropagation()` for Nested Click Handlers
In data tables with row-click and per-row action buttons, `$event.stopPropagation()` on button clicks prevents the row-click handler from also firing. Pattern used consistently in doctor table, user table, and check-in table.

### Zero-Dependency Chart Rendering
All charts are implemented with raw SVG in Angular templates. Avoids adding Chart.js, ngx-charts, or D3 (hundreds of KB each) to the bundle. Trade-off: more verbose template code, but full control over appearance and no version dependency risk.

### sessionStorage vs localStorage
`sessionStorage` is used intentionally — auth state is cleared when the browser tab is closed. This reduces risk on shared hospital workstations where the next staff member might use the same browser window without logging in.

### Role-Based UI Rendering (RBAC at Component Level)
```html
@if (auth.isAdmin) { <admin-nav-links/> }
@if (auth.isDoctor) { <doctor-nav-links/> }
```
Sidebar navigation links are conditionally rendered based on role. Each role sees only their relevant pages. This is complementary to backend access control.

---

## 8. Frontend ↔ Backend Connection Map

| User Action | Component Method | Service Call | Backend Endpoint | HTTP |
|---|---|---|---|---|
| Type name in login | `filterPersons()` | `api.getAuthUsers(role)` | `GET /auth/users` | GET |
| Click Login | `onLogin()` | `api.login()` | `POST /auth/login` | POST |
| Change password | `submit()` | `api.changePassword()` | `POST /auth/change-password` | POST |
| Type patient name (dupe check) | `checkDupe()` | `api.checkDuplicate()` | `GET /patients/check-duplicate` | GET |
| Register patient | `submitForm()` | `api.createPatient()` | `POST /patients` | POST |
| Search patients | `search()` | `api.getPatients()` | `GET /patients` | GET |
| Check in patient | `checkIn()` | `api.updatePatient()` | `PUT /patients/{id}` | PUT |
| View doctor queue | `ngOnInit()` | `api.getPatients()` | `GET /patients?doctor=X` | GET |
| Start consultation | `startConsult()` | `api.createConsultation()` | `POST /consultations` | POST |
| Search medication | `searchMed()` | `api.getMedications()` | `GET /medications` | GET |
| Save prescription | `submit()` | `api.createPrescription()` | `POST /prescriptions` | POST |
| View patient history | `ngOnInit()` | `forkJoin(consultations + prescriptions)` | `GET /consultations/patient/{id}` + `GET /prescriptions/patient/{id}` | GET |
| Admin: load dashboard | `ngOnInit()` | `api.getAdminStats()` | `GET /admin/stats` | GET |
| Admin: load reports | `load()` | `forkJoin(5 analytics calls)` | Multiple `GET /admin/*` | GET |
| Admin: create user | `submitAdd()` | `api.createAdminUser()` | `POST /admin/users` | POST |
| Admin: toggle user (re-enable emails a new temp password) | `toggleStatus()` | `api.toggleUserStatus()` | `PUT /admin/users/{source}/{id}/toggle` | PUT |
| Admin: delete user | `deleteUser()` | `api.deleteAdminUser()` | `DELETE /admin/users/{source}/{id}` | DELETE |
| Admin: add doctor | `submitAdd()` | `api.createAdminDoctor()` | `POST /admin/doctors` | POST |
| Admin: edit doctor | `submitEdit()` | `api.updateAdminDoctor()` | `PUT /admin/doctors/{id}` | PUT |
| Admin: view audit | `ngOnInit()` | `api.getAuditLogsFull()` | `GET /admin/audit-logs-full` | GET |
| Admin: filter audit | `applyFilter()` | `api.getAuditLogsFull()` | `GET /admin/audit-logs-full?module=X` | GET |
| Export CSV | `exportCSV()` | — (Blob download) | None (client-side) | — |
| Export PDF | `exportPDF()` | — (`window.print()`) | None (client-side) | — |

**Every request above automatically includes** `X-User-Name` and `X-User-Email` headers via `authHeaderInterceptor`, enabling full audit attribution on the backend without any component explicitly handling it.

---

## 9. Environment & Configuration

### `src/assets/config.json`
```json
{
  "apiUrl": "http://localhost:8000"
}
```
Change this file to point to staging or production without rebuilding the Angular app.

### Angular CLI Commands
```bash
# Start development server (hot reload at http://localhost:4200)
ng serve

# Production build (output to dist/)
ng build --configuration production

# TypeScript type check without building
npx tsc --noEmit

# Generate a new component
ng generate component pages/my-new-page --standalone
```

### Running the Full Stack
```bash
# Backend (from Backend/)
uvicorn main:app --reload --port 8000

# Frontend (from Frontend/)
ng serve
```

---

## 10. CTO-Level Interview Questions

> Acting as CTO — these are the questions you'd ask a frontend developer in a technical design review of this application.

---

**Q1. The application uses `sessionStorage` for auth state. A doctor leaves their workstation unlocked with the browser open. What happens, and how would you prevent unauthorized access?**

*Expected answer:* The session persists until the tab is closed. Another person can access all doctor functionality without logging in. Solution: implement an inactivity timeout — track `mousemove`, `keydown`, and `click` events using `fromEvent()` RxJS streams; if no event fires for 5 minutes, call `auth.logout()` and show a "Session expired" dialog. The hospital's OS-level screen lock policy is the first line of defense, but the app should not rely on it.

---

**Q2. The `authGuard` only checks whether a user is logged in. A receptionist can manually navigate to `/admin-dashboard` via the URL bar. What happens, and how do you fix it?**

*Expected answer:* They'll see the admin dashboard because `authGuard` only checks `isLoggedIn()`, not the role. Fix: extend `authGuard` to accept a `data.roles` array on the route definition (`data: { roles: ['Admin'] }`), then check `AuthService.getUser().role` against the allowed list inside the guard. Return `createUrlTree(['/dashboard'])` (the user's correct home) if the role doesn't match. This is the Angular-native RBAC pattern at the route level.

---

**Q3. All five analytics API calls in the Reports page fire inside `forkJoin`. If `getWaitingTime` is slow (2 seconds), the entire dashboard waits 2 seconds before rendering anything. How would you improve perceived performance?**

*Expected answer:* Replace `forkJoin` with individual subscriptions that update each chart section independently as data arrives. Use a loading skeleton (shimmer placeholder) per chart section so the user sees structure immediately. Charts render as soon as their individual data resolves rather than waiting for the slowest call. Alternatively, use `combineLatest` with `startWith(null)` per stream and show a per-section spinner.

---

**Q4. Medication search in the e-prescription fires an API call on every keystroke. With a fast typist, this generates 10 requests in under a second. What's the problem and how do you solve it?**

*Expected answer:* Race condition — responses arrive out of order, and the last displayed result may correspond to a stale query, not the latest keypress. Also wastes backend resources. Fix: pipe the input through an RxJS Subject with `debounceTime(300)`, `distinctUntilChanged()`, and `switchMap()`. `switchMap` automatically cancels the previous in-flight HTTP request when a new keystroke arrives. This is the canonical Angular typeahead pattern.

---

**Q5. The duplicate patient check fires on `(blur)` of the mobile field. What happens if the user fills in mobile last and immediately clicks Submit without moving focus first?**

*Expected answer:* The `blur` fires after the click event, but by then the submit handler may already be in flight — or the `allowDuplicateMobile` flag hasn't been evaluated. Fix: always run a final duplicate check inside the submit handler before calling `createPatient()`. Chain with `switchMap`: `checkDuplicate(...).pipe(switchMap(result => { if (result.mobileExists && !this.allowDuplicate) throw error; return this.api.createPatient(...); }))`. The `blur` check is UX sugar; the submit-time check is the real gate.

---

**Q6. The audit log page sends all filter parameters on every keystroke of the search input. How would you optimize this without changing the backend?**

*Expected answer:* Add `debounceTime(400)` + `distinctUntilChanged()` to the search input stream using an RxJS Subject. Only fire the API call after the user has stopped typing for 400ms and the value has actually changed. This reduces API calls from ~10/second (fast typist) to ~1 per search term. Combined with `switchMap`, it also cancels in-flight requests that are now stale.

---

**Q7. The CSV export builds a string from the currently loaded page data. If the admin wants to export all 30 days of patient flow but the report shows only the last 10 rows of audit logs — what would the export contain, and how do you fix it?**

*Expected answer:* The export contains only the currently visible component state — the in-memory data already loaded, not all records. Fix for complete export: (a) add a backend `GET /admin/audit-logs-full/export` endpoint that returns a `StreamingResponse` CSV with `Content-Disposition: attachment` — the browser downloads it directly; or (b) before generating the CSV, call the API once more with `page_size=10000` to fetch all records, then build the CSV. Option (a) is preferable for large datasets because it avoids loading thousands of rows into browser memory.

---

**Q8. Queue tokens are generated in component memory (`CARD-001`, `CARD-002`, …). If two receptionists work simultaneously on different computers, what happens?**

*Expected answer:* Both components maintain independent counters. Receptionist A and Receptionist B could both assign `CARD-003` to different patients. Fix: move token generation to the backend. The `PUT /patients/{id}` check-in endpoint queries `MAX(queue_token)` for that doctor today, increments it, and returns the generated token in the response. The frontend sends the assignment data and displays the token it receives — it never generates one. This guarantees uniqueness across multiple workstations.

---

**Q9. The application has no global HTTP error handling. A network outage shows a spinning loader forever. How do you add centralized error handling without modifying every component?**

*Expected answer:* Add a second `HttpInterceptorFn` that wraps `next(req)` in `catchError()`. For 401 responses, auto-redirect to `/login` and clear the session. For 403 responses, show a "Permission denied" toast. For 5xx responses, show a "Server error — try again" notification. For network errors (no response), show "No connection." Register this interceptor alongside `authHeaderInterceptor` in `app.config.ts`. Components don't need to handle these cases individually.

---

**Q10. The entire application is a Single-Page Application with no server-side rendering. What are the SEO and first-paint performance implications, and when would you introduce Angular Universal (SSR)?**

*Expected answer:* For a hospital internal tool, SEO is irrelevant — it's not publicly indexed. First-paint performance: the browser must download `main.js`, parse it, bootstrap Angular, then make API calls before anything useful renders (typically 1–3 seconds on a fast connection, longer on hospital Wi-Fi). For this use case, the trade-off is acceptable. Angular Universal (SSR) would be warranted if: (a) the app is publicly accessible and SEO matters, or (b) the hospital has slow internal network where initial JS parse time is a problem. The immediate improvement without SSR: enable route-level lazy loading (already in use), add `preconnect` hints to the API origin in `index.html`, and serve the Angular app with `brotli` compression.
