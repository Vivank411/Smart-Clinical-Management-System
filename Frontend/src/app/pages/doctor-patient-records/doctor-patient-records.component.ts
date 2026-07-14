import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { debounceTime, distinctUntilChanged, Subject } from 'rxjs';
import { ApiService, ApiPatient, PrescriptionResponse } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

interface ConsultData {
  symptoms?: string[];
  vitals?: { bp?: string; pulse?: string; temp?: string; spo2?: string; weight?: string; height?: string };
  diagnosis?: string;
  notes?: string;
  completedAt?: string;
  images?: { name: string; url: string; annotated?: boolean }[];
}

@Component({
  selector: 'app-doctor-patient-records',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './doctor-patient-records.component.html',
  styleUrl: './doctor-patient-records.component.scss'
})
export class DoctorPatientRecordsComponent implements OnInit {

  patients: ApiPatient[] = [];
  isLoadingList = false;
  searchQuery = '';
  private searchSubject = new Subject<string>();

  selectedPatient: ApiPatient | null = null;
  prescriptions: PrescriptionResponse[] = [];
  consultData: ConsultData | null = null;
  isLoadingDetail = false;
  zoomedImage: string | null = null;

  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit() {
    this.loadPatients();
    this.searchSubject.pipe(debounceTime(300), distinctUntilChanged()).subscribe(q => this.loadPatients(q));
  }

  loadPatients(search = '') {
    this.isLoadingList = true;
    const drName = this.auth.getUser()?.name ?? '';
    this.api.getPatients({ status: 'Completed', doctor: drName, search, limit: 200 }).subscribe({
      next: (pts) => { this.patients = pts; this.isLoadingList = false; },
      error: () => { this.isLoadingList = false; }
    });
  }

  onSearch() { this.searchSubject.next(this.searchQuery.trim()); }

  clearSearch() { this.searchQuery = ''; this.loadPatients(); }

  selectPatient(p: ApiPatient) {
    if (this.selectedPatient?.id === p.id) return;
    this.selectedPatient = p;
    this.prescriptions   = [];
    this.consultData     = null;
    this.isLoadingDetail = true;
    this.zoomedImage     = null;

    forkJoin([
      this.api.getPatient(p.id),
      this.api.getPatientPrescriptions(p.id)
    ]).subscribe({
      next: ([patient, prs]) => {
        this.selectedPatient = patient;
        this.prescriptions   = prs;
        if (patient.medicalHistory) {
          try { this.consultData = JSON.parse(patient.medicalHistory); } catch {}
        }
        this.isLoadingDetail = false;
      },
      error: () => { this.isLoadingDetail = false; }
    });
  }

  get latestPrescription(): PrescriptionResponse | null {
    return this.prescriptions.length ? this.prescriptions[0] : null;
  }

  get vitalsEntries(): { label: string; value: string }[] {
    const v = this.consultData?.vitals;
    if (!v) return [];
    const map: Record<string, string> = { bp: 'BP', pulse: 'Pulse', temp: 'Temp', spo2: 'SpO₂', weight: 'Weight', height: 'Height' };
    return Object.entries(map).filter(([k]) => (v as any)[k]).map(([k, label]) => ({ label, value: (v as any)[k] }));
  }

  get clinicalImages() { return this.consultData?.images ?? []; }

  get allergyList(): string[] {
    return this.selectedPatient?.allergies?.split(',').map(s => s.trim()).filter(Boolean) ?? [];
  }

  initials(name: string): string {
    return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
  }

  formatDate(d: any): string {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }); } catch { return String(d); }
  }

  formatDob(dob: string | null): string {
    if (!dob) return '—';
    const [y, m, d] = dob.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  getVisitDate(p: ApiPatient): string {
    if (p.medicalHistory) {
      try {
        const d = JSON.parse(p.medicalHistory);
        if (d.completedAt) return new Date(d.completedAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
      } catch {}
    }
    return '—';
  }

  get lastVisitDisplay(): string {
    if (this.consultData?.completedAt) {
      return new Date(this.consultData.completedAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    }
    if (this.latestPrescription?.prescriptionDate) {
      return this.formatDate(this.latestPrescription.prescriptionDate);
    }
    return '—';
  }
}
