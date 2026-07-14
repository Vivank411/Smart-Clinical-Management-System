import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ApiService, ApiPatient } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-doctor-queue',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './doctor-queue.component.html',
  styleUrl: './doctor-queue.component.scss'
})
export class DoctorQueueComponent implements OnInit, OnDestroy {
  queuePatients: ApiPatient[] = [];  // Checked-In only → shown in table
  allPatients:   ApiPatient[] = [];  // all → for stats

  isLoading   = false;
  lastRefresh = '';

  private refreshTimer: ReturnType<typeof setInterval> | null = null;

  readonly today = new Date().toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  });

  constructor(public auth: AuthService, private api: ApiService, private router: Router) {}

  ngOnInit() {
    this.loadQueue();
    this.refreshTimer = setInterval(() => this.loadQueue(true), 30_000);
  }

  ngOnDestroy() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
  }

  loadQueue(silent = false) {
    if (!silent) this.isLoading = true;

    const drName = this.auth.getUser()?.name ?? '';
    this.api.getPatients({ status: 'Checked-In', doctor: drName, limit: 500 }).subscribe({
      next: (pts) => {
        this.queuePatients = pts.sort((a, b) => {
          const n = (t: string | null) => parseInt(t?.replace(/\D/g, '') || '9999');
          return n(a.queueToken) - n(b.queueToken);
        });
        if (!silent) this.isLoading = false;
        this.lastRefresh = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
      },
      error: () => { if (!silent) this.isLoading = false; }
    });

    this.api.getPatients({ doctor: drName, limit: 1000 }).subscribe({
      next: (pts) => { this.allPatients = pts; }
    });
  }

  // Only patients whose status was set to 'Consulted' via POST /consultations (real doctor flow)
  get consultedCount() {
    return this.allPatients.filter(p => p.status === 'Consulted').length;
  }

  // Patients who also had a prescription written (POST /prescriptions sets status → Completed)
  get completedCount() {
    return this.allPatients.filter(p => p.status === 'Completed').length;
  }

  initials(name: string): string {
    return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
  }

  allergyList(p: ApiPatient): string[] {
    return p.allergies?.split(',').map(s => s.trim()).filter(Boolean) ?? [];
  }

  startConsultation(p: ApiPatient) {
    this.router.navigate(['/doctor-consultation', p.id]);
  }
}
