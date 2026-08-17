import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService, PaymentStatus } from '../../services/api.service';

/**
 * Receipt shown once the fee has been collected — this is where the queue
 * token is revealed. The payment is always re-read from the API rather than
 * trusted from the query string.
 */
@Component({
  selector: 'app-payment-result',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './payment-result.component.html',
  styleUrl: './payment-result.component.scss',
})
export class PaymentResultComponent implements OnInit {
  payment: PaymentStatus | null = null;
  loading = true;
  errorMessage = '';

  constructor(
    private api: ApiService,
    private route: ActivatedRoute,
    private router: Router,
  ) {}

  ngOnInit(): void {
    const txnid = this.route.snapshot.queryParamMap.get('txnid');
    if (!txnid) {
      this.errorMessage = 'No payment reference was supplied.';
      this.loading = false;
      return;
    }
    this.api.getPaymentStatus(txnid).subscribe({
      next: (p) => { this.payment = p; this.loading = false; },
      error: () => {
        this.errorMessage = 'Could not look up this payment.';
        this.loading = false;
      },
    });
  }

  get succeeded(): boolean { return this.payment?.status === 'Success'; }

  get amountLabel(): string {
    if (!this.payment) return '';
    const symbol = this.payment.currency === 'INR' ? '₹' : `${this.payment.currency} `;
    return `${symbol}${this.payment.amount}`;
  }

  get methodLabel(): string {
    return { qr: 'UPI / QR', card: 'Card', cash: 'Cash' }[this.payment?.method ?? 'cash'];
  }

  get paidAtLabel(): string {
    if (!this.payment?.completedAt) return '';
    const d = new Date(this.payment.completedAt);
    return isNaN(d.getTime())
      ? this.payment.completedAt
      : d.toLocaleString('en-US', {
          day: '2-digit', month: 'short', year: 'numeric',
          hour: '2-digit', minute: '2-digit', hour12: true,
        });
  }

  retry(): void {
    if (!this.payment) return;
    this.router.navigate(['/payment', this.payment.patientId]);
  }

  goToDashboard(): void { this.router.navigate(['/dashboard']); }

  print(): void { window.print(); }
}
