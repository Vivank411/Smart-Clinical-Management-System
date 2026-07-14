import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { DatePickerModule } from 'primeng/datepicker';
import { TextareaModule } from 'primeng/textarea';
import { RadioButtonModule } from 'primeng/radiobutton';
import { DialogModule } from 'primeng/dialog';
import { AutoCompleteModule } from 'primeng/autocomplete';
import { AuthService } from '../../services/auth.service';
import { ApiService, ApiPatient } from '../../services/api.service';

interface PatientRecord {
  numericId:    number;
  id:           string;
  name:         string;
  initials:     string;
  mobile:       string;
  age:          number;
  gender:       string;
  bloodGroup:   string;
  dob:          string;
  lastVisit:    string;
  registeredOn: string;
}

interface Doctor {
  label:    string;
  value:    string;
  specialty: string;
  from:     string;
  to:       string;
}

@Component({
  selector: 'app-check-in',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    InputTextModule, SelectModule, DatePickerModule,
    TextareaModule, RadioButtonModule, DialogModule, AutoCompleteModule
  ],
  templateUrl: './check-in.component.html',
  styleUrl: './check-in.component.scss'
})
export class CheckInComponent implements OnInit {

  /* ── Patient search ── */
  patientSearch: any = '';
  patientSuggestions: PatientRecord[] = [];
  selectedPatient: PatientRecord | null = null;

  /* ── Visit details ── */
  assignedDoctor: Doctor | null = null;
  visitDate: Date = new Date();
  visitTime = '';
  reasonForVisit = '';
  visitType = 'Outpatient';
  priority = 'Normal';
  symptoms = '';
  notes = '';
  uploadedFileName = '';

  /* ── UI state ── */
  submitted    = false;
  showPreview  = false;
  showSuccess  = false;
  isLoading    = false;
  errorMessage = '';
  queueToken   = '';

  today = new Date();

  /* ── Data ── */
  doctors: Doctor[] = [];

  private readonly ALL_SLOTS = [
    '09:00 AM','09:30 AM','10:00 AM','10:30 AM','11:00 AM','11:30 AM',
    '12:00 PM','12:30 PM','01:00 PM','01:30 PM','02:00 PM','02:30 PM',
    '03:00 PM','03:30 PM','04:00 PM','04:30 PM','05:00 PM'
  ];

  visitTypeOpts = ['Outpatient','Inpatient','Emergency','Follow-up'].map(v => ({ label: v, value: v }));

  constructor(
    public auth: AuthService,
    private router: Router,
    private api: ApiService
  ) {}

  ngOnInit() {
    this.api.getDoctors().subscribe({
      next: (docs) => {
        this.doctors = docs.map(d => ({
          label:    d.name,
          value:    String(d.id),
          specialty: d.specialization,
          from:     '09:00 AM',
          to:       '05:00 PM',
        }));
      },
      error: () => { /* doctors list stays empty */ }
    });

    const state = history.state as { patient?: PatientRecord };
    if (state?.patient) {
      this.selectedPatient = state.patient;
      this.patientSearch   = state.patient;
    }
  }

  private mapApiPatient(p: ApiPatient): PatientRecord {
    const parts    = p.name.split(' ');
    const initials = parts.slice(0, 2).map(w => w[0]).join('').toUpperCase();
    return {
      numericId:    p.id,
      id:           p.patientId,
      name:         p.name,
      initials:     initials,
      mobile:       p.mobileNumber ?? '—',
      age:          p.age,
      gender:       p.gender,
      bloodGroup:   'N/A',
      dob:          p.dob
                    ? new Date(p.dob).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
                    : '—',
      lastVisit:    '—',
      registeredOn: '—'
    };
  }

  /* ── Autocomplete ── */
  filterPatients(event: { query: string }) {
    const q = (event.query || '').trim();
    if (!q) { this.patientSuggestions = []; return; }

    this.api.getPatients({ search: q, limit: 6 }).subscribe({
      next: (patients) => {
        this.patientSuggestions = patients.map(p => this.mapApiPatient(p));
      },
      error: () => { this.patientSuggestions = []; }
    });
  }

