import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { InputTextModule } from 'primeng/inputtext';
import { ButtonModule } from 'primeng/button';
import { SelectModule } from 'primeng/select';
import { AutoCompleteModule } from 'primeng/autocomplete';
import { DialogModule } from 'primeng/dialog';
import { AuthService } from '../../services/auth.service';
import { ApiService, ApiPatient, PrescriptionResponse } from '../../services/api.service';

interface Patient {
  numericId: number;
  id: string;
  name: string;
  mobile: string;
  age: number;
  gender: string;
  status: string;
  lastVisit: string;
}

interface ConsultData {
  symptoms?: string[];
  vitals?: { bp?: string; pulse?: string; temp?: string; spo2?: string; weight?: string; height?: string };
  diagnosis?: string;
  notes?: string;
  completedAt?: string;
  images?: { name: string; url: string; annotated?: boolean }[];
}

@Component({
  selector: 'app-search-patient',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, InputTextModule, ButtonModule, SelectModule, AutoCompleteModule, DialogModule],
  templateUrl: './search-patient.component.html',
  styleUrl: './search-patient.component.scss'
})
export class SearchPatientComponent implements OnInit {

  searchValue: any = '';
  suggestions: Patient[] = [];
  currentPage = 1;
  pageSize = 5;
  isLoading = false;

  pageSizeOpts = [
    { label: '5 / page',  value: 5  },
    { label: '10 / page', value: 10 },
    { label: '20 / page', value: 20 }
  ];

  allPatients: Patient[] = [];
  filteredPatients: Patient[] = [];

  /* Detail panel */
  showDetails         = false;
  isLoadingDetails    = false;
  selectedPatient:    ApiPatient | null = null;
  selectedPrescriptions: PrescriptionResponse[] = [];
  consultData:        ConsultData | null = null;
  zoomedImage:        string | null = null;

  constructor(
    public auth: AuthService,
    private router: Router,
    private api: ApiService
  ) {}

  ngOnInit() { this.loadPatients(); }

  private mapApiPatient(p: ApiPatient): Patient {
    return {
      numericId: p.id,
      id:        p.patientId,
      name:      p.name,
      mobile:    p.mobileNumber ?? '—',
      age:       p.age,
      gender:    p.gender,
      status:    p.status,
      lastVisit: p.checkinTime ?? '—',
    };
  }

  private loadPatients(search = '') {
    this.isLoading = true;
    this.api.getPatients({ search, limit: 100 }).subscribe({
      next: (pts) => { this.allPatients = pts.map(p => this.mapApiPatient(p)); this.filteredPatients = [...this.allPatients]; this.currentPage = 1; this.isLoading = false; },
      error: () => { this.isLoading = false; }
    });
  }

  filterSuggestions(event: { query: string }) {
    const q = event.query.trim().toLowerCase();
    if (!q) { this.suggestions = []; return; }
    this.api.getPatients({ search: q, limit: 8 }).subscribe({
      next: (pts) => { this.suggestions = pts.map(p => this.mapApiPatient(p)); },
      error: () => { this.suggestions = []; }
    });
  }

  onPatientSelect(event: any) { const p: Patient = event.value ?? event; this.filteredPatients = [p]; this.currentPage = 1; }

  search() {
    this.currentPage = 1;
    if (this.searchValue && typeof this.searchValue === 'object') { this.filteredPatients = [this.searchValue as Patient]; return; }
    this.loadPatients((this.searchValue || '').toString().trim());
  }

  clear() { this.searchValue = ''; this.suggestions = []; this.currentPage = 1; this.loadPatients(); }

