import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-admin-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-settings.component.html',
  styleUrl: './admin-settings.component.scss',
})
export class AdminSettingsComponent {
  private readonly STORAGE_KEY = 'mc_admin_settings';

  activeSection = 'general';
  saveLoading   = false;
  showSaved     = false;

  sections = [
    { id: 'general',       icon: 'pi-cog',       label: 'General Settings' },
    { id: 'notifications', icon: 'pi-bell',      label: 'Notification Settings' },
    { id: 'appointments',  icon: 'pi-calendar',  label: 'Appointment Settings' },
  ];

  // ── Option lists ───────────────────────────────────────────────────────────
  readonly timeSlots = [
    '06:00 AM','07:00 AM','08:00 AM','09:00 AM','10:00 AM','11:00 AM',
    '12:00 PM','01:00 PM','02:00 PM','03:00 PM','04:00 PM','05:00 PM',
    '06:00 PM','07:00 PM','08:00 PM','09:00 PM',
  ];
  readonly weekDays = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  readonly smsProviders = ['Twilio', 'MSG91', 'AWS SNS', 'Custom Gateway'];

  // ── General ────────────────────────────────────────────────────────────────
  general = {
    systemName:          'MediClinic',
    systemTagline:       'Your Health, Our Priority',
    orgName:             'MediClinic Hospital',
    contactEmail:        'info@mediclinic.com',
    contactPhone:        '+91 98765 43210',
    timezone:            '(GMT+05:30) Asia/Kolkata',
    dateFormat:          'DD MMM, YYYY (19 Jun, 2026)',
    timeFormat:          '12 Hour (02:30 PM)',
    enableRegistration:  true,
    emailVerification:   true,   // permanently enabled — mandatory, not user-configurable
    maintenanceMode:     false,
  };

  // ── Email ──────────────────────────────────────────────────────────────────
  email = {
    enabled:         true,
    smtpHost:        'smtp.gmail.com',
    smtpPort:        '587',
    encryption:      'TLS',
    username:        '',
    password:        '',
    fromName:        'MediClinic',
    fromEmail:       'no-reply@mediclinic.com',
    replyTo:         'support@mediclinic.com',
    sendWelcome:     true,
    sendReset:       true,
    sendAppointment: true,
    testTo:          '',
  };
  testEmailStatus: '' | 'sending' | 'sent' | 'error' = '';

  // ── SMS ────────────────────────────────────────────────────────────────────
  sms = {
    enabled:       false,
    provider:      'Twilio',
    apiKey:        '',
    senderId:      'MEDCLN',
    reminders:     true,
    otp:           true,
    queueUpdates:  false,
    testTo:        '',
  };
  testSmsStatus: '' | 'sending' | 'sent' | 'error' = '';

  // ── Notifications ──────────────────────────────────────────────────────────
  notifications = {
    reminderLeadTime: '24 Hours',
    events: [
      { id: 'appt_new',    label: 'New Appointment Booked',   sub: 'When a patient is checked in or booked.',   inApp: true,  email: true,  sms: false },
      { id: 'appt_remind', label: 'Appointment Reminder',     sub: 'Reminder before an upcoming visit.',        inApp: true,  email: true,  sms: true  },
      { id: 'checkin',     label: 'Patient Check-In',         sub: 'When a patient checks in at reception.',    inApp: true,  email: false, sms: false },
      { id: 'rx_ready',    label: 'Prescription Ready',       sub: 'When a doctor issues an e-prescription.',   inApp: true,  email: true,  sms: false },
      { id: 'queue',       label: 'Queue / Token Update',     sub: 'When the patient\'s queue position moves.', inApp: true,  email: false, sms: true  },
      { id: 'account',     label: 'New User Account',         sub: 'When an account is created or reactivated.', inApp: true,  email: true,  sms: false },
      { id: 'system',      label: 'System Alerts',            sub: 'Errors, downtime and security warnings.',   inApp: true,  email: true,  sms: false },
    ],
  };

  // ── Appointments ───────────────────────────────────────────────────────────
  appointments = {
    defaultDuration:    '30',
    bufferTime:         '10',
    slotInterval:       '30',
    workStart:          '09:00 AM',
    workEnd:            '05:00 PM',
    workingDays:        { Mon: true, Tue: true, Wed: true, Thu: true, Fri: true, Sat: true, Sun: false } as Record<string, boolean>,
    maxAdvanceDays:     '30',
    maxPerSlot:         '1',
    allowOnlineBooking: true,
    autoConfirm:        false,
    allowCancellation:  true,
    cancellationWindow: '4',
  };

