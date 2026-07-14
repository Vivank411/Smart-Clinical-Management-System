import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { DatePickerModule } from 'primeng/datepicker';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { TextareaModule } from 'primeng/textarea';
import { AuthService } from '../../services/auth.service';
import { ApiService } from '../../services/api.service';
import { SettingsService } from '../../services/settings.service';

@Component({
  selector: 'app-patient-registration',
  standalone: true,
  imports: [
    CommonModule, FormsModule, RouterLink,
    InputTextModule, SelectModule, DatePickerModule,
    DialogModule, ButtonModule, TextareaModule
  ],
  templateUrl: './patient-registration.component.html',
  styleUrl: './patient-registration.component.scss'
})
export class PatientRegistrationComponent implements OnInit {

  /* Personal */
  firstName = ''; lastName = ''; dob: Date | null = null;
  gender = ''; bloodGroup = '';
  mobile = ''; email = ''; address = '';
  insuranceCompany = '';

  /* Additional (optional) */
  idProofType = ''; idProofNumber = '';
  emergencyName = ''; emergencyRelation = ''; emergencyPhone = '';

  /* Medical chips */
  allergies: string[] = [];   allergyInput = '';
  conditions: string[] = [];  conditionInput = '';
  medications: string[] = []; medicationInput = '';
  prevSurgeries = ''; notes = '';

  /* UI state */
  showPreview = false;
  showSuccess = false;
  isLoading = false;
  errorMessage = '';
  registeredId = '';
  registeredNumericId = 0;
  private checkInTimer: ReturnType<typeof setTimeout> | null = null;

  /* Duplicate detection */
  duplicateNameDob  = '';
  duplicateMobile   = '';
  mobileMatchName   = '';
  mobileMatchId     = '';
  allowDuplicateMobile = false;
  private dupCheckTimer: ReturnType<typeof setTimeout> | null = null;

  /* ID proof validation & auto-fill */
  idProofError      = '';
  autoFilledPatient: any = null;
  isCheckingIdProof = false;
  regSubmitted      = false;

  private readonly ID_RULES: Record<string, { pattern: RegExp; hint: string }> = {
    'Aadhaar Card':    { pattern: /^\d{12}$/,                   hint: '12-digit number' },
    'PAN Card':        { pattern: /^[A-Z]{5}\d{4}[A-Z]$/,      hint: 'Format: AAAAA0000A (5 letters, 4 digits, 1 letter)' },
    'Passport':        { pattern: /^[A-Z]\d{7}$/,               hint: 'Format: A0000000 (1 letter + 7 digits)' },
    'Voter ID':        { pattern: /^[A-Z]{3}\d{7}$/,            hint: 'Format: AAA0000000 (3 letters + 7 digits)' },
    'Driving Licence': { pattern: /^[A-Z]{2}\d{2}[A-Z0-9]{5,13}$/, hint: 'State code + RTO code + licence number' },
  };

  private readonly ID_INPUT_RULES: Record<string, { strip: RegExp; maxLen: number }> = {
    'Aadhaar Card':    { strip: /[^\d]/g,     maxLen: 12 },
    'PAN Card':        { strip: /[^A-Z0-9]/g, maxLen: 10 },
    'Passport':        { strip: /[^A-Z0-9]/g, maxLen: 8  },
    'Voter ID':        { strip: /[^A-Z0-9]/g, maxLen: 10 },
    'Driving Licence': { strip: /[^A-Z0-9]/g, maxLen: 17 },
  };

  get idMaxLength(): number {
    return this.ID_INPUT_RULES[this.idProofType]?.maxLen ?? 30;
  }

  /* Dropdown options */
  genderOpts       = ['Male','Female','Other'].map(v => ({ label: v, value: v }));
  bloodOpts        = ['A+','A-','B+','B-','AB+','AB-','O+','O-'].map(v => ({ label: v, value: v }));
  idProofOpts      = ['Aadhaar Card','PAN Card','Passport','Voter ID','Driving Licence'].map(v => ({ label: v, value: v }));
  relationshipOpts = ['Father','Mother','Spouse','Sibling','Son','Daughter','Friend','Other'].map(v => ({ label: v, value: v }));
  insuranceOpts: { label: string; value: string }[] = [];

