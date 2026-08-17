import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { forkJoin } from 'rxjs';
import {
  ApiService, ApiPatient, PaymentConfig, PaymentMethod, PaymentStatus,
} from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

/** Shown under the bundled QR when no custom label has been set. */
const DEFAULT_QR_LABEL = '8273075781@pthdfc';

/**
 * Consultation-fee collection at the desk, taken after check-in.
 *
 * All three methods settle in person — the patient scans the clinic's QR, taps
 * a card on the clinic's own machine, or hands over cash — and the receptionist
 * confirms. The queue token is issued by the server at that moment.
 */
@Component({
  selector: 'app-payment',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './payment.component.html',
  styleUrl: './payment.component.scss',
})
export class PaymentComponent implements OnInit {
  patient: ApiPatient | null = null;
  config: PaymentConfig | null = null;

  method: PaymentMethod | null = null;
  payment: PaymentStatus | null = null;

  loading = true;
  busy = false;
  errorMessage = '';

  /** Reconciliation details, captured against the bank statement later. */
  reference = '';
  cardLast4 = '';
  notes = '';

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private route: ActivatedRoute,
    private router: Router,
  ) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('patientId'));
    if (!id) { this.errorMessage = 'No patient selected for payment.'; this.loading = false; return; }

    forkJoin({
      patient: this.api.getPatient(id),
      config:  this.api.getPaymentConfig(),
    }).subscribe({
      next: ({ patient, config }) => {
        this.patient = patient;
        this.config  = config;
        this.loading = false;
      },
      error: () => {
        this.errorMessage = 'Could not load the payment details. Please try again.';
        this.loading = false;
      },
    });
  }

  // ── Display ────────────────────────────────────────────────────────────────

  get amountLabel(): string {
    if (!this.config) return '';
    const symbol = this.config.currency === 'INR' ? '₹' : `${this.config.currency} `;
    return `${symbol}${this.config.amount}`;
  }

  get initials(): string {
    return (this.patient?.name ?? '')
      .split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?';
  }

  get alreadyPaid(): boolean {
    return this.patient?.paymentStatus === 'Paid' || this.patient?.paymentStatus === 'Waived';
  }

  /**
   * The QR shown at the counter.
   *
   * Falls back to the image bundled at `public/payment-qr.png`, so the option
   * works out of the box. Uploading one under Settings → Payment Settings
   * overrides it without touching the code.
   */
  get qrSrc(): string {
    return this.config?.qrImage || 'payment-qr.png';
  }

  get qrCaption(): string {
    return this.config?.qrLabel || DEFAULT_QR_LABEL;
  }

  /** Set when the bundled asset is missing and nothing has been uploaded. */
  qrBroken = false;

  onQrLoadError(): void { this.qrBroken = true; }

  get referenceLabel(): string {
    return this.method === 'qr'
      ? 'UPI reference / UTR number'
      : 'Approval code from the card machine';
  }

  /** Blocks confirm when a full card number has been pasted into reference. */
  get referenceLooksLikeACardNumber(): boolean {
    return this.reference.replace(/\D/g, '').length >= 13;
  }

  get cardLast4Invalid(): boolean {
    return !!this.cardLast4 && !/^\d{4}$/.test(this.cardLast4);
  }

  get canConfirm(): boolean {
    return !this.busy && !this.referenceLooksLikeACardNumber && !this.cardLast4Invalid;
  }

  // ── Flow ───────────────────────────────────────────────────────────────────

  choose(method: PaymentMethod): void {
    if (!this.patient || this.busy) return;
    this.busy = true;
    this.errorMessage = '';

    this.api.initiatePayment(this.patient.id, method).subscribe({
      next: (p) => {
        this.busy = false;
        this.method = method;
        this.payment = p;
      },
      error: (err) => {
        this.busy = false;
        this.errorMessage = err.error?.detail ?? 'Could not start the payment. Please try again.';
      },
    });
  }

  confirm(): void {
    if (!this.payment || !this.canConfirm) return;
    this.busy = true;
    this.errorMessage = '';

    this.api.confirmPayment(this.payment.txnid, {
      collectedBy: this.auth.getUser()?.name,
      reference:   this.reference.trim() || undefined,
      cardLast4:   this.method === 'card' ? (this.cardLast4.trim() || undefined) : undefined,
      notes:       this.notes.trim() || undefined,
    }).subscribe({
      next: (p) => {
        this.busy = false;
        this.router.navigate(['/payment/result'], { queryParams: { txnid: p.txnid } });
      },
      error: (err) => {
        this.busy = false;
        this.errorMessage = err.error?.detail ?? 'Could not record the payment. Please try again.';
      },
    });
  }

  /** Abandon this attempt and go back to the method list. */
  back(): void {
    if (!this.payment || this.busy) { this.reset(); return; }
    this.busy = true;
    this.api.cancelPayment(this.payment.txnid).subscribe({
      next: () => { this.busy = false; this.reset(); },
      error: () => { this.busy = false; this.reset(); },
    });
  }

  private reset(): void {
    this.method = null;
    this.payment = null;
    this.reference = '';
    this.cardLast4 = '';
    this.notes = '';
    this.errorMessage = '';
  }

  cancel(): void { this.router.navigate(['/dashboard']); }
}
