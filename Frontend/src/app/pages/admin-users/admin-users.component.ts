import { Component, OnInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, AdminUserItem, AdminUserCreate } from '../../services/api.service';

interface UserForm {
  firstName: string; lastName: string; email: string;
  phone: string; role: string; specialization: string; sendWelcomeEmail: boolean;
}

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-users.component.html',
  styleUrl: './admin-users.component.scss',
})
export class AdminUsersComponent implements OnInit {
  users: AdminUserItem[] = [];
  loading = false;

  searchQuery = '';
  roleFilter  = '';
  page        = 1;
  readonly pageSize = 10;

  // ── Create modal ────────────────────────────────────────────────────────────
  showCreate    = false;
  createLoading = false;
  createError   = '';
  form: UserForm = this.blankForm();

  // ── Success toast (shared: create / reactivation) ────────────────────────────
  showSuccess  = false;
  successTitle = '';
  successMsg   = '';
  successEmail = '';
  private toastTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Edit modal ──────────────────────────────────────────────────────────────
  showEdit    = false;
  editTarget: AdminUserItem | null = null;
  editForm: UserForm = this.blankForm();
  editLoading = false;
  editError   = '';

  // ── Delete confirm ──────────────────────────────────────────────────────────
  showDelete    = false;
  deleteTarget: AdminUserItem | null = null;
  deleteLoading = false;

  // ── Three-dots dropdown ──────────────────────────────────────────────────
  openMenuId: number | null = null;