  today = new Date();

  registrationEnabled = true;

  constructor(
    public auth: AuthService,
    private router: Router,
    private api: ApiService,
    private cdr: ChangeDetectorRef,
    private settings: SettingsService
  ) {}

  ngOnInit() {
    this.registrationEnabled = this.settings.registrationEnabled;
    if (!this.registrationEnabled) return;   // don't bother loading data when registration is off

    this.api.getInsuranceCompanies().subscribe({
      next: (companies) => {
        this.insuranceOpts = companies.map(c => ({ label: c.name, value: c.name }));
      },
      error: () => {
        /* Non-critical: insurance list just stays empty */
      }
    });
  }

  get initials() { return ((this.firstName[0] ?? '') + (this.lastName[0] ?? '')).toUpperCase() || '?'; }
  get fullName()  { return [this.firstName, this.lastName].filter(Boolean).join(' ') || '—'; }

  /* ── Mandatory-field validation (shown after Register is pressed) ── */
  get firstNameInvalid(): boolean { return this.regSubmitted && !this.firstName.trim(); }
  get lastNameInvalid():  boolean { return this.regSubmitted && !this.lastName.trim(); }
  get dobInvalid():       boolean { return this.regSubmitted && !this.dob; }
  get genderInvalid():    boolean { return this.regSubmitted && !this.gender; }
  get mobileInvalid():    boolean { return this.regSubmitted && this.mobile.replace(/\D/g, '').length !== 10; }

  get mobileErrorMsg(): string {
    return !this.mobile.trim() ? 'Mobile number is required.' : 'Mobile number must be 10 digits.';
  }

  get hasMandatoryErrors(): boolean {
    return this.firstNameInvalid || this.lastNameInvalid || this.dobInvalid || this.genderInvalid || this.mobileInvalid;
  }

  private scrollToFirstError() {
    setTimeout(() => document.querySelector('.field.invalid')
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }

  get age(): string {
    if (!this.dob) return '';
    const diff = Date.now() - this.dob.getTime();
    const years  = Math.floor(diff / (365.25 * 24 * 3600 * 1000));
    const months = Math.floor((diff % (365.25 * 24 * 3600 * 1000)) / (30.44 * 24 * 3600 * 1000));
    return `${years} yrs ${months} mo`;
  }

  get ageYears(): number {
    if (!this.dob) return 0;
    return Math.floor((Date.now() - this.dob.getTime()) / (365.25 * 24 * 3600 * 1000));
  }

  get formattedDob() {
    if (!this.dob) return '—';
    return this.dob.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) + ` (${this.ageYears} years)`;
  }

  /* Chip helpers */
  addAllergy()    { const v = this.allergyInput.trim();    if (v && !this.allergies.includes(v))   this.allergies.push(v);    this.allergyInput = ''; }
  addCondition()  { const v = this.conditionInput.trim();  if (v && !this.conditions.includes(v))  this.conditions.push(v);  this.conditionInput = ''; }
  addMedication() { const v = this.medicationInput.trim(); if (v && !this.medications.includes(v)) this.medications.push(v); this.medicationInput = ''; }

