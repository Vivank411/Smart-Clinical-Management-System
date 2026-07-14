import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ApiService, PatientFlowDay, ConsultationStat, DoctorWorkloadItem,
  WaitingTimeDay, DepartmentStat, PeakHour, WeeklySummary
} from '../../services/api.service';
import { forkJoin } from 'rxjs';

@Component({
  selector: 'app-admin-reports',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-reports.component.html',
  styleUrl: './admin-reports.component.scss',
})
export class AdminReportsComponent implements OnInit {
  loading = true;

  patientFlow: PatientFlowDay[]         = [];
  waitingTime: WaitingTimeDay[]         = [];
  consultationStats: ConsultationStat[] = [];
  doctorWorkload: DoctorWorkloadItem[]  = [];
  departmentStats: DepartmentStat[]     = [];
  peakHours: PeakHour[]                 = [];
  summary: WeeklySummary = {
    totalPatients: 0, totalConsultations: 0, avgWaitingTime: 0, cancelledConsultations: 0,
    patientsChange: 0, consultationsChange: 0, waitingTimeChange: 0, cancelledChange: 0,
  };

  selectedRange = '7';

  readonly CIRC = 282.74;
  readonly CONSULT_COLORS = ['#0d6e6e', '#f59e0b', '#ef4444'];
  readonly DEPT_COLORS    = ['#0d6e6e', '#f59e0b', '#3b82f6', '#8b5cf6', '#94a3b8'];

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); }

  get rangeDays(): number { return Number(this.selectedRange); }

  get dateRangeLabel(): string {
    const today = new Date();
    const from  = new Date(today);
    from.setDate(today.getDate() - this.rangeDays + 1);
    const fmt = (d: Date) =>
      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    return `${fmt(from)} – ${fmt(today)}`;
  }

  onRangeChange(): void { this.load(); }

  load(): void {
    this.loading = true;
    const days = this.rangeDays;
    forkJoin({
      patientFlow:       this.api.getPatientFlow(days),
      waitingTime:       this.api.getWaitingTime(days),
      consultationStats: this.api.getConsultationStats(),
      doctorWorkload:    this.api.getDoctorWorkload(),
      departmentStats:   this.api.getDepartmentStats(),
      peakHours:         this.api.getPeakHours(),
      summary:           this.api.getWeeklySummary(),
    }).subscribe({
      next: d => {
        this.patientFlow       = d.patientFlow;
        this.waitingTime       = d.waitingTime;
        this.consultationStats = d.consultationStats;
        this.doctorWorkload    = d.doctorWorkload;
        this.departmentStats   = d.departmentStats;
        this.peakHours         = d.peakHours;
        this.summary           = d.summary;
        this.loading           = false;
      },
      error: () => { this.loading = false; },
    });
  }

  // ── Bar chart ──────────────────────────────────────────────────────────────
  get maxFlow(): number { return Math.max(...this.patientFlow.map(d => d.count), 1); }

  barH(count: number): number {
    return Math.max(count > 0 ? 4 : 0, Math.round((count / this.maxFlow) * 100));
  }

  get barYLabels(): number[] {
    const max  = this.maxFlow;
    const step = Math.max(1, Math.ceil(max / 4));
    return [step * 4, step * 3, step * 2, step, 0];
  }

  // ── SVG line chart ─────────────────────────────────────────────────────────
  private calcPts(values: number[], w: number, h: number): { x: number; y: number }[] {
    if (values.length < 2) return [];
    const min   = Math.min(...values);
    const max   = Math.max(...values);
    const range = max - min || 1;
    const step  = w / (values.length - 1);
    return values.map((v, i) => ({
      x: +(i * step).toFixed(1),
      y: +(h * (1 - (v - min) / range)).toFixed(1),
    }));
  }

  svgPoints(values: number[], w = 400, h = 80): string {
    return this.calcPts(values, w, h).map(p => `${p.x},${p.y}`).join(' ');
  }

  svgDots(values: number[], w = 400, h = 80): { x: number; y: number; val: number }[] {
    return this.calcPts(values, w, h).map((p, i) => ({ ...p, val: values[i] }));
  }

  get waitingPts()  { return this.svgPoints(this.waitingTime.map(d => d.mins)); }
  get waitingDots() { return this.svgDots(this.waitingTime.map(d => d.mins)); }
  get peakPts()     { return this.svgPoints(this.peakHours.map(d => d.mins)); }
  get peakDots()    { return this.svgDots(this.peakHours.map(d => d.mins)); }

  get maxWaiting(): number { return Math.max(...this.waitingTime.map(d => d.mins), 1); }
  get waitingYLabels(): number[] {
    const max  = this.maxWaiting;
    const step = Math.max(1, Math.ceil(max / 4));
    return [step * 4, step * 3, step * 2, step, 0];
  }

  get maxPeak(): number { return Math.max(...this.peakHours.map(d => d.mins), 1); }
  get peakYLabels(): number[] {
    const max  = this.maxPeak;
    const step = Math.max(1, Math.ceil(max / 3));
    return [step * 3, step * 2, step, 0];
  }

  // ── Donut ──────────────────────────────────────────────────────────────────
  donutSegs(items: { percentage: number }[], colors: string[]) {
    let cum = 0;
    return items.map((s, i) => {
      const pct  = s.percentage || 0;
      const dash = +((pct / 100) * this.CIRC).toFixed(2);
      const gap  = +(this.CIRC - dash).toFixed(2);
      const rot  = -90 + cum * 3.6;
      cum += pct;
      return { dash: `${dash} ${gap}`, rot, color: colors[i % colors.length] };
    });
  }

  get consultSegs() { return this.donutSegs(this.consultationStats, this.CONSULT_COLORS); }
  get deptSegs()    { return this.donutSegs(this.departmentStats,   this.DEPT_COLORS); }

  // ── Workload bar ───────────────────────────────────────────────────────────
  get maxWorkload(): number { return Math.max(...this.doctorWorkload.map(d => d.count), 1); }
  workW(count: number): number {
    return Math.max(count > 0 ? 4 : 0, Math.round((count / this.maxWorkload) * 100));
  }

  // ── Trend helpers ──────────────────────────────────────────────────────────
  trendClass(val: number, invertGood = false): string {
    if (val === 0) return 'trend-neutral';
    const positive = invertGood ? val < 0 : val > 0;
    return positive ? 'trend-up' : 'trend-down';
  }
  trendIcon(val: number, invertGood = false): string {
    if (val === 0) return 'pi-minus';
    const positive = invertGood ? val < 0 : val > 0;
    return positive ? 'pi-arrow-up' : 'pi-arrow-down';
  }

  // ── Exports ────────────────────────────────────────────────────────────────
  exportCSV(): void {
    const nl = '\n';
    const rows: string[] = [
      `"MedClinic Analytics Report — ${this.dateRangeLabel}"`,
      '',
      '"DAILY PATIENT FLOW"',
      '"Day","Patients"',
      ...this.patientFlow.map(d => `"${d.day}",${d.count}`),
      '',
      '"AVERAGE WAITING TIME"',
      '"Day","Minutes"',
      ...this.waitingTime.map(d => `"${d.day}",${d.mins}`),
      '',
      '"CONSULTATION STATUS"',
      '"Status","Count","%"',
      ...this.consultationStats.map(s => `"${s.label}",${s.count},${s.percentage}`),
      '',
      '"BY DEPARTMENT"',
      '"Department","Count","%"',
      ...this.departmentStats.map(d => `"${d.department}",${d.count},${d.percentage}`),
      '',
      '"PEAK HOURS"',
      '"Hour","Avg Wait (mins)"',
      ...this.peakHours.map(h => `"${h.hour}",${h.mins}`),
      '',
      '"DOCTOR WORKLOAD"',
      '"Doctor","Patients"',
      ...this.doctorWorkload.map(d => `"${d.name}",${d.count}`),
      '',
      '"SUMMARY"',
      '"Metric","Value"',
      `"Total Patients",${this.summary.totalPatients}`,
      `"Total Consultations",${this.summary.totalConsultations}`,
      `"Avg Waiting Time (mins)",${this.summary.avgWaitingTime}`,
    ];
    const blob = new Blob([rows.join(nl)], { type: 'text/csv;charset=utf-8;' });
    this._download(blob, `medclinic-report-${this._today()}.csv`);
  }

  exportExcel(): void {
    const html = `<html xmlns:o="urn:schemas-microsoft-com:office:office"
      xmlns:x="urn:schemas-microsoft-com:office:excel">
<head><meta charset="utf-8"><title>MedClinic Report</title></head>
<body>
<table border="1" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px">
  <tr><th colspan="3" style="background:#0d6e6e;color:#fff;font-size:14px;padding:10px">
    MedClinic Analytics — ${this.dateRangeLabel}</th></tr>
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="2" style="background:#e2e8f0;padding:6px">Daily Patient Flow</th></tr>
  <tr><th style="padding:5px">Day</th><th style="padding:5px">Patients</th></tr>
  ${this.patientFlow.map(d => `<tr><td style="padding:4px">${d.day}</td><td style="padding:4px;text-align:right">${d.count}</td></tr>`).join('')}
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="3" style="background:#e2e8f0;padding:6px">Consultation Statistics</th></tr>
  <tr><th>Status</th><th>Count</th><th>%</th></tr>
  ${this.consultationStats.map(s => `<tr><td style="padding:4px">${s.label}</td><td style="padding:4px;text-align:right">${s.count}</td><td style="padding:4px;text-align:right">${s.percentage}%</td></tr>`).join('')}
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="3" style="background:#e2e8f0;padding:6px">Consultations by Department</th></tr>
  <tr><th>Department</th><th>Count</th><th>%</th></tr>
  ${this.departmentStats.map(d => `<tr><td style="padding:4px">${d.department}</td><td style="padding:4px;text-align:right">${d.count}</td><td style="padding:4px;text-align:right">${d.percentage}%</td></tr>`).join('')}
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="2" style="background:#e2e8f0;padding:6px">Doctor Workload</th></tr>
  <tr><th>Doctor</th><th>Patients</th></tr>
  ${this.doctorWorkload.map(d => `<tr><td style="padding:4px">${d.name}</td><td style="padding:4px;text-align:right">${d.count}</td></tr>`).join('')}
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="2" style="background:#e2e8f0;padding:6px">Summary</th></tr>
  <tr><td style="padding:4px">Total Patients</td><td style="padding:4px;text-align:right">${this.summary.totalPatients}</td></tr>
  <tr><td style="padding:4px">Total Consultations</td><td style="padding:4px;text-align:right">${this.summary.totalConsultations}</td></tr>
  <tr><td style="padding:4px">Avg Waiting Time</td><td style="padding:4px;text-align:right">${this.summary.avgWaitingTime} mins</td></tr>
</table>
</body></html>`;
    const blob = new Blob([html], { type: 'application/vnd.ms-excel;charset=utf-8;' });
    this._download(blob, `medclinic-report-${this._today()}.xls`);
  }

  exportPDF(): void { window.print(); }

  private _today(): string { return new Date().toISOString().slice(0, 10); }

  private _download(blob: Blob, name: string): void {
    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  }
}