  readonly roleOptions = ['Doctor', 'Junior Doctor', 'Receptionist', 'Admin'];
  readonly Math = Math;

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); }

  @HostListener('document:click')
  onDocClick() { this.openMenuId = null; }

  load(): void {
    this.loading = true;
    this.api.getAdminUsers().subscribe({
      next: u => { this.users = u; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  get filtered(): AdminUserItem[] {
    let list = this.users;
    if (this.roleFilter) list = list.filter(u => u.role === this.roleFilter);
    const q = this.searchQuery.trim().toLowerCase();
    if (q) list = list.filter(u => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));
    return list;
  }

  get paginated(): AdminUserItem[] {
    return this.filtered.slice((this.page - 1) * this.pageSize, this.page * this.pageSize);
  }

  get totalPages(): number { return Math.max(1, Math.ceil(this.filtered.length / this.pageSize)); }
  get pageNums(): number[] { return Array.from({ length: this.totalPages }, (_, i) => i + 1); }
  onSearch(): void { this.page = 1; }

  // ── Create ───────────────────────────────────────────────────────────────
  openCreate(): void {
    this.form = this.blankForm();
    this.createError = '';
    this.showCreate  = true;
    this.showSuccess = false;
  }

  closeCreate(): void { this.showCreate = false; }

  submitCreate(): void {
    if (!this.form.firstName.trim() || !this.form.lastName.trim() || !this.form.email.trim()) {
      this.createError = 'First name, last name and email are required.';
      return;
    }
    this.createLoading = true;
    this.createError   = '';
    this.api.createAdminUser({
      firstName: this.form.firstName.trim(), lastName: this.form.lastName.trim(),
      email: this.form.email.trim(), phone: this.form.phone || undefined,
      role: this.form.role, specialization: this.form.specialization || undefined,
      sendWelcomeEmail: this.form.sendWelcomeEmail,
    }).subscribe({
      next: user => {
        this.createLoading = false; this.showCreate = false;
        this.showToast('User Created Successfully!', 'Welcome email sent with a temporary password to', user.email);
        this.load();
      },
      error: err => {
        this.createLoading = false;
        this.createError   = err.error?.detail ?? 'Failed to create user.';
      },
    });
  }

  // ── Edit ─────────────────────────────────────────────────────────────────
  openEdit(user: AdminUserItem, event: Event): void {
    event.stopPropagation();
    this.openMenuId = null;
    this.editTarget = user;
    const parts = user.name.split(' ');
    const first = parts[0];
    const last  = parts.slice(1).join(' ');
    this.editForm = {
      firstName: first, lastName: last,
      email: user.email, phone: user.phone ?? '',
      role: user.role, specialization: user.specialization ?? '',
      sendWelcomeEmail: false,
    };
    this.editError  = '';
    this.showEdit   = true;
  }

  closeEdit(): void { this.showEdit = false; this.editTarget = null; }

  submitEdit(): void {
    if (!this.editForm.firstName.trim() || !this.editForm.email.trim()) {
      this.editError = 'Name and email are required.';
      return;
    }
    if (!this.editTarget) return;
    this.editLoading = true;
    this.editError   = '';
    this.api.updateAdminUser(this.editTarget.source, this.editTarget.id, {
      firstName:      this.editForm.firstName.trim(),
      lastName:       this.editForm.lastName.trim(),
      email:          this.editForm.email.trim(),
      phone:          this.editForm.phone || undefined,
      role:           this.editForm.role,
      specialization: this.editForm.specialization || undefined,
    }).subscribe({
      next: updated => {
        const idx = this.users.findIndex(u => u.id === updated.id && u.source === updated.source);
        if (idx !== -1) this.users[idx] = updated;
        this.editLoading = false;
        this.closeEdit();
      },
      error: err => {
        this.editLoading = false;
        this.editError   = err.error?.detail ?? 'Failed to update user.';
      },
    });
  }

  // ── Delete ────────────────────────────────────────────────────────────────
  openDelete(user: AdminUserItem, event: Event): void {
    event.stopPropagation();
    this.openMenuId  = null;
    this.deleteTarget = user;
    this.showDelete   = true;
  }

  closeDelete(): void { this.showDelete = false; this.deleteTarget = null; }

  confirmDelete(): void {
    if (!this.deleteTarget) return;
    this.deleteLoading = true;
    this.api.deleteAdminUser(this.deleteTarget.source, this.deleteTarget.id).subscribe({
      next: () => {
        this.users = this.users.filter(
          u => !(u.id === this.deleteTarget!.id && u.source === this.deleteTarget!.source)
        );
        this.deleteLoading = false;
        this.closeDelete();
      },
      error: () => { this.deleteLoading = false; },
    });
  }

  // ── Three-dots menu ───────────────────────────────────────────────────────
  toggleMenu(id: number, event: Event): void {
    event.stopPropagation();
    this.openMenuId = this.openMenuId === id ? null : id;
  }

  // ── Toggle Status ─────────────────────────────────────────────────────────
  // Reactivating a user generates a fresh temporary password on the server and
  // emails it to them; they must set their own password on next login.
  toggleStatus(user: AdminUserItem, event: Event): void {
    event.stopPropagation();
    this.api.toggleUserStatus(user.source, user.id).subscribe({
      next: res => {
        user.isActive = res.isActive;
        if (res.isActive) {
          this.showToast(
            'User Reactivated',
            res.passwordEmailed
              ? 'A new temporary password has been emailed to'
              : 'A new temporary password was generated for',
            user.email,
          );
        }
      },
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  private blankForm(): UserForm {
    return { firstName: '', lastName: '', email: '', phone: '', role: 'Receptionist', specialization: '', sendWelcomeEmail: true };
  }

  private showToast(title: string, msg: string, email: string): void {
    this.successTitle = title;
    this.successMsg   = msg;
    this.successEmail = email;
    this.showSuccess  = true;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => (this.showSuccess = false), 6000);
  }

  initials(name: string): string {
    return name.replace(/^Dr\.?\s*/i, '').split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
  }

  avatarBg(name: string): string {
    const palette = ['#0d6e6e','#3b82f6','#8b5cf6','#f59e0b','#10b981','#ef4444','#0891b2'];
    return palette[name.charCodeAt(0) % palette.length];
  }

  roleBadge(role: string): string {
    return ({ Doctor: 'rb--blue', 'Junior Doctor': 'rb--teal', Receptionist: 'rb--purple', Admin: 'rb--amber' } as Record<string,string>)[role] ?? 'rb--slate';
  }
}
