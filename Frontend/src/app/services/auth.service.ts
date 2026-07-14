import { Injectable } from '@angular/core';
import { Router } from '@angular/router';

export interface User {
  name: string;
  role: string;
  initials: string;
  email: string;
  specialization?: string;
  mustChangePassword?: boolean;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private currentUser: User | null = null;

  constructor(private router: Router) {
    const stored = sessionStorage.getItem('mc_user');
    if (stored) this.currentUser = JSON.parse(stored);
  }

  setUser(user: User): void {
    this.currentUser = user;
    sessionStorage.setItem('mc_user', JSON.stringify(user));
  }

  logout(): void {
    this.currentUser = null;
    sessionStorage.removeItem('mc_user');
    this.router.navigate(['/login']);
  }

  isLoggedIn(): boolean { return !!this.currentUser; }
  getUser(): User | null { return this.currentUser; }

  get isDoctor(): boolean       { return this.currentUser?.role === 'Junior Doctor'; }
  get isFullDoctor(): boolean   { return this.currentUser?.role === 'Doctor'; }
  get isReceptionist(): boolean { return this.currentUser?.role === 'Receptionist'; }
  get isAdmin(): boolean        { return this.currentUser?.role === 'Admin'; }

  get homeRoute(): string {
    if (this.isFullDoctor) return '/doctor-queue';
    if (this.isDoctor)     return '/doctor-dashboard';
    if (this.isAdmin)      return '/admin-dashboard';
    return '/dashboard';
  }
}
