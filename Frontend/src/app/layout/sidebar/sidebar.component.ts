import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../services/auth.service';

interface NavItem { label: string; icon: string; route: string; }

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {
  @Input()  mobileOpen = false;
  @Output() navClick   = new EventEmitter<void>();

  constructor(public auth: AuthService) {}

  onNavClick(): void { this.navClick.emit(); }

  get navItems(): NavItem[] {
    const role = this.auth.getUser()?.role;
    if (role === 'Doctor') {
      return [
        { label: 'Queue',            icon: 'pi-list-check', route: '/doctor-queue' },
        { label: 'E-Prescriptions',  icon: 'pi-file-edit',  route: '/doctor-eprescription' },
        { label: 'Patient Records',  icon: 'pi-folder',     route: '/doctor-patient-records' },
      ];
    }
    if (role === 'Junior Doctor') {
      return [
        { label: 'Patient Queue', icon: 'pi-list-check', route: '/doctor-dashboard' },
      ];
    }
    if (role === 'Admin') {
      return [
        { label: 'Dashboard',         icon: 'pi-th-large',   route: '/admin-dashboard' },
        { label: 'User Management',   icon: 'pi-users',      route: '/admin-users' },
        { label: 'Doctor Management', icon: 'pi-heart',      route: '/admin-doctors' },
        { label: 'Reports',           icon: 'pi-chart-bar',  route: '/admin-reports' },
        { label: 'Audit Logs',        icon: 'pi-file-check', route: '/admin-audit' },
        { label: 'System Settings',   icon: 'pi-cog',        route: '/admin-settings' },
      ];
    }
    return [
      { label: 'Dashboard',            icon: 'pi-th-large',  route: '/dashboard' },
      { label: 'Patient Registration', icon: 'pi-user-plus', route: '/patient-registration' },
      { label: 'Search Patient',       icon: 'pi-search',    route: '/search-patient' },
    ];
  }

  get portalLabel(): string {
    const role = this.auth.getUser()?.role;
    if (role === 'Doctor')        return 'Doctor Portal';
    if (role === 'Junior Doctor') return 'Doctor Portal';
    if (role === 'Admin')         return 'Admin Portal';
    return 'Reception Portal';
  }
}
