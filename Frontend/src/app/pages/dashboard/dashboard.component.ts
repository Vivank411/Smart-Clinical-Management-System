import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SelectModule } from 'primeng/select';
import { InputTextModule } from 'primeng/inputtext';
import { ApiService, ApiPatient, ApiDoctor, DashboardStats } from '../../services/api.service';

interface QueueEntry {
  _id:         number;   // internal: DB patient id, used for sort order
  num:         number;
  token:       string;
  patientName: string;
  patientId:   string;
  doctor:      string;
  status:      'In Consultation' | 'Waiting' | 'Completed';
  checkIn:     string;
}

interface DoctorRow {
  name:      string;
  specialty: string;
  status:    'Available' | 'In Consultation' | 'On Break' | 'Offline';
  from:      string;
  to:        string;
}

interface Stat {
  label:     string;
  value:     number;
  sub:       string;
  icon:      string;
  iconColor: string;
  iconBg:    string;
  highlight?: boolean;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, SelectModule, InputTextModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  selectedDoctor = 'All Doctors';
  doctorSearch   = '';

  today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  doctorFilterOptions: { label: string; value: string }[] = [
    { label: 'All Doctors', value: 'All Doctors' }
  ];

  stats: Stat[] = [
    { label: 'Total Patients',   value: 0, sub: 'Registered in system', icon: 'pi-users',        iconColor: '#3b82f6', iconBg: '#eff6ff'  },
    { label: 'Checked In',       value: 0, sub: 'Arrived today',         icon: 'pi-clock',        iconColor: '#10b981', iconBg: '#ecfdf5'  },
    { label: 'In Consultation',  value: 0, sub: 'Active sessions',       icon: 'pi-user',         iconColor: '#f59e0b', iconBg: '#fffbeb'  },
    { label: 'Completed',        value: 0, sub: 'Visits done',           icon: 'pi-check-square', iconColor: '#8b5cf6', iconBg: '#f5f3ff'  },
    { label: 'Doctors On-Duty',  value: 0, sub: 'Available now',         icon: 'pi-heart',        iconColor: '#fff',    iconBg: 'rgba(255,255,255,0.2)', highlight: true },
  ];

  queue:   QueueEntry[] = [];
  doctors: DoctorRow[]  = [];

  constructor(private api: ApiService) {}

  ngOnInit() {
    this.loadStats();
    this.loadQueue();
    this.loadDoctors();
  }

  private loadStats() {
    this.api.getDashboardStats().subscribe({
      next: (s: DashboardStats) => {
        this.stats[0].value = s.totalPatients;
        this.stats[1].value = s.checkedIn;
        this.stats[2].value = s.inConsultation;
        this.stats[3].value = s.completed;
        this.stats[4].value = s.doctorsOnDuty;
      },
      error: () => { /* stats stay at 0 */ }
    });
  }

  private loadQueue() {
    this.api.getPatients({ status: 'Checked-In', limit: 50 }).subscribe({
      next: (checkedInPatients) => {
        this.api.getPatients({ status: 'Consulted', limit: 50 }).subscribe({
          next: (consultedPatients) => {
            // Merge both groups, then assign sequential num
            const all = [
              ...checkedInPatients.map(p => this.toQueueEntry(p, 'Waiting')),
              ...consultedPatients.map(p => this.toQueueEntry(p, 'In Consultation')),
            ];
            // Sort by patient DB id (oldest check-in first), then renumber
            all.sort((a, b) => a._id - b._id);
            this.queue = all.map((e, i) => ({ ...e, num: i + 1 }));
          },
          error: () => {
            this.queue = checkedInPatients.map((p, i) => ({ ...this.toQueueEntry(p, 'Waiting'), num: i + 1 }));
          }
        });
      },
      error: () => { this.queue = []; }
    });
  }

  private toQueueEntry(p: ApiPatient, displayStatus: 'Waiting' | 'In Consultation' | 'Completed') {
    return {
      _id:         p.id,                                              // used for sorting only
      num:         0,                                                  // set after sort
      token:       p.queueToken ?? `Q-${String(p.id).padStart(3, '0')}`,
      patientName: p.name,
      patientId:   p.patientId,
      doctor:      p.doctor ?? '—',
      status:      displayStatus as QueueEntry['status'],
      checkIn:     p.checkinTime ?? '—',
    };
  }

  private loadDoctors() {
    this.api.getDoctors().subscribe({
      next: (docs: ApiDoctor[]) => {
        this.doctors = docs.map(d => ({
          name:      d.name,
          specialty: d.specialization,
          status:    'Available' as const,
          from:      '09:00 AM',
          to:        '05:00 PM',
        }));
        this.doctorFilterOptions = [
          { label: 'All Doctors', value: 'All Doctors' },
          ...docs.map(d => ({ label: d.name, value: d.name }))
        ];
      },
      error: () => { this.doctors = []; }
    });
  }

  get filteredDoctors(): DoctorRow[] {
    const q = this.doctorSearch.trim().toLowerCase();
    if (!q) return this.doctors;
    return this.doctors.filter(d =>
      d.name.toLowerCase().includes(q) || d.specialty.toLowerCase().includes(q)
    );
  }

  get filteredQueue(): QueueEntry[] {
    return this.selectedDoctor === 'All Doctors'
      ? this.queue
      : this.queue.filter(q => q.doctor === this.selectedDoctor);
  }

  statusBadgeClass(s: string) {
    return ({ 'In Consultation': 'badge--amber', 'Waiting': 'badge--blue', 'Completed': 'badge--green' } as Record<string, string>)[s] ?? '';
  }

  doctorBadgeClass(s: string) {
    return ({ 'Available': 'badge--green', 'In Consultation': 'badge--amber', 'On Break': 'badge--orange', 'Offline': 'badge--slate' } as Record<string, string>)[s] ?? '';
  }

  doctorInitials(name: string) {
    return name.replace('Dr. ', '').split(' ').map(w => w[0]).join('');
  }
}