  get totalPages()        { return Math.ceil(this.filteredPatients.length / this.pageSize); }
  get paginatedResults()  { const s = (this.currentPage - 1) * this.pageSize; return this.filteredPatients.slice(s, s + this.pageSize); }
  get pages()             { return Array.from({ length: Math.min(this.totalPages, 5) }, (_, i) => i + 1); }
  get showingFrom()       { return this.filteredPatients.length === 0 ? 0 : (this.currentPage - 1) * this.pageSize + 1; }
  get showingTo()         { return Math.min(this.currentPage * this.pageSize, this.filteredPatients.length); }
  setPage(p: number)      { if (p >= 1 && p <= this.totalPages) this.currentPage = p; }
  onPageSizeChange()      { this.currentPage = 1; }

  /* ── Detail dialog ── */
  viewDetails(p: Patient) {
    this.selectedPatient       = null;
    this.selectedPrescriptions = [];
    this.consultData           = null;
    this.isLoadingDetails      = true;
    this.showDetails           = true;

    forkJoin([
      this.api.getPatient(p.numericId),
      this.api.getPatientPrescriptions(p.numericId)
    ]).subscribe({
      next: ([patient, prescriptions]) => {
        this.selectedPatient       = patient;
        this.selectedPrescriptions = prescriptions;
        if (patient.medicalHistory) {
          try { this.consultData = JSON.parse(patient.medicalHistory); } catch { this.consultData = null; }
        }
        this.isLoadingDetails = false;
      },
      error: () => { this.isLoadingDetails = false; this.showDetails = false; }
    });
  }

  get detailInitials(): string {
    if (!this.selectedPatient) return '?';
    return this.selectedPatient.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
  }

  get detailAllergyList(): string[] {
    return this.selectedPatient?.allergies?.split(',').map(s => s.trim()).filter(Boolean) ?? [];
  }

  get latestPrescription(): PrescriptionResponse | null {
    return this.selectedPrescriptions.length ? this.selectedPrescriptions[0] : null;
  }

  get consultVitals(): { label: string; value: string }[] {
    const v = this.consultData?.vitals;
    if (!v) return [];
    const map: Record<string, string> = { bp: 'BP', pulse: 'Pulse', temp: 'Temp', spo2: 'SpO₂', weight: 'Weight', height: 'Height' };
    return Object.entries(map).filter(([k]) => (v as any)[k]).map(([k, label]) => ({ label, value: (v as any)[k] }));
  }

  formatAddress(p: ApiPatient): string {
    return [p.addressLine1, p.addressLine2, p.city, p.pinCode].filter(Boolean).join(', ');
  }

  formatDob(dob: string | null): string {
    if (!dob) return '—';
    const [y, m, d] = dob.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  formatDate(d: string | null): string {
    if (!d) return '—';
    try { return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }); } catch { return d; }
  }

  detailStatusClass(status: string): string {
    return ({ 'Registered': 'ds--gray', 'Checked-In': 'ds--blue', 'Consulted': 'ds--amber', 'Completed': 'ds--green' } as Record<string, string>)[status] ?? 'ds--gray';
  }

  checkInFromDetails() {
    if (!this.selectedPatient) return;
    const p = this.selectedPatient;
    const parts = p.name.trim().split(/\s+/);
    const initials = ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
    const patient = { numericId: p.id, id: p.patientId, name: p.name, initials, mobile: p.mobileNumber ?? '—', age: p.age, gender: p.gender, bloodGroup: 'N/A', dob: this.formatDob(p.dob), lastVisit: p.checkinTime ?? '—', registeredOn: '—' };
    this.showDetails = false;
    this.router.navigate(['/check-in'], { state: { patient } });
  }

  checkInPatient(p: Patient) {
    const initials = p.name.split(' ').map((w: string) => w[0]).join('').substring(0, 2).toUpperCase();
    const patient = { numericId: p.numericId, id: p.id, name: p.name, initials, mobile: p.mobile, age: p.age, gender: p.gender, bloodGroup: 'N/A', dob: '—', lastVisit: p.lastVisit, registeredOn: '—' };
    this.router.navigate(['/check-in'], { state: { patient } });
  }
}
