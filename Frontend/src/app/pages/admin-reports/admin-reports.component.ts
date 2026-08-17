import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ApiService, PatientFlowDay, ConsultationStat, DoctorWorkloadItem,
  WaitingTimeDay, DepartmentStat, PeakHour, WeeklySummary,
  PaymentSummary, RevenueDay, TopPayer
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
    totalPatients: 0, patientsCheckedIn: 0, totalConsultations: 0,
    avgWaitingTime: 0, cancelledConsultations: 0,
    patientsChange: 0, consultationsChange: 0, waitingTimeChange: 0, cancelledChange: 0,
  };

  payments: PaymentSummary = {
    totalCollected: 0, transactionCount: 0, payingPatients: 0, averagePerPatient: 0,
    collectedChange: 0, outstandingVisits: 0, byMethod: [],
  };
  revenueFlow: RevenueDay[] = [];
  topPayers: TopPayer[]     = [];

  selectedRange = '7';

  readonly CIRC = 282.74;
  readonly CONSULT_COLORS = ['#0d6e6e', '#f59e0b', '#ef4444'];
  readonly DEPT_COLORS    = ['#0d6e6e', '#f59e0b', '#3b82f6', '#8b5cf6', '#94a3b8'];
  readonly METHOD_COLORS: Record<string, string> = {
    qr: '#8b5cf6', card: '#3b82f6', cash: '#16a34a',
  };

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); }

  get rangeDays(): number { return Number(this.selectedRange); }

  get dateRangeLabel(): string {
    const fmt = (d: Date) =>
      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    const today = new Date();
    if (this.rangeDays === 1) return `${fmt(today)} (Today)`;
    const from = new Date(today);
    from.setDate(today.getDate() - this.rangeDays + 1);
    return `${fmt(from)} – ${fmt(today)}`;
  }

  /** Label for the "vs previous period" comparisons on the summary cards. */
  get comparisonLabel(): string {
    return this.rangeDays === 1 ? 'vs yesterday' : `vs previous ${this.rangeDays} days`;
  }

  onRangeChange(): void { this.load(); }

  load(): void {
    this.loading = true;
    // Every panel is scoped to the same window so the figures agree.
    const days = this.rangeDays;
    forkJoin({
      patientFlow:       this.api.getPatientFlow(days),
      waitingTime:       this.api.getWaitingTime(days),
      consultationStats: this.api.getConsultationStats(days),
      doctorWorkload:    this.api.getDoctorWorkload(days),
      departmentStats:   this.api.getDepartmentStats(days),
      peakHours:         this.api.getPeakHours(days),
      summary:           this.api.getWeeklySummary(days),
      payments:          this.api.getPaymentSummary(days),
      revenueFlow:       this.api.getRevenueFlow(days),
      topPayers:         this.api.getTopPayers(days),
    }).subscribe({
      next: d => {
        this.patientFlow       = d.patientFlow;
        this.waitingTime       = d.waitingTime;
        this.consultationStats = d.consultationStats;
        this.doctorWorkload    = d.doctorWorkload;
        this.departmentStats   = d.departmentStats;
        this.peakHours         = d.peakHours;
        this.summary           = d.summary;
        this.payments          = d.payments;
        this.revenueFlow       = d.revenueFlow;
        this.topPayers         = d.topPayers;
        this.loading           = false;
      },
      error: () => { this.loading = false; },
    });
  }

  // ── Axis scaling ───────────────────────────────────────────────────────────
  // Every chart is drawn against the axis it displays, from a zero baseline.
  // Scaling to the data's own min/max instead made a value of 1 fill a 0–4
  // axis, and made the smallest point in a series look like zero.

  /** Top gridline value: the axis is 0..this, in `divisions` equal steps. */
  private axisTop(values: number[], divisions: number): number {
    const max  = Math.max(...values, 0);
    const step = Math.max(1, Math.ceil(max / divisions));
    return step * divisions;
  }

  private axisLabels(top: number, divisions: number): number[] {
    const step = top / divisions;
    return Array.from({ length: divisions + 1 }, (_, i) => +(top - i * step).toFixed(1));
  }

  // ── Bar chart ──────────────────────────────────────────────────────────────
  get flowAxisTop(): number { return this.axisTop(this.patientFlow.map(d => d.count), 4); }
  get barYLabels(): number[] { return this.axisLabels(this.flowAxisTop, 4); }

  barH(count: number): number {
    if (count <= 0) return 0;
    // Floor of 2% so a non-zero day is still visible against a tall axis.
    return Math.max(2, Math.round((count / this.flowAxisTop) * 100));
  }

  // ── SVG line chart ─────────────────────────────────────────────────────────
  private calcPts(values: number[], top: number, w: number, h: number): { x: number; y: number }[] {
    if (!values.length) return [];
    const y = (v: number) => +(h * (1 - v / (top || 1))).toFixed(1);
    // A single-day range still has to plot — centre the lone point.
    if (values.length === 1) return [{ x: +(w / 2).toFixed(1), y: y(values[0]) }];
    const step = w / (values.length - 1);
    return values.map((v, i) => ({ x: +(i * step).toFixed(1), y: y(v) }));
  }

  svgPoints(values: number[], top: number, w = 400, h = 80): string {
    return this.calcPts(values, top, w, h).map(p => `${p.x},${p.y}`).join(' ');
  }

  svgDots(values: number[], top: number, w = 400, h = 80): { x: number; y: number; val: number }[] {
    return this.calcPts(values, top, w, h).map((p, i) => ({ ...p, val: values[i] }));
  }

  get waitingAxisTop(): number { return this.axisTop(this.waitingTime.map(d => d.mins), 4); }
  get waitingYLabels(): number[] { return this.axisLabels(this.waitingAxisTop, 4); }
  get waitingPts()  { return this.svgPoints(this.waitingTime.map(d => d.mins), this.waitingAxisTop); }
  get waitingDots() { return this.svgDots(this.waitingTime.map(d => d.mins), this.waitingAxisTop); }

  get peakPts()  { return this.svgPoints(this.peakHours.map(d => d.count), this.peakAxisTop); }
  get peakDots() { return this.svgDots(this.peakHours.map(d => d.count), this.peakAxisTop); }

  /** True when no visit in the window had both a check-in and a consultation. */
  get waitingUnmeasured(): boolean {
    return this.waitingTime.length > 0 && this.waitingTime.every(d => d.mins === 0);
  }

  get totalCheckIns(): number {
    return this.peakHours.reduce((sum, h) => sum + h.count, 0);
  }

  get peakAxisTop(): number { return this.axisTop(this.peakHours.map(d => d.count), 3); }
  get peakYLabels(): number[] { return this.axisLabels(this.peakAxisTop, 3); }

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

  // ── Money ──────────────────────────────────────────────────────────────────

  /** ₹1,250 — no decimals; the paise are noise on a summary screen. */
  money(value: number): string {
    return '₹' + Math.round(value ?? 0).toLocaleString('en-IN');
  }

  get revenueAxisTop(): number {
    // Round the top gridline up to a clean figure so the axis reads sensibly.
    const max = Math.max(...this.revenueFlow.map(d => d.amount), 0);
    if (max <= 0) return 100;
    const magnitude = Math.pow(10, Math.floor(Math.log10(max)));
    return Math.ceil(max / magnitude) * magnitude;
  }

  get revenueYLabels(): number[] {
    const top = this.revenueAxisTop;
    return [top, top * 0.75, top * 0.5, top * 0.25, 0];
  }

  revenueBarH(amount: number): number {
    if (amount <= 0) return 0;
    return Math.max(2, Math.round((amount / this.revenueAxisTop) * 100));
  }

  /** Width of a top-payer bar, relative to the biggest payer in the list. */
  payerBarW(amount: number): number {
    const top = this.topPayers[0]?.maxAmount ?? 0;
    return top > 0 ? Math.max(3, Math.round((amount / top) * 100)) : 0;
  }

  methodColor(method: string): string {
    return this.METHOD_COLORS[method] ?? '#94a3b8';
  }

  get methodSegs() {
    return this.donutSegs(
      this.payments.byMethod,
      this.payments.byMethod.map(m => this.methodColor(m.method)),
    );
  }

  get hasRevenue(): boolean { return this.payments.transactionCount > 0; }

  // ── Workload bar ───────────────────────────────────────────────────────────
  get maxWorkload(): number { return Math.max(...this.doctorWorkload.map(d => d.count), 1); }
  workW(count: number): number {
    return Math.max(count > 0 ? 4 : 0, Math.round((count / this.maxWorkload) * 100));
  }

  // ── Trend helpers ──────────────────────────────────────────────────────────
  // A null change means the previous window had no activity at all. Showing
  // "+100%" there implied the figure had doubled, which was never true.
  trendClass(val: number | null, invertGood = false): string {
    if (val === null || val === 0) return 'trend-neutral';
    const positive = invertGood ? val < 0 : val > 0;
    return positive ? 'trend-up' : 'trend-down';
  }
  trendIcon(val: number | null, invertGood = false): string {
    if (val === null) return 'pi-info-circle';
    if (val === 0) return 'pi-minus';
    const positive = invertGood ? val < 0 : val > 0;
    return positive ? 'pi-arrow-up' : 'pi-arrow-down';
  }

  /** Wording for a change value, including the "nothing to compare" case. */
  trendText(val: number | null, unit: '%' | 'mins' = '%'): string {
    if (val === null) return `No activity in the previous ${this.periodNoun}`;
    if (val === 0)    return `No change ${this.comparisonLabel}`;
    const shown = unit === '%' ? `${val.toFixed(1)}%` : `${Math.round(val)} mins`;
    return `${shown} ${this.comparisonLabel}`;
  }

  get periodNoun(): string {
    return this.rangeDays === 1 ? 'day' : `${this.rangeDays} days`;
  }

  // ── Exports ────────────────────────────────────────────────────────────────
  exportCSV(): void {
    const nl = '\n';
    const rows: string[] = [
      `"MedClinic Analytics Report — ${this.dateRangeLabel}"`,
      '',
      '"DAILY CONSULTATIONS"',
      '"Day","Consultations"',
      ...this.patientFlow.map(d => `"${d.day}",${d.count}`),
      '',
      '"AVERAGE WAITING TIME (CHECK-IN TO CONSULTATION)"',
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
      '"Hour","Check-ins"',
      ...this.peakHours.map(h => `"${h.hour}",${h.count}`),
      '',
      '"DOCTOR WORKLOAD"',
      '"Doctor","Consultations"',
      ...this.doctorWorkload.map(d => `"${d.name}",${d.count}`),
      '',
      '"REVENUE COLLECTED"',
      `"Day","Amount (${'INR'})"`,
      ...this.revenueFlow.map(d => `"${d.day}",${d.amount}`),
      '',
      '"PAYMENTS BY METHOD"',
      '"Method","Transactions","Amount","%"',
      ...this.payments.byMethod.map(m => `"${m.label}",${m.count},${m.amount},${m.percentage}`),
      '',
      '"PAYMENTS BY PATIENT"',
      '"Rank","Patient","Patient ID","Method","Payments","Amount"',
      ...this.topPayers.map((p, i) =>
        `${i + 1},"${p.name}","${p.patientCode}","${p.methods}",${p.payments},${p.amount}`),
      '',
      '"SUMMARY"',
      '"Metric","Value"',
      `"Patients Seen",${this.summary.totalPatients}`,
      `"Total Consultations",${this.summary.totalConsultations}`,
      `"Avg Waiting Time (mins)",${this.summary.avgWaitingTime}`,
      `"Total Collected",${this.payments.totalCollected}`,
      `"Transactions",${this.payments.transactionCount}`,
      `"Paying Patients",${this.payments.payingPatients}`,
      `"Avg Per Patient",${this.payments.averagePerPatient}`,
      `"Unpaid Visits",${this.payments.outstandingVisits}`,
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
  <tr><th colspan="2" style="background:#e2e8f0;padding:6px">Daily Consultations</th></tr>
  <tr><th style="padding:5px">Day</th><th style="padding:5px">Consultations</th></tr>
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
  <tr><th>Doctor</th><th>Consultations</th></tr>
  ${this.doctorWorkload.map(d => `<tr><td style="padding:4px">${d.name}</td><td style="padding:4px;text-align:right">${d.count}</td></tr>`).join('')}
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="2" style="background:#e2e8f0;padding:6px">Peak Hours</th></tr>
  <tr><th>Hour</th><th>Check-ins</th></tr>
  ${this.peakHours.map(h => `<tr><td style="padding:4px">${h.hour}</td><td style="padding:4px;text-align:right">${h.count}</td></tr>`).join('')}
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="3" style="background:#e2e8f0;padding:6px">Payments by Method</th></tr>
  <tr><th>Method</th><th>Transactions</th><th>Amount</th></tr>
  ${this.payments.byMethod.map(m => `<tr><td style="padding:4px">${m.label}</td><td style="padding:4px;text-align:right">${m.count}</td><td style="padding:4px;text-align:right">${m.amount}</td></tr>`).join('')}
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="3" style="background:#e2e8f0;padding:6px">Payments by Patient</th></tr>
  <tr><th>Patient</th><th>Payments</th><th>Amount</th></tr>
  ${this.topPayers.map(p => `<tr><td style="padding:4px">${p.name} (${p.patientCode})</td><td style="padding:4px;text-align:right">${p.payments}</td><td style="padding:4px;text-align:right">${p.amount}</td></tr>`).join('')}
  <tr><td colspan="3"></td></tr>
  <tr><th colspan="2" style="background:#e2e8f0;padding:6px">Summary</th></tr>
  <tr><td style="padding:4px">Patients Seen</td><td style="padding:4px;text-align:right">${this.summary.totalPatients}</td></tr>
  <tr><td style="padding:4px">Total Consultations</td><td style="padding:4px;text-align:right">${this.summary.totalConsultations}</td></tr>
  <tr><td style="padding:4px">Avg Waiting Time</td><td style="padding:4px;text-align:right">${this.summary.avgWaitingTime} mins</td></tr>
  <tr><td style="padding:4px">Total Collected</td><td style="padding:4px;text-align:right">${this.payments.totalCollected}</td></tr>
  <tr><td style="padding:4px">Unpaid Visits</td><td style="padding:4px;text-align:right">${this.payments.outstandingVisits}</td></tr>
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
