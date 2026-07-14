import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-change-password',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './change-password.component.html',
  styleUrl: './change-password.component.scss'
})
export class ChangePasswordComponent {
  currentPw  = '';
  newPw      = '';
  confirmPw  = '';
  showCur    = false;
  showNew    = false;
  showConf   = false;
  loading    = false;
  error      = '';

  constructor(
    public  auth: AuthService,
    private api:  ApiService,
    private router: Router,
  ) {
    // If user isn't logged in or doesn't need to change password, redirect
    const user = this.auth.getUser();
    if (!user) {
      this.router.navigate(['/login']);
    }
  }

  get user() { return this.auth.getUser(); }

  get hasMinLength(): boolean  { return this.newPw.length >= 8; }
  get hasUppercase(): boolean  { return /[A-Z]/.test(this.newPw); }
  get hasNumber(): boolean     { return /[0-9]/.test(this.newPw); }
  get hasSpecial(): boolean    { return /[^A-Za-z0-9]/.test(this.newPw); }
  get passwordsMatch(): boolean { return this.newPw === this.confirmPw; }

  get strength(): number {
    return [this.hasMinLength, this.hasUppercase, this.hasNumber, this.hasSpecial]
      .filter(Boolean).length;
  }

  get strengthLabel(): string {
    return ['', 'Weak', 'Fair', 'Good', 'Strong'][this.strength];
  }

  get strengthClass(): string {
    return ['', 'str--weak', 'str--fair', 'str--good', 'str--strong'][this.strength];
  }

  submit(): void {
    this.error = '';
    if (!this.currentPw) { this.error = 'Please enter your current (temporary) password.'; return; }
    if (this.newPw.length < 8) { this.error = 'New password must be at least 8 characters.'; return; }
    if (this.newPw !== this.confirmPw) { this.error = 'Passwords do not match.'; return; }
    if (this.newPw === this.currentPw) { this.error = 'New password must be different from the temporary password.'; return; }

    const email = this.user?.email;
    if (!email) { this.router.navigate(['/login']); return; }

    this.loading = true;
    this.api.changePassword(email, this.currentPw, this.newPw).subscribe({
      next: () => {
        // Clear the mustChangePassword flag in session
        const u = this.auth.getUser();
        if (u) { u.mustChangePassword = false; this.auth.setUser(u); }
        this.loading = false;
        this.router.navigate([this.auth.homeRoute]);
      },
      error: (err) => {
        this.error   = err.error?.detail ?? 'Failed to change password. Please try again.';
        this.loading = false;
      },
    });
  }
}