  onPatientSelect(event: any) {
    const p: PatientRecord = event.value ?? event;
    this.selectedPatient = p;
    this.patientSearch   = p;
  }

  clearPatient() {
    this.selectedPatient     = null;
    this.patientSearch       = '';
    this.patientSuggestions  = [];
    this.submitted           = false;
    this.errorMessage        = '';
  }

  /* ── File upload ── */
  onFileChange(event: any) {
    const file: File = event.target.files?.[0];
    if (file) this.uploadedFileName = file.name;
  }

  /* ── Computed display values ── */
  get visitDateTimeDisplay(): string {
    if (!this.visitDate) return '—';
    const d = this.visitDate.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    return this.visitTime ? `${d}, ${this.visitTime}` : d;
  }

  get step1Done():   boolean { return !!this.selectedPatient; }
  get step2Active(): boolean { return this.step1Done; }
  get step3Active(): boolean {
    return this.step1Done && !!this.assignedDoctor && !!this.visitTime && !!this.reasonForVisit.trim();
  }
  get isFormValid(): boolean { return this.step3Active; }

  private parseTimeMins(t: string): number {
    const [timePart, period] = t.split(' ');
    let [h, m] = timePart.split(':').map(Number);
    if (period === 'PM' && h !== 12) h += 12;
    if (period === 'AM' && h === 12) h = 0;
    return h * 60 + m;
  }

  get availableTimeOpts(): { label: string; value: string }[] {
    if (!this.assignedDoctor) return [];

    const docFrom = this.parseTimeMins(this.assignedDoctor.from);
    const docTo   = this.parseTimeMins(this.assignedDoctor.to);

    const isToday = this.visitDate
      ? this.visitDate.toDateString() === new Date().toDateString()
      : true;
    const now = new Date();
    const nowMins = now.getHours() * 60 + now.getMinutes();

    return this.ALL_SLOTS
      .filter(t => {
        const mins = this.parseTimeMins(t);
        return mins >= docFrom && mins <= docTo && (!isToday || mins > nowMins);
      })
      .map(t => ({ label: t, value: t }));
  }

  onDoctorChange() {
    this.visitTime = '';
  }

  onVisitDateChange() {
    if (this.visitTime && !this.availableTimeOpts.some(o => o.value === this.visitTime)) {
      this.visitTime = '';
    }
  }

  /* ── Actions ── */
  openPreview() {
    this.submitted = true;
    if (!this.isFormValid) return;
    this.showPreview = true;
  }

  private doCheckIn(onSuccess: (queueToken: string) => void) {
    if (!this.selectedPatient) return;
    this.isLoading    = true;
    this.errorMessage = '';

    this.api.updatePatient(this.selectedPatient.numericId, {
      status:         'Checked-In',
      doctor:         this.assignedDoctor!.label,
      reasonForVisit: this.reasonForVisit,
    }).subscribe({
      next: (patient) => {
        this.isLoading = false;
        onSuccess(patient.queueToken ?? '');
      },
      error: (err) => {
        this.isLoading    = false;
        this.showPreview  = false;
        this.errorMessage = err.error?.detail ?? 'Check-in failed. Please try again.';
      }
    });
  }

  confirmCheckIn() {
    this.doCheckIn((token) => {
      this.queueToken = token;
      this.showPreview = false;
      this.showSuccess = true;
    });
  }

  checkIn() {
    this.submitted = true;
    if (!this.isFormValid) return;
    this.doCheckIn((token) => {
      this.queueToken  = token;
      this.showSuccess = true;
    });
  }

  onSuccessClose() {
    this.showSuccess = false;
    this.router.navigate(['/dashboard']);
  }

  cancel() {
    this.router.navigate(['/dashboard']);
  }
}
