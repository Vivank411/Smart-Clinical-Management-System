import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, ApiPatient, MedicationResponse } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

interface MedRow {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  suggestions: string[];
  showSug: boolean;
}

interface ConsultationData {
  symptoms?: string[];
  vitals?: { bp?: string; pulse?: string; temp?: string; spo2?: string; weight?: string; height?: string };
  diagnosis?: string;
  notes?: string;
  completedAt?: string;
  images?: { name: string; url: string; annotated?: boolean }[];
  jrNotes?: string;
}

@Component({
  selector: 'app-doctor-eprescription',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './doctor-eprescription.component.html',
  styleUrl: './doctor-eprescription.component.scss'
})
export class DoctorEprescriptionComponent implements OnInit {
  patients: ApiPatient[] = [];
  selectedPatient: ApiPatient | null = null;
  consultation: ConsultationData = {};

  isLoadingPatients = false;
  isSaving = false;
  savedSuccess = false;
  showPreview = false;
  zoomedImage: string | null = null;

  rows: MedRow[] = [];
  rxNotes = '';
  allMeds: MedicationResponse[] = [];

  readonly FREQUENCIES = ['OD (Once daily)', 'BD (Twice daily)', 'TDS (Thrice daily)', 'QID (Four times)', 'SOS (As needed)', 'At night', 'Before meal', 'After meal'];
  readonly DOSAGES = [
    '2.5mg','5mg','10mg','20mg','25mg','40mg','50mg','75mg','100mg','125mg',
    '150mg','200mg','250mg','300mg','400mg','500mg','650mg','750mg','1000mg',
    '5mg/5ml','10mg/5ml','125mg/5ml','200mg/5ml','250mg/5ml','500mg/5ml',
    '1 puff','2 puffs','1 drop','2 drops','1 tablet','2 tablets','1 sachet'
  ];
  readonly today = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });

  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit() {
    this.loadPatients();
    this.api.getMedications().subscribe({ next: (m) => { this.allMeds = m; } });
  }

  loadPatients() {
    this.isLoadingPatients = true;
    this.api.getPatients({ status: 'Consulted', doctor: this.auth.getUser()?.name ?? '', limit: 500 }).subscribe({
      next: (pts) => { this.patients = pts; this.isLoadingPatients = false; },
      error: () => { this.isLoadingPatients = false; }
    });
  }

  selectPatient(p: ApiPatient) {
    this.selectedPatient = p;
    this.consultation = {};
    this.rows = [];
    this.rxNotes = '';
    this.savedSuccess = false;
    this.showPreview = false;

    if (p.medicalHistory) {
      try { this.consultation = JSON.parse(p.medicalHistory); } catch {}
    }

    this.api.getPatientPrescriptions(p.id).subscribe({
      next: (prs) => {
        if (prs.length) {
          const last = prs[prs.length - 1];
          this.rows = last.medications.map(m => ({
            name: m.name, dosage: m.dosage, frequency: m.frequency,
            duration: m.duration ?? '', suggestions: [], showSug: false
          }));
          this.rxNotes = last.notes ?? '';
        } else {
          this.addRow();
        }
      },
      error: () => { this.addRow(); }
    });
  }

  addRow() {
    this.rows.push({ name: '', dosage: '500mg', frequency: 'OD (Once daily)', duration: '', suggestions: [], showSug: false });
  }

  removeRow(i: number) { this.rows.splice(i, 1); }

  onMedInput(row: MedRow) {
    const q = row.name.trim().toLowerCase();
    if (!q) { row.suggestions = []; row.showSug = false; return; }
    row.suggestions = this.allMeds.filter(m => m.name.toLowerCase().includes(q)).slice(0, 8).map(m => m.name);
    row.showSug = row.suggestions.length > 0;
  }

  pickSuggestion(row: MedRow, name: string) {
    const med = this.allMeds.find(m => m.name === name);
    row.name = name;
    // Pre-select the closest matching dosage from dropdown list
    if (med?.defaultDosage) {
      const match = this.DOSAGES.find(d => d.toLowerCase() === med.defaultDosage!.toLowerCase());
      row.dosage = match ?? (this.DOSAGES.includes(med.defaultDosage!) ? med.defaultDosage! : this.DOSAGES[7]);
    }
    row.suggestions = [];
    row.showSug = false;
  }

  hideSuggestions(row: MedRow) {
    setTimeout(() => { row.showSug = false; }, 200);
  }

  get filledRows(): MedRow[] {
    return this.rows.filter(r => r.name.trim());
  }

  proceedToPreview() {
    if (!this.filledRows.length) return;
    this.showPreview = true;
  }

  backToEdit() {
    this.showPreview = false;
    this.savedSuccess = false;
  }

  savePrescription() {
    if (!this.selectedPatient || !this.filledRows.length) return;
    this.isSaving = true;
    this.api.createPrescription({
      patientId: this.selectedPatient.id,
      medications: this.filledRows.map(r => ({ name: r.name, dosage: r.dosage, frequency: r.frequency, duration: r.duration })),
      doctorName: this.auth.getUser()?.name,
      notes: this.rxNotes
    }).subscribe({
      next: () => {
        this.isSaving = false;
        this.savedSuccess = true;
        // Backend sets status=Completed; after 1.5s clear selection + refresh list
        setTimeout(() => {
          this.selectedPatient = null;
          this.showPreview = false;
          this.savedSuccess = false;
          this.rows = [];
          this.rxNotes = '';
          this.loadPatients();
        }, 1500);
      },
      error: () => { this.isSaving = false; }
    });
  }

  printPrescription() { window.print(); }

  get allergyList(): string[] {
    return this.selectedPatient?.allergies?.split(',').map(s => s.trim()).filter(Boolean) ?? [];
  }

  get clinicalImages() { return this.consultation.images ?? []; }

  get vitalsEntries(): { label: string; value: string }[] {
    if (!this.consultation?.vitals) return [];
    const v = this.consultation.vitals;
    const map: Record<string, string> = { bp: 'BP', pulse: 'Pulse', temp: 'Temp', spo2: 'SpO₂', weight: 'Weight', height: 'Height' };
    return Object.entries(map).filter(([k]) => (v as any)[k]).map(([k, label]) => ({ label, value: (v as any)[k] }));
  }

  initials(name: string) { return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase(); }

  trackIdx(i: number) { return i; }

  getDosageOptions(row: MedRow): string[] {
    if (row.dosage && !this.DOSAGES.includes(row.dosage)) {
      return [row.dosage, ...this.DOSAGES];
    }
    return this.DOSAGES;
  }
}
