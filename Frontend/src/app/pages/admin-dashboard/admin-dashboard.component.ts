import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ApiService, AdminStats, PatientFlowDay,
  ConsultationStat, DoctorWorkloadItem, AuditLogItem,
} from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

interface DonutSegment {
  label: string;
  count: number;
  percentage: number;
  len: number;
  rotation: number;
  gap: number;
}

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.scss',
})
export class AdminDashboardComponent implements OnInit {
  today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  stats: AdminStats = {
    totalUsers: 0, activeDoctors: 0, totalPatients: 0,
    avgWaitingTime: 0, consultationsTotal: 0,
  };
  patientFlow: PatientFlowDay[]    = [];
  consultationStats: ConsultationStat[] = [];
  doctorWorkload: DoctorWorkloadItem[]  = [];
  auditLogs: AuditLogItem[]            = [];

  loading = true;
  readonly C = 282.74; // 2π × r(45)

  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit(): void {
    this.api.getAdminStats().subscribe({ next: s => (this.stats = s), error: () => {} });

    this.api.getPatientFlow().subscribe({
      next: d => { this.patientFlow = d; this.loading = false; },
      error: () => { this.loading = false; },
    });

    this.api.getConsultationStats().subscribe({ next: s => (this.consultationStats = s), error: () => {} });
    this.api.getDoctorWorkload().subscribe({ next: w => (this.doctorWorkload = w), error: () => {} });
    this.api.getAuditLogs().subscribe({ next: l => (this.auditLogs = l), error: () => {} });
  }

  get maxFlowCount(): number {
    return Math.max(...this.patientFlow.map(d => d.count), 1);
  }

  barHeight(count: number): number {
    return Math.round((count / this.maxFlowCount) * 100);
  }

  workloadWidth(item: DoctorWorkloadItem): number {
    return item.maxCount > 0 ? Math.round((item.count / item.maxCount) * 100) : 0;
  }

  get donutSegments(): DonutSegment[] {
    let cumulative = 0;
    return this.consultationStats.map(s => {
      const len = (s.percentage / 100) * this.C;
      const rotation = -90 + cumulative * 3.6;
      cumulative += s.percentage;
      return { label: s.label, count: s.count, percentage: s.percentage, len, rotation, gap: this.C - len };
    });
  }

  get totalConsultations(): number {
    return this.consultationStats.reduce((sum, s) => sum + s.count, 0);
  }

  segmentColor(label: string): string {
    const map: Record<string, string> = {
      Completed: '#0d6e6e',
      Pending:   '#f59e0b',
      Cancelled: '#ef4444',
    };
    return map[label] ?? '#94a3b8';
  }

  doctorInitials(name: string): string {
    return name.replace(/^Dr\.?\s*/i, '').split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
  }

  actionIcon(action: string): string {
    const map: Record<string, string> = {
      'Prescription Added': 'pi-file-edit',
      'Consultation Added': 'pi-heart',
      'Patient Check-in':   'pi-sign-in',
      'User Created':        'pi-user-plus',
      'Doctor Updated':      'pi-pencil',
      'Login':               'pi-lock-open',
    };
    return map[action] ?? 'pi-circle-fill';
  }

  moduleTag(module: string): string {
    const map: Record<string, string> = {
      'Consultation':     'tag--teal',
      'Queue':            'tag--blue',
      'User Management':  'tag--purple',
      'Authentication':   'tag--amber',
      'Doctor Management':'tag--green',
    };
    return map[module] ?? 'tag--slate';
  }
}