  onAllergyKey(e: KeyboardEvent)    { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); this.addAllergy(); } }
  onConditionKey(e: KeyboardEvent)  { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); this.addCondition(); } }
  onMedicationKey(e: KeyboardEvent) { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); this.addMedication(); } }
  removeChip(list: string[], i: number) { list.splice(i, 1); }

  clearForm() {
    this.firstName = ''; this.lastName = ''; this.dob = null;
    this.gender = ''; this.bloodGroup = '';
    this.mobile = ''; this.email = ''; this.address = '';
    this.insuranceCompany = '';
    this.idProofType = ''; this.idProofNumber = '';
    this.emergencyName = ''; this.emergencyRelation = ''; this.emergencyPhone = '';
    this.allergies = []; this.conditions = []; this.medications = [];
    this.prevSurgeries = ''; this.notes = '';
    this.errorMessage = '';
    this.duplicateNameDob = ''; this.duplicateMobile = '';
    this.mobileMatchName = ''; this.mobileMatchId = '';
    this.allowDuplicateMobile = false;
    if (this.dupCheckTimer) { clearTimeout(this.dupCheckTimer); this.dupCheckTimer = null; }
    this.idProofError = ''; this.autoFilledPatient = null;
    this.isCheckingIdProof = false; this.regSubmitted = false;
  }

  /* ── Duplicate detection ── */
  onNameOrDobChange() {
    this.duplicateNameDob = '';
    if (this.dupCheckTimer) { clearTimeout(this.dupCheckTimer); this.dupCheckTimer = null; }
    if (this.firstName.trim() && this.lastName.trim() && this.dob) {
      this.dupCheckTimer = setTimeout(() => this.runNameDobCheck(), 700);
    }
  }

  onMobileChange() {
    this.duplicateMobile = '';
    this.mobileMatchName = '';
    this.mobileMatchId = '';
    this.allowDuplicateMobile = false;
  }

  onMobileBlur() {
    if (this.mobile.replace(/\D/g, '').length === 10) {
      this.runMobileCheck();
    }
  }

  private runNameDobCheck() {
    const name   = `${this.firstName.trim()} ${this.lastName.trim()}`;
    const d      = this.dob!;
    const dobStr = [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-');
    this.api.checkDuplicate(name, dobStr, '').subscribe({
      next: (r) => {
        if (r.nameDobExists) {
          this.duplicateNameDob = `A patient with this name and date of birth is already registered (${r.nameDobPatientId}).`;
        }
      },
      error: () => {}
    });
  }

  private runMobileCheck() {
    this.api.checkDuplicate('', '', this.mobile.trim()).subscribe({
      next: (r) => {
        if (r.mobileExists) {
          this.mobileMatchName = r.mobilePatientName ?? '';
          this.mobileMatchId   = r.mobilePatientId   ?? '';
          this.duplicateMobile = r.mobilePatientName ?? 'another patient';
        }
      },
      error: () => {}
    });
  }

  /* ── ID proof ── */
  onIdTypeChange() {
    this.idProofNumber = '';
    this.idProofError  = '';
    this.autoFilledPatient = null;
  }

  onIdNumberChange(value: string) {
    const rule = this.ID_INPUT_RULES[this.idProofType];
    if (rule) {
      let filtered = this.idProofType !== 'Aadhaar Card' ? value.toUpperCase() : value;
      filtered = filtered.replace(rule.strip, '').slice(0, rule.maxLen);
      this.idProofNumber = filtered;
      // Force Angular to write filtered value back to DOM (blocks invalid chars)
      if (filtered !== value) this.cdr.detectChanges();
    } else {
      this.idProofNumber = value;
    }
    this.idProofError = '';
    this.autoFilledPatient = null;
  }

  validateIdNumber(): boolean {
    if (!this.idProofType || !this.idProofNumber.trim()) {
      this.idProofError = '';
      return false;
    }
    const rule = this.ID_RULES[this.idProofType];
    if (!rule) { this.idProofError = ''; return true; }
    if (!rule.pattern.test(this.idProofNumber.trim())) {
      this.idProofError = `Invalid ${this.idProofType} — ${rule.hint}`;
      return false;
    }
    this.idProofError = '';
    return true;
  }

  onIdNumberBlur() {
    if (!this.validateIdNumber()) return;
    this.isCheckingIdProof = true;
    this.api.getPatientByIdProof(this.idProofType, this.idProofNumber.trim()).subscribe({
      next: (p) => {
        this.isCheckingIdProof = false;
        this.autoFilledPatient = p;
        this.autoFillFromPatient(p);
      },
      error: () => { this.isCheckingIdProof = false; }
    });
  }

  private autoFillFromPatient(p: any) {
    const parts = p.name.trim().split(/\s+/);
    this.firstName = parts[0] ?? '';
    this.lastName  = parts.slice(1).join(' ');
    this.gender    = p.gender ?? '';
    this.mobile    = p.mobileNumber ?? '';
    if (p.dob) {
      const [y, m, d] = (p.dob as string).split('-').map(Number);
      this.dob = new Date(y, m - 1, d);
    }
    this.insuranceCompany = p.insuranceCompany ?? '';
    if (p.allergies) {
      this.allergies = (p.allergies as string).split(',').map((s: string) => s.trim()).filter(Boolean);
    }
    this.onNameOrDobChange();
  }

  dismissAutoFill() {
    this.autoFilledPatient = null;
  }

  goToCheckInAutofilled() {
    if (!this.autoFilledPatient) return;
    const p = this.autoFilledPatient;
    const parts    = p.name.trim().split(/\s+/);
    const initials = ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
    const patient = {
      numericId:    p.id,
      id:           p.patientId,
      name:         p.name,
      initials,
      mobile:       p.mobileNumber ?? '—',
      age:          p.age,
      gender:       p.gender ?? 'N/A',
      bloodGroup:   'N/A',
      dob:          p.dob ? new Date(p.dob + 'T00:00:00').toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—',
      lastVisit:    '—',
      registeredOn: '—',
    };
    this.router.navigate(['/check-in'], { state: { patient } });
  }

  openPreview() {
    this.regSubmitted = true;
    // Mandatory personal fields must be filled before previewing / registering
    if (this.hasMandatoryErrors) { this.scrollToFirstError(); return; }
    if (this.duplicateNameDob) return;
    if (this.duplicateMobile && !this.allowDuplicateMobile) return;
    // ID proof is optional — but if a type is chosen, a valid number is required
    if (this.idProofType && !this.idProofNumber.trim()) return;
    if (this.idProofType && !this.validateIdNumber()) return;
    this.showPreview = true;
  }

  confirmRegister() {
    if (!this.dob) return;
    this.isLoading = true;
    this.errorMessage = '';

    // Use local date parts to avoid UTC timezone shift (e.g. IST is UTC+5:30)
    const d = this.dob;
    const dobStr = [
      d.getFullYear(),
      String(d.getMonth() + 1).padStart(2, '0'),
      String(d.getDate()).padStart(2, '0')
    ].join('-');

    const medParts: string[] = [];
    if (this.conditions.length)    medParts.push('Conditions: '  + this.conditions.join(', '));
    if (this.medications.length)   medParts.push('Medications: ' + this.medications.join(', '));
    if (this.prevSurgeries.trim()) medParts.push('Surgeries: '   + this.prevSurgeries.trim());
    if (this.notes.trim())         medParts.push('Notes: '       + this.notes.trim());

    const payload = {
      firstName:            this.firstName.trim(),
      lastName:             this.lastName.trim(),
      gender:               this.gender,
      dob:                  dobStr,
      age:                  this.ageYears,
      mobileNumber:         this.mobile.trim(),
      insuranceCompany:     this.insuranceCompany || undefined,
      medicalHistory:       medParts.length ? medParts.join(' | ') : undefined,
      allergies:            this.allergies.length ? this.allergies.join(', ') : undefined,
      allowDuplicateMobile: this.allowDuplicateMobile,
      idProofType:          this.idProofType,
      idProofNumber:        this.idProofNumber.trim(),
    };

    this.api.createPatient(payload).subscribe({
      next: (patient) => {
        this.registeredId        = patient.patientId;
        this.registeredNumericId = patient.id;
        this.isLoading   = false;
        this.showPreview = false;
        this.showSuccess = true;
        // Auto-navigate to check-in after 1.5 s — user can also click buttons manually
        this.checkInTimer = setTimeout(() => this.checkInNewPatient(), 1500);
      },
      error: (err) => {
        this.isLoading   = false;
        this.showPreview = false;
        this.errorMessage = err.error?.detail ?? 'Registration failed. Please try again.';
      }
    });
  }

  onSuccessClose() {
    if (this.checkInTimer) clearTimeout(this.checkInTimer);
    this.showSuccess = false;
    this.router.navigate(['/dashboard']);
  }

  checkInNewPatient() {
    if (this.checkInTimer) clearTimeout(this.checkInTimer);
    const dobStr = this.dob
      ? this.dob.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
      : '—';
    const patient = {
      numericId:    this.registeredNumericId,
      id:           this.registeredId,
      name:         this.fullName,
      initials:     this.initials,
      mobile:       this.mobile,
      age:          this.ageYears,
      gender:       this.gender || 'N/A',
      bloodGroup:   this.bloodGroup || 'N/A',
      dob:          dobStr,
      lastVisit:    '—',
      registeredOn: new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    };
    this.showSuccess = false;
    this.router.navigate(['/check-in'], { state: { patient } });
  }
}
