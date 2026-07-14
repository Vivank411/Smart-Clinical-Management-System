import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { ApiService, ApiPatient, PatientUpdate } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

interface MedDetails {
  structured: boolean;
  symptoms: string[];
  vitals: { label: string; icon: string; value: string }[];
  diagnosis: string;
  notes: string;
  historyNotes: string;   // the junior doctor's past-medication / history notes (plain text)
}

@Component({
  selector: 'app-doctor-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, DialogModule, InputTextModule],
  templateUrl: './doctor-dashboard.component.html',
  styleUrl: './doctor-dashboard.component.scss'
})
export class DoctorDashboardComponent implements OnInit {

  allPatients: ApiPatient[]      = [];
  filteredPatients: ApiPatient[] = [];
  searchQuery  = '';
  isLoading    = false;

  /* ── Detail dialog ── */
  showDetail      = false;
  isLoadingDetail = false;
  selectedPatient: ApiPatient | null = null;

  /* ── Edit state ── */
  isEditing         = false;
  isSaving          = false;
  editAllergies:    string[] = [];
  editAllergyInput  = '';
  editMedicalHistory = '';

  constructor(public auth: AuthService, private api: ApiService) {}

  ngOnInit() { this.loadPatients(); }

  loadPatients() {
    this.isLoading = true;
    this.api.getPatients({ limit: 500 }).subscribe({
      next: (patients) => {
        this.allPatients = patients;
        this.applyFilter();
        this.isLoading = false;
      },
      error: () => { this.isLoading = false; }
    });
  }

  applyFilter() {
    const q = this.searchQuery.trim().toLowerCase();
    this.filteredPatients = q
      ? this.allPatients.filter(p =>
          p.name.toLowerCase().includes(q) ||
          p.patientId.toLowerCase().includes(q) ||
          (p.mobileNumber ?? '').includes(q)
        )
      : [...this.allPatients];
  }

  /* ── Stats ── */
  get totalCount()     { return this.allPatients.length; }
  get checkedInCount() { return this.allPatients.filter(p => p.status === 'Checked-In').length; }
  get reviewedCount()  { return this.allPatients.filter(p => this.isReviewed(p)).length; }

  isReviewed(p: ApiPatient): boolean {
    // Card turns green when junior doctor has filled allergies or medical history
    return !!(p.allergies?.trim() || p.medicalHistory?.trim());
  }

  /* ── Open detail ── */
  openPatient(p: ApiPatient) {
    this.isEditing      = false;
    this.selectedPatient = null;
    this.isLoadingDetail = true;
    this.showDetail      = true;
    this.api.getPatient(p.id).subscribe({
      next: (pt)  => { this.selectedPatient = pt; this.isLoadingDetail = false; },
      error: ()   => { this.isLoadingDetail = false; this.showDetail = false; }
    });
  }

  /* ── Detail helpers ── */
  get detailInitials(): string {
    return this.selectedPatient?.name.split(' ').slice(0,2).map(w => w[0]).join('').toUpperCase() ?? '?';
  }

  get detailAllergyList(): string[] {
    return this.selectedPatient?.allergies?.split(',').map(s => s.trim()).filter(s => !!s) ?? [];
  }

  /** Parse medicalHistory (JSON from a completed consultation, or plain jr-doctor text) into a viewable shape. */
  get medDetails(): MedDetails | null {
    const raw = this.selectedPatient?.medicalHistory?.trim();
    if (!raw) return null;
    const base = this.parseHistory(raw);
    if (base) {
      const v = base['vitals'] ?? {};
      const vitalDefs: [string, string, unknown][] = [
        ['Blood Pressure', 'pi-heart',      v.bp],
        ['Pulse Rate',     'pi-wave-pulse', v.pulse],
        ['Temperature',    'pi-sun',        v.temp],
        ['SpO₂',           'pi-chart-bar',  v.spo2],
        ['Weight',         'pi-user',       v.weight],
        ['Height',         'pi-arrows-v',   v.height],
      ];
      return {
        structured:   true,
        symptoms:     Array.isArray(base['symptoms']) ? base['symptoms'] : [],
        vitals:       vitalDefs.filter(([, , val]) => !!val).map(([label, icon, val]) => ({ label, icon, value: String(val) })),
        diagnosis:    base['diagnosis'] ?? '',
        notes:        base['notes'] ?? '',
        historyNotes: base['jrNotes'] ?? '',
      };
    }
    // Plain text — the junior doctor's own notes
    return { structured: false, symptoms: [], vitals: [], diagnosis: '', notes: '', historyNotes: raw };
  }

  /** Returns the parsed object only when medicalHistory is a structured JSON record, else null. */
  private parseHistory(raw: string): Record<string, any> | null {
    try {
      const d = JSON.parse(raw);
      if (d && typeof d === 'object' && !Array.isArray(d)) return d;
    } catch { /* not JSON */ }
    return null;
  }

  formatDob(dob: string | null): string {
    if (!dob) return '—';
    const [y, m, d] = dob.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  formatAddress(p: ApiPatient): string {
    return [p.addressLine1, p.addressLine2, p.city, p.pinCode].filter(v => !!v).join(', ');
  }

  statusClass(status: string): string {
    const map: Record<string, string> = {
      'Registered': 'st--gray', 'Checked-In': 'st--blue',
      'Consulted': 'st--green', 'Completed': 'st--teal'
    };
    return map[status] ?? 'st--gray';
  }

  /* ── Edit medical details ── */
  // When a consultation exists, medicalHistory is structured JSON — keep it and let the
  // junior doctor edit only their own past-medication / history notes (jrNotes).
  editBase: Record<string, any> | null = null;

  startEdit() {
    if (!this.selectedPatient) return;
    this.editAllergies = this.detailAllergyList.slice();
    const raw = this.selectedPatient.medicalHistory?.trim() ?? '';
    this.editBase = raw ? this.parseHistory(raw) : null;
    this.editMedicalHistory = this.editBase ? (this.editBase['jrNotes'] ?? '') : raw;
    this.isEditing = true;
  }

  cancelEdit() { this.isEditing = false; }

  onAllergyKey(evt: KeyboardEvent) {
    if (evt.key === 'Enter' && this.editAllergyInput.trim()) {
      evt.preventDefault();
      this.editAllergies.push(this.editAllergyInput.trim());
      this.editAllergyInput = '';
    }
  }

  removeAllergy(i: number) { this.editAllergies.splice(i, 1); }

  saveChanges() {
    if (!this.selectedPatient) return;
    this.isSaving = true;
    // Preserve any structured consultation data; only replace the jr-doctor notes.
    const medicalHistory = this.editBase
      ? JSON.stringify({ ...this.editBase, jrNotes: this.editMedicalHistory })
      : this.editMedicalHistory;
    const update: PatientUpdate = {
      allergies:      this.editAllergies.join(', '),
      medicalHistory,
      // Junior doctor only enriches records — status is managed by the full doctor workflow
    };
    this.api.updatePatient(this.selectedPatient.id, update).subscribe({
      next: (updated) => {
        this.selectedPatient = updated;
        const idx = this.allPatients.findIndex(p => p.id === updated.id);
        if (idx !== -1) { this.allPatients[idx] = updated; this.applyFilter(); }
        this.isEditing = false;
        this.isSaving  = false;
      },
      error: () => { this.isSaving = false; }
    });
  }
}
