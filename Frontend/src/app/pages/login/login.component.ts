import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { AutoCompleteModule, AutoCompleteSelectEvent } from 'primeng/autocomplete';
import { AuthService, User } from '../../services/auth.service';
import { ApiService, AuthUser } from '../../services/api.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, AutoCompleteModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss'
})
export class LoginComponent implements OnInit {
  password      = '';
  showPw        = false;
  error         = '';
  loading       = false;
  personLoading = false;

  allPersons:      AuthUser[] = [];
  filteredPersons: AuthUser[] = [];
  selectedPerson:  AuthUser | null = null;

  constructor(
    private auth: AuthService,
    private router: Router,
    private api: ApiService,
  ) {}

  ngOnInit(): void {
    this.loadPersons();
  }

  private loadPersons(): void {
    this.personLoading = true;
    this.api.getAuthUsers().subscribe({
      next: (users) => {
        this.allPersons    = users;
        this.personLoading = false;
      },
      error: () => {
        this.personLoading = false;
        this.error = 'Could not load users — check server connection.';
      },
    });
  }

  filterPersons(event: { query: string }): void {
    const q = event.query.trim().toLowerCase();
    this.filteredPersons = !q
      ? [...this.allPersons]
      : this.allPersons.filter(p =>
          p.name.toLowerCase().includes(q) || p.email.toLowerCase().includes(q)
        );
  }

  onPersonSelect(event: AutoCompleteSelectEvent): void {
    this.selectedPerson = event.value as AuthUser;
    this.error          = '';
  }

  onNameBlur(): void {
    if (!this.selectedPerson && this.filteredPersons.length === 1) {
      this.selectedPerson = this.filteredPersons[0];
    }
  }

  onNameClear(): void {
    this.selectedPerson = null;
    this.password       = '';
  }

  getInitials(name: string): string {
    return name.replace(/^Dr\.?\s*/i, '').trim()
      .split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
  }

  onLogin(): void {
    this.error = '';
    if (!this.selectedPerson?.email) {
      this.error = 'Please select a user from the suggestions.';
      return;
    }
    if (!this.password.trim()) {
      this.error = 'Please enter your password.';
      return;
    }

    this.loading = true;
    this.api.login({
      email:    this.selectedPerson.email,
      password: this.password,
    }).subscribe({
      next: (res) => {
        const parts = res.name.replace(/^Dr\.?\s*/i, '').trim().split(/\s+/);
        const user: User = {
          name:               res.name,
          email:              res.email,
          role:               res.role,
          initials:           parts.slice(0, 2).map(w => w[0]).join('').toUpperCase() || res.name[0].toUpperCase(),
          specialization:     res.specialization,
          mustChangePassword: res.mustChangePassword ?? false,
        };
        this.auth.setUser(user);
        this.loading = false;
        if (res.mustChangePassword) {
          this.router.navigate(['/change-password']);
        } else {
          this.router.navigate([this.auth.homeRoute]);
        }
      },
      error: (err) => {
        this.error   = err.error?.detail ?? 'Login failed. Please check your credentials.';
        this.loading = false;
      },
    });
  }
}