  overview = {
    version:        'v2.4.0',
    lastUpdated:    'Jun 10, 2026',
    totalUsers:     245,
    activeSessions: 12,
    dbSize:         '512 MB',
    storageUsed:    '2.4 GB / 20 GB',
  };

  // ── Backup ──────────────────────────────────────────────────────────────────
  backupLast  = 'Jun 19, 2026 02:30 AM';
  backupNext  = 'Jun 20, 2026 02:30 AM';
  isBackingUp = false;
  backupDone  = false;

  constructor() {
    this.loadSaved();
    this.general.emailVerification = true;   // enforce: always on, even if an old saved value disabled it
  }

  get activeSectionLabel(): string {
    return this.sections.find(s => s.id === this.activeSection)?.label ?? '';
  }

  // ── Appointment helpers ────────────────────────────────────────────────────
  toggleDay(day: string): void {
    this.appointments.workingDays[day] = !this.appointments.workingDays[day];
  }

  // ── Test actions (front-end validation + simulated send) ────────────────────
  sendTestEmail(): void {
    if (!this.email.testTo.trim() || !this.email.smtpHost.trim()) {
      this.testEmailStatus = 'error';
      return;
    }
    this.testEmailStatus = 'sending';
    setTimeout(() => { this.testEmailStatus = 'sent'; }, 900);
  }

  sendTestSms(): void {
    if (!this.sms.testTo.trim() || !this.sms.apiKey.trim()) {
      this.testSmsStatus = 'error';
      return;
    }
    this.testSmsStatus = 'sending';
    setTimeout(() => { this.testSmsStatus = 'sent'; }, 900);
  }

  // ── Persistence ────────────────────────────────────────────────────────────
  private loadSaved(): void {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (saved.general)       Object.assign(this.general, saved.general);
      if (saved.email)         Object.assign(this.email, saved.email);
      if (saved.sms)           Object.assign(this.sms, saved.sms);
      if (saved.appointments)  Object.assign(this.appointments, saved.appointments);
      if (saved.backup) {
        this.backupLast = saved.backup.last ?? this.backupLast;
        this.backupNext = saved.backup.next ?? this.backupNext;
      }
      if (saved.notifications) {
        this.notifications.reminderLeadTime = saved.notifications.reminderLeadTime ?? this.notifications.reminderLeadTime;
        if (Array.isArray(saved.notifications.events)) {
          for (const ev of saved.notifications.events) {
            const target = this.notifications.events.find(e => e.id === ev.id);
            if (target) { target.inApp = ev.inApp; target.email = ev.email; target.sms = ev.sms; }
          }
        }
      }
    } catch { /* ignore corrupt/unavailable storage */ }
  }

  private buildPayload() {
    return {
      general:       this.general,
      email:         this.email,
      sms:           this.sms,
      notifications: this.notifications,
      appointments:  this.appointments,
      backup:        { last: this.backupLast, next: this.backupNext },
    };
  }

  private persist(): void {
    try { localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.buildPayload())); }
    catch { /* storage unavailable */ }
  }

  saveChanges(): void {
    this.saveLoading = true;
    setTimeout(() => {
      this.persist();
      this.saveLoading = false;
      this.showSaved   = true;
      setTimeout(() => { this.showSaved = false; }, 3000);
    }, 600);
  }

  /** Toggles apply and persist immediately, with a brief confirmation. */
  toggleGeneral(key: 'enableRegistration' | 'maintenanceMode'): void {   // emailVerification is fixed on
    this.general[key] = !this.general[key];
    this.persist();
    this.showSaved = true;
    setTimeout(() => { this.showSaved = false; }, 2000);
  }

  // ── Backup ──────────────────────────────────────────────────────────────────
  private formatBackupTime(d: Date): string {
    const date = d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' });
    const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
    return `${date} ${time}`;
  }

  runBackup(): void {
    if (this.isBackingUp) return;
    this.isBackingUp = true;
    this.backupDone  = false;
    setTimeout(() => {
      const now  = new Date();
      const next = new Date(now.getTime() + 24 * 60 * 60 * 1000);
      this.backupLast = this.formatBackupTime(now);
      this.backupNext = this.formatBackupTime(next);
      this.persist();
      this.isBackingUp = false;
      this.backupDone  = true;
      setTimeout(() => { this.backupDone = false; }, 3500);
    }, 1600);
  }
}
