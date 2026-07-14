import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ConfigService } from './config.service';

// ── Shared API types (mirror the backend schemas) ──────────────────────────────

export interface ApiPatient {
  id: number;
  patientId: string;
  name: string;
  gender: string;
  dob: string;
  age: number;
  mobileNumber: string | null;
  insuranceCompany: string | null;
  addressLine1: string | null;
  addressLine2: string | null;
  city: string | null;
  pinCode: string | null;
  status: string;
  doctor: string | null;
  medicalHistory: string | null;
  allergies: string | null;
  reasonForVisit: string | null;
  queueToken: string | null;
  checkinTime: string | null;
  idProofType: string | null;
  idProofNumber: string | null;
}

export interface PatientCreate {
  firstName: string;
  lastName: string;
  gender: string;
  dob: string;
  age: number;
  mobileNumber: string;
  insuranceCompany?: string;
  medicalHistory?: string;
  allergies?: string;
  allowDuplicateMobile?: boolean;
  idProofType?: string;
  idProofNumber?: string;
}

export interface DuplicateCheckResult {
  nameDobExists: boolean;
  nameDobPatientId: string | null;
  mobileExists: boolean;
  mobilePatientName: string | null;
  mobilePatientId: string | null;
}

export interface PatientUpdate {
  name?: string;
  gender?: string;
  dob?: string;
  age?: number;
  insuranceCompany?: string;
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  pinCode?: string;
  status?: string;
  doctor?: string;
  medicalHistory?: string;
  allergies?: string;
  reasonForVisit?: string;
  queueToken?: string;
}

export interface ApiDoctor {
  id: number;
  name: string;
  specialization: string;
  phone: string | null;
  email: string | null;
  role: string;
  is_active: boolean;
  available_from?: string | null;
  available_to?: string | null;
}

export interface ApiInsuranceCompany {
  id: number;
  name: string;
  contactNumber: string | null;
  email: string | null;
}

export interface DashboardStats {
  totalPatients: number;
  checkedIn: number;
  inConsultation: number;
  completed: number;
  doctorsOnDuty: number;
}

export interface ConsultationCreate {
  patientId: number;
  chiefComplaint: string;
  doctorName?: string;
}

export interface ConsultationResponse {
  id: number;
  patientId: number;
  chiefComplaint: string;
  consultationDate: string;
  doctorName: string | null;
}

export interface MedicationItem {
  name: string;
  dosage: string;
  frequency: string;
  duration?: string;
}

export interface PrescriptionCreate {
  patientId: number;
  medications: MedicationItem[];
  doctorName?: string;
  notes?: string;
}

export interface PrescriptionResponse {
  id: number;
  patientId: number;
  medications: MedicationItem[];
  doctorName: string | null;
  prescriptionDate: string;
  notes: string | null;
}

export interface MedicationResponse {
  id: number;
  name: string;
  category: string | null;
  defaultDosage: string | null;
}

export interface ApiReceptionist {
  id: number;
  name: string;
  email: string;
}

export interface AdminStats {
  totalUsers: number;
  activeDoctors: number;
  totalPatients: number;
  avgWaitingTime: number;
  consultationsTotal: number;
}

export interface PatientFlowDay {
  day: string;
  count: number;
}

export interface ConsultationStat {
  label: string;
  count: number;
  percentage: number;
}

export interface DoctorWorkloadItem {
  name: string;
  count: number;
  maxCount: number;
}

export interface AuditLogItem {
  time: string;
  user: string;
  action: string;
  module: string;
  details: string;
}

export interface AdminUserItem {
  id: number;
  name: string;
  email: string;
  role: string;
  isActive: boolean;
  source: string;
  specialization?: string;
  phone?: string;
}

export interface AdminUserCreate {
  firstName: string;
  lastName: string;
  email: string;
  phone?: string;
  role: string;
  specialization?: string;
  sendWelcomeEmail?: boolean;
}

export interface TempPasswordResponse {
  tempPassword: string;
  userId: number;
  source: string;
}

export interface DoctorStats {
  total: number;
  active: number;
  inactive: number;
  specializations: number;
}

export interface AdminDoctorCreate {
  name: string;
  specialization: string;
  email?: string;
  phone?: string;
  role?: string;
  available_from?: string;
  available_to?: string;
}

export interface DoctorUpdate {
  name?: string;
  specialization?: string;
  email?: string;
  phone?: string;
  role?: string;
  available_from?: string;
  available_to?: string;
}

