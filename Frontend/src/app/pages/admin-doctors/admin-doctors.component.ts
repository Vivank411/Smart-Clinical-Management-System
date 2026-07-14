import { Component, OnInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, ApiDoctor, DoctorStats, AdminDoctorCreate, DoctorUpdate } from '../../services/api.service';

@Component({
  selector: 'app-admin-doctors',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-doctors.component.html',
  styleUrl: './admin-doctors.component.scss',
})
export class AdminDoctorsComponent implements OnInit {
  doctors: ApiDoctor[] = [];
  stats: DoctorStats = { total: 0, active: 0, inactive: 0, specializations: 0 };
  loading     = false;
  searchQuery = '';
  selected: ApiDoctor | null = null;

  // Add modal
  showAdd    = false;
  addLoading = false;
  addError   = '';
  addForm: AdminDoctorCreate = this.blankAdd();

  // Edit modal
  showEdit    = false;
  editLoading = false;
  editError   = '';
  editForm: DoctorUpdate & { id: number } = { id: 0, name: '', specialization: '', email: '', phone: '', role: '', available_from: '09:00 AM', available_to: '05:00 PM' };

  // Row actions (kebab) menu
  menuOpenId: number | null = null;

  // Delete confirmation
  showDelete    = false;
  deleteLoading = false;
  deleteError   = '';
  deleteTarget: ApiDoctor | null = null;

  readonly roleOptions = ['Doctor', 'Junior Doctor'];
  readonly specOptions = ['General Medicine','Cardiology','Dermatology','Orthopedic','ENT','Neurology','Pediatrics','Ophthalmology','Gynecology'];
  readonly availDays   = ['Mon','Tue','Wed','Thu','Fri','Sat'];
  readonly timeSlots   = [
    '06:00 AM','07:00 AM','08:00 AM','09:00 AM','10:00 AM','11:00 AM',
    '12:00 PM','01:00 PM','02:00 PM','03:00 PM','04:00 PM','05:00 PM',
    '06:00 PM','07:00 PM','08:00 PM','09:00 PM',
  ];

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); this.loadStats(); }

  load(): void {
    this.loading = true;
    this.api.getDoctors().subscribe({
      next: d => {
        this.doctors = d;
        this.loading = false;
        if (this.selected) {
          this.selected = d.find(x => x.id === this.selected!.id) ?? null;
        }
      },
      error: () => { this.loading = false; },
    });
  }

  loadStats(): void {
    this.api.getDoctorStats().subscribe({ next: s => (this.stats = s), error: () => {} });
  }

  get filtered(): ApiDoctor[] {
    const q = this.searchQuery.trim().toLowerCase();
    if (!q) return this.doctors;
    return this.doctors.filter(d =>
      d.name.toLowerCase().includes(q) || d.specialization.toLowerCase().includes(q)
    );
  }

  selectDoctor(d: ApiDoctor): void {
    this.selected = this.selected?.id === d.id ? null : d;
  }

  toggleStatus(d: ApiDoctor, event: Event): void {
    event.stopPropagation();
    this.api.toggleDoctorStatus(d.id).subscribe({
      next: res => {
        d.is_active = res.isActive;
        if (this.selected?.id === d.id) this.selected = { ...d, is_active: res.isActive };
        this.loadStats();
      },
    });
  }

  // ── Row actions (kebab) menu ─────────────────────────────────────────────────
  toggleMenu(d: ApiDoctor, event: Event): void {
    event.stopPropagation();
    this.menuOpenId = this.menuOpenId === d.id ? null : d.id;
  }

  closeMenu(): void { this.menuOpenId = null; }

  @HostListener('document:click')
  onDocumentClick(): void { this.closeMenu(); }

  // ── Delete Doctor ────────────────────────────────────────────────────────────
  openDelete(d: ApiDoctor, event: Event): void {
    event.stopPropagation();
    this.closeMenu();
    this.deleteTarget  = d;
    this.deleteError   = '';
    this.showDelete    = true;
  }

  closeDelete(): void {
    this.showDelete   = false;
    this.deleteTarget = null;
  }

  confirmDelete(): void {
    if (!this.deleteTarget) return;
    const target = this.deleteTarget;
    this.deleteLoading = true;
    this.deleteError   = '';
    this.api.deleteAdminDoctor(target.id).subscribe({
      next: () => {
        this.deleteLoading = false;
        this.showDelete    = false;
        this.deleteTarget  = null;
        if (this.selected?.id === target.id) this.selected = null;
        this.load();
        this.loadStats();
      },
      error: err => {
        this.deleteLoading = false;
        this.deleteError   = err.error?.detail ?? 'Failed to delete doctor.';
      },
    });
  }

  // ── Add Doctor ──────────────────────────────────────────────────────────────
  openAdd(): void {
    this.addForm  = this.blankAdd();
    this.addError = '';
    this.showAdd  = true;
  }

  private blankAdd(): AdminDoctorCreate {
    return { name: '', specialization: '', email: '', phone: '', role: 'Doctor', available_from: '09:00 AM', available_to: '05:00 PM' };
  }

  closeAdd(): void { this.showAdd = false; }

  submitAdd(): void {
    if (!this.addForm.name.trim() || !this.addForm.specialization.trim()) {
      this.addError = 'Name and specialization are required.';
      return;
    }
    this.addLoading = true;
    this.addError   = '';
    this.api.createAdminDoctor(this.addForm).subscribe({
      next: () => { this.addLoading = false; this.showAdd = false; this.load(); this.loadStats(); },
      error: err => { this.addLoading = false; this.addError = err.error?.detail ?? 'Failed to create doctor.'; },
    });
  }

  // ── Edit Doctor ─────────────────────────────────────────────────────────────
  openEdit(d: ApiDoctor, event: Event): void {
    event.stopPropagation();
    this.editForm = {
      id: d.id,
      name: d.name,
      specialization: d.specialization,
      email: d.email ?? '',
      phone: d.phone ?? '',
      role: d.role,
      available_from: d.available_from ?? '09:00 AM',
      available_to:   d.available_to   ?? '05:00 PM',
    };
    this.editError = '';
    this.showEdit  = true;
  }

  closeEdit(): void { this.showEdit = false; }

  submitEdit(): void {
    if (!this.editForm.name?.trim() || !this.editForm.specialization?.trim()) {
      this.editError = 'Name and specialization are required.';
      return;
    }
    this.editLoading = true;
    this.editError   = '';
    const { id, ...payload } = this.editForm;
    this.api.updateAdminDoctor(id, payload).subscribe({
      next: () => { this.editLoading = false; this.showEdit = false; this.load(); this.loadStats(); },
      error: err => { this.editLoading = false; this.editError = err.error?.detail ?? 'Failed to update doctor.'; },
    });
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────
  initials(name: string): string {
    return name.replace(/^Dr\.?\s*/i, '').split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
  }

  avatarBg(name: string): string {
    const p = ['#0d6e6e','#3b82f6','#8b5cf6','#f59e0b','#10b981','#0891b2'];
    return p[name.charCodeAt(0) % p.length];
  }

  specBadge(spec: string): string {
    const map: Record<string,string> = {
      'Cardiology':'sb--red','Dermatology':'sb--pink','Orthopedic':'sb--orange',
      'ENT':'sb--purple','Neurology':'sb--blue','Pediatrics':'sb--teal',
      'Ophthalmology':'sb--indigo','Gynecology':'sb--rose',
    };
    return map[spec] ?? 'sb--slate';
  }
}
