import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, AuditLogFull } from '../../services/api.service';

@Component({
  selector: 'app-admin-audit',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-audit.component.html',
  styleUrl: './admin-audit.component.scss',
})
export class AdminAuditComponent implements OnInit {
  logs: AuditLogFull[] = [];
  total   = 0;
  loading = false;

  page     = 1;
  pageSize = 10;

  search       = '';
  moduleFilter = '';
  actionFilter = '';
  statusFilter = '';

  readonly modules = [
    'Authentication', 'Consultation', 'Doctor Management', 'Patient Management',
    'Queue', 'Reports & Analytics', 'System Settings', 'User Management',
  ];
  readonly actions = [
    'Consultation Added', 'Data Exported', 'Doctor Added', 'Doctor Updated',
    'Failed Login', 'Login', 'Password Reset', 'Patient Check-in',
    'Patient Registered', 'Prescription Added', 'Record Deleted',
    'Report Generated', 'Settings Updated', 'User Created', 'User Disabled',
  ];

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading = true;
    this.api.getAuditLogsFull(this.page, this.pageSize, this.search, this.moduleFilter, this.actionFilter, this.statusFilter)
      .subscribe({
        next: res => { this.logs = res.logs; this.total = res.total; this.loading = false; },
        error: () => { this.loading = false; },
      });
  }

  onFilter(): void { this.page = 1; this.load(); }

  clearFilters(): void {
    this.search = ''; this.moduleFilter = ''; this.actionFilter = ''; this.statusFilter = '';
    this.onFilter();
  }

  setPage(n: number): void { if (n >= 1 && n <= this.totalPages) { this.page = n; this.load(); } }

  get totalPages(): number { return Math.ceil(this.total / this.pageSize); }
  get start(): number { return this.total ? (this.page - 1) * this.pageSize + 1 : 0; }
  get end(): number   { return Math.min(this.page * this.pageSize, this.total); }

  get pageNums(): (number | -1)[] {
    const nums: (number | -1)[] = [];
    const p = this.page, t = this.totalPages;
    if (t <= 7) { for (let i = 1; i <= t; i++) nums.push(i); return nums; }
    nums.push(1);
    if (p > 3) nums.push(-1);
    for (let i = Math.max(2, p - 1); i <= Math.min(t - 1, p + 1); i++) nums.push(i);
    if (p < t - 2) nums.push(-1);
    nums.push(t);
    return nums;
  }

  actionColor(type: string): string {
    const m: Record<string, string> = {
      create: '#0d6e6e', edit: '#3b82f6', checkin: '#f59e0b', login: '#0d9488',
      disable: '#e11d48', delete: '#e11d48', security: '#8b5cf6',
      export: '#0d6e6e', error: '#e11d48',
    };
    return m[type] ?? '#64748b';
  }

  actionIcon(type: string): string {
    const m: Record<string, string> = {
      create: 'pi-plus', edit: 'pi-pencil', checkin: 'pi-user', login: 'pi-sign-in',
      disable: 'pi-lock', delete: 'pi-trash', security: 'pi-key',
      export: 'pi-shield', error: 'pi-exclamation-triangle',
    };
    return m[type] ?? 'pi-circle';
  }

  actionBg(type: string): string {
    const m: Record<string, string> = {
      create: '#f0fdf4', edit: '#eff6ff', checkin: '#fffbeb', login: '#f0fdfa',
      disable: '#fff1f2', delete: '#fff1f2', security: '#f5f3ff',
      export: '#f0fdfa', error: '#fffbeb',
    };
    return m[type] ?? '#f8fafc';
  }
}