export interface WaitingTimeDay { day: string; mins: number; }
export interface DepartmentStat { department: string; count: number; percentage: number; }
export interface PeakHour { hour: string; mins: number; }
export interface WeeklySummary {
  totalPatients: number; totalConsultations: number;
  avgWaitingTime: number; cancelledConsultations: number;
  patientsChange: number; consultationsChange: number;
  waitingTimeChange: number; cancelledChange: number;
}
export interface AuditLogFull {
  id: number; time: string; user: string; userEmail: string;
  action: string; module: string; details: string;
  ipAddress: string; status: string; actionType: string;
}
export interface AuditLogsResponse { logs: AuditLogFull[]; total: number; }

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  name: string;
  email: string;
  role: string;
  specialization?: string;
  mustChangePassword?: boolean;
}

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  password: string;
  role: string;
  specialization?: string;
}

// ── Service ────────────────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class ApiService {
  private get base(): string { return this.config.apiUrl; }

  constructor(private http: HttpClient, private config: ConfigService) {}

  // Patients
  createPatient(data: PatientCreate): Observable<ApiPatient> {
    return this.http.post<ApiPatient>(`${this.base}/patients`, data);
  }

  getPatientByIdProof(idProofType: string, idProofNumber: string): Observable<ApiPatient> {
    let p = new HttpParams().set('id_proof_type', idProofType).set('id_proof_number', idProofNumber);
    return this.http.get<ApiPatient>(`${this.base}/patients/by-id-proof`, { params: p });
  }

  checkDuplicate(name: string, dob: string, mobile: string): Observable<DuplicateCheckResult> {
    let p = new HttpParams();
    if (name)   p = p.set('name', name);
    if (dob)    p = p.set('dob', dob);
    if (mobile) p = p.set('mobile', mobile);
    return this.http.get<DuplicateCheckResult>(`${this.base}/patients/check-duplicate`, { params: p });
  }

  getPatients(params?: {
    search?: string;
    status?: string;
    skip?: number;
    limit?: number;
    dob?: string;
    doctor?: string;
  }): Observable<ApiPatient[]> {
    let p = new HttpParams();
    if (params?.search) p = p.set('search', params.search);
    if (params?.status) p = p.set('status', params.status);
    if (params?.skip != null) p = p.set('skip', String(params.skip));
    if (params?.limit != null) p = p.set('limit', String(params.limit));
    if (params?.dob) p = p.set('dob', params.dob);
    if (params?.doctor) p = p.set('doctor', params.doctor);
    return this.http.get<ApiPatient[]>(`${this.base}/patients`, { params: p });
  }

  getPatient(id: number): Observable<ApiPatient> {
    return this.http.get<ApiPatient>(`${this.base}/patients/${id}`);
  }

  updatePatient(id: number, data: PatientUpdate): Observable<ApiPatient> {
    return this.http.put<ApiPatient>(`${this.base}/patients/${id}`, data);
  }

  // Doctors
  getDoctors(role?: string): Observable<ApiDoctor[]> {
    let p = new HttpParams();
    if (role) p = p.set('role', role);
    return this.http.get<ApiDoctor[]>(`${this.base}/doctors`, { params: p });
  }

  // Insurance Companies
  getInsuranceCompanies(): Observable<ApiInsuranceCompany[]> {
    return this.http.get<ApiInsuranceCompany[]>(`${this.base}/insurance-companies`);
  }

  // Dashboard
  getDashboardStats(): Observable<DashboardStats> {
    return this.http.get<DashboardStats>(`${this.base}/dashboard/stats`);
  }

  // Consultations
  createConsultation(data: ConsultationCreate): Observable<ConsultationResponse> {
    return this.http.post<ConsultationResponse>(`${this.base}/consultations`, data);
  }

  getPatientConsultations(patientId: number): Observable<ConsultationResponse[]> {
    return this.http.get<ConsultationResponse[]>(`${this.base}/consultations/patient/${patientId}`);
  }

  // Medications
  getMedications(search?: string): Observable<MedicationResponse[]> {
    let p = new HttpParams();
    if (search) p = p.set('search', search);
    return this.http.get<MedicationResponse[]>(`${this.base}/medications`, { params: p });
  }

  // Prescriptions
  createPrescription(data: PrescriptionCreate): Observable<PrescriptionResponse> {
    return this.http.post<PrescriptionResponse>(`${this.base}/prescriptions`, data);
  }

  getPatientPrescriptions(patientId: number): Observable<PrescriptionResponse[]> {
    return this.http.get<PrescriptionResponse[]>(`${this.base}/prescriptions/patient/${patientId}`);
  }

  // Auth
  login(data: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.base}/auth/login`, data);
  }

  changePassword(email: string, currentPassword: string, newPassword: string): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.base}/auth/change-password`, { email, currentPassword, newPassword });
  }

  getAuthUsers(role = ''): Observable<AuthUser[]> {
    const p = role ? new HttpParams().set('role', role) : new HttpParams();
    return this.http.get<AuthUser[]>(`${this.base}/auth/users`, { params: p });
  }

  // Receptionists
  getReceptionists(): Observable<ApiReceptionist[]> {
    return this.http.get<ApiReceptionist[]>(`${this.base}/receptionists`);
  }

  // Admin
  getAdminStats(): Observable<AdminStats> {
    return this.http.get<AdminStats>(`${this.base}/admin/stats`);
  }

  getPatientFlow(days = 7): Observable<PatientFlowDay[]> {
    const p = new HttpParams().set('days', String(days));
    return this.http.get<PatientFlowDay[]>(`${this.base}/admin/patient-flow`, { params: p });
  }

  getConsultationStats(): Observable<ConsultationStat[]> {
    return this.http.get<ConsultationStat[]>(`${this.base}/admin/consultation-stats`);
  }

  getDoctorWorkload(): Observable<DoctorWorkloadItem[]> {
    return this.http.get<DoctorWorkloadItem[]>(`${this.base}/admin/doctor-workload`);
  }

  getAuditLogs(): Observable<AuditLogItem[]> {
    return this.http.get<AuditLogItem[]>(`${this.base}/admin/audit-logs`);
  }

  // Admin User Management
  getAdminUsers(role = '', search = ''): Observable<AdminUserItem[]> {
    let p = new HttpParams();
    if (role)   p = p.set('role', role);
    if (search) p = p.set('search', search);
    return this.http.get<AdminUserItem[]>(`${this.base}/admin/users`, { params: p });
  }

  createAdminUser(data: AdminUserCreate): Observable<AdminUserItem> {
    return this.http.post<AdminUserItem>(`${this.base}/admin/users`, data);
  }

  toggleUserStatus(source: string, id: number): Observable<{ isActive: boolean; passwordEmailed: boolean }> {
    return this.http.put<{ isActive: boolean; passwordEmailed: boolean }>(`${this.base}/admin/users/${source}/${id}/toggle`, {});
  }

  updateAdminUser(source: string, id: number, data: Partial<AdminUserCreate>): Observable<AdminUserItem> {
    return this.http.put<AdminUserItem>(`${this.base}/admin/users/${source}/${id}`, data);
  }

  deleteAdminUser(source: string, id: number): Observable<{ deleted: boolean }> {
    return this.http.delete<{ deleted: boolean }>(`${this.base}/admin/users/${source}/${id}`);
  }


  // Admin Doctor Management
  getDoctorStats(): Observable<DoctorStats> {
    return this.http.get<DoctorStats>(`${this.base}/admin/doctor-stats`);
  }

  createAdminDoctor(data: AdminDoctorCreate): Observable<ApiDoctor> {
    return this.http.post<ApiDoctor>(`${this.base}/admin/doctors`, data);
  }

  toggleDoctorStatus(id: number): Observable<{ isActive: boolean }> {
    return this.http.put<{ isActive: boolean }>(`${this.base}/admin/doctors/${id}/toggle`, {});
  }

  updateAdminDoctor(id: number, data: DoctorUpdate): Observable<ApiDoctor> {
    return this.http.put<ApiDoctor>(`${this.base}/admin/doctors/${id}`, data);
  }

  deleteAdminDoctor(id: number): Observable<{ deleted: boolean }> {
    return this.http.delete<{ deleted: boolean }>(`${this.base}/admin/doctors/${id}`);
  }

  // Reports & Analytics
  getWaitingTime(days = 7): Observable<WaitingTimeDay[]> {
    const p = new HttpParams().set('days', String(days));
    return this.http.get<WaitingTimeDay[]>(`${this.base}/admin/waiting-time`, { params: p });
  }

  getDepartmentStats(): Observable<DepartmentStat[]> {
    return this.http.get<DepartmentStat[]>(`${this.base}/admin/department-stats`);
  }

  getPeakHours(): Observable<PeakHour[]> {
    return this.http.get<PeakHour[]>(`${this.base}/admin/peak-hours`);
  }

  getWeeklySummary(): Observable<WeeklySummary> {
    return this.http.get<WeeklySummary>(`${this.base}/admin/weekly-summary`);
  }

  getAuditLogsFull(page = 1, pageSize = 10, search = '', module = '', action = '', status = ''): Observable<AuditLogsResponse> {
    let p = new HttpParams().set('page', String(page)).set('page_size', String(pageSize));
    if (search) p = p.set('search', search);
    if (module) p = p.set('module', module);
    if (action) p = p.set('action', action);
    if (status) p = p.set('status', status);
    return this.http.get<AuditLogsResponse>(`${this.base}/admin/audit-logs-full`, { params: p });
  }
}
