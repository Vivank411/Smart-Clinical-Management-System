import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, ApiPatient, MedicationResponse, SafetyCheckResult } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

interface MedRow {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  suggestions: string[];
  showSug: boolean;
  /** Result of the last safety check for this row; null once the row changes. */
  safety?: SafetyCheckResult | null;
  /** Doctor explicitly chose to prescribe despite the conflict. */
  acknowledged?: boolean;
  checking?: boolean;
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
            duration: m.duration ?? '', suggestions: [], showSug: false,
            safety: null, acknowledged: false, checking: false
          }));
          this.rxNotes = last.notes ?? '';
          // Rows carried over from a previous prescription have never been
          // checked — a pre-filled conflict is exactly the one a doctor is
          // least likely to notice unaided.
          this.checkAllRows();
        } else {
          this.addRow();
        }
      },
      error: () => { this.addRow(); }
    });
  }

  addRow() {
    this.rows.push({ name: '', dosage: '500mg', frequency: 'OD (Once daily)', duration: '',
                     suggestions: [], showSug: false, safety: null, acknowledged: false, checking: false });
  }

  removeRow(i: number) { this.rows.splice(i, 1); }

  // ── Clinical safety ────────────────────────────────────────────────────────

  safetyDialog: { row: MedRow; result: SafetyCheckResult } | null = null;
  showAlternatives = false;

  /**
   * Runs whenever a row has enough detail to be checkable. Conflicts are
   * detected server-side by the rule engine; this only presents the result.
   */
  runSafetyCheck(row: MedRow, openDialog = true, done?: () => void) {
    if (!this.selectedPatient || !row.name.trim()) { row.safety = null; done?.(); return; }

    row.checking = true;
    row.acknowledged = false;
    this.api.checkMedication({
      patientId: this.selectedPatient.id,
      medicine: { name: row.name.trim(), dosage: row.dosage, frequency: row.frequency, duration: row.duration },
      currentMedicines: this.rows
        .filter(r => r !== row && r.name.trim())
        .map(r => ({ name: r.name.trim(), dosage: r.dosage, frequency: r.frequency, duration: r.duration })),
      doctorName: this.auth.getUser()?.name,
    }).subscribe({
      next: (res) => {
        row.checking = false;
        row.safety = res.hasConflict ? res : null;
        if (res.hasConflict && openDialog) this.openSafetyDialog(row);
        done?.();
      },
      // A failed check leaves the row unchecked rather than marking it clean.
      error: () => { row.checking = false; row.safety = null; done?.(); }
    });
  }

  onMedicineCommitted(row: MedRow) {
    if (row.name.trim()) this.runSafetyCheck(row);
  }

  /**
   * Check every filled row without opening a dialog per result, then surface
   * the most severe conflict once. Used for prescriptions loaded from history.
   */
  checkAllRows() {
    const filled = this.rows.filter(r => r.name.trim());
    if (!filled.length) return;

    let pending = filled.length;
    filled.forEach(row => this.runSafetyCheck(row, false, () => {
      if (--pending > 0) return;
      const worst = filled.find(r => r.safety?.severity === 'High')
                 ?? filled.find(r => r.safety?.hasConflict);
      if (worst) this.openSafetyDialog(worst);
    }));
  }

  openSafetyDialog(row: MedRow) {
    if (!row.safety) return;
    this.showAlternatives = false;
    this.safetyDialog = { row, result: row.safety };
  }

  closeSafetyDialog() {
    this.safetyDialog = null;
    this.showAlternatives = false;
  }

  /** "Proceed Anyway" — keep the medicine, record that the warning was seen. */
  acknowledgeConflict() {
    if (this.safetyDialog) this.safetyDialog.row.acknowledged = true;
    this.closeSafetyDialog();
  }

  /** "Replace Medicine" — reveal the alternatives picker inside the dialog. */
  startReplace() {
    this.showAlternatives = true;
  }

  chooseAlternative(name: string, defaultDosage?: string) {
    if (!this.safetyDialog) return;
    const row = this.safetyDialog.row;
    row.name = name;
    if (defaultDosage && this.DOSAGES.includes(defaultDosage)) row.dosage = defaultDosage;
    row.safety = null;
    row.acknowledged = false;
    this.closeSafetyDialog();
    this.runSafetyCheck(row);   // the replacement is checked in turn
  }

  get unresolvedConflicts(): MedRow[] {
    return this.rows.filter(r => r.name.trim() && r.safety?.hasConflict && !r.acknowledged);
  }

  onMedInput(row: MedRow) {
    const q = row.name.trim().toLowerCase();
    if (!q) { row.suggestions = []; row.showSug = false; return; }
    row.suggestions = this.allMeds.filter(m => m.name.toLowerCase().includes(q)).slice(0, 8).map(m => m.name);
    row.showSug = row.suggestions.length > 0;
  }

  pickSuggestion(row: MedRow, name: string) {
    const med = this.allMeds.find(m => m.name === name);
    row.name = name;
    row.safety = null;
    row.acknowledged = false;
    // Pre-select the closest matching dosage from dropdown list
    if (med?.defaultDosage) {
      const match = this.DOSAGES.find(d => d.toLowerCase() === med.defaultDosage!.toLowerCase());
      row.dosage = match ?? (this.DOSAGES.includes(med.defaultDosage!) ? med.defaultDosage! : this.DOSAGES[7]);
    }
    row.suggestions = [];
    row.showSug = false;
    this.runSafetyCheck(row);
  }

  hideSuggestions(row: MedRow) {
    setTimeout(() => { row.showSug = false; }, 200);
  }

  get filledRows(): MedRow[] {
    return this.rows.filter(r => r.name.trim());
  }

  proceedToPreview() {
    if (!this.filledRows.length) return;
    // Surface any conflict the doctor hasn't looked at yet rather than letting
    // it pass silently into the printed prescription.
    const unreviewed = this.unresolvedConflicts[0];
    if (unreviewed) { this.openSafetyDialog(unreviewed); return; }
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
