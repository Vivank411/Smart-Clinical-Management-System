import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent)
  },
  {
    path: 'change-password',
    loadComponent: () => import('./pages/change-password/change-password.component').then(m => m.ChangePasswordComponent)
  },
  {
    path: '',
    loadComponent: () => import('./layout/main-layout/main-layout.component').then(m => m.MainLayoutComponent),
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent)
      },
      {
        path: 'patient-registration',
        loadComponent: () => import('./pages/patient-registration/patient-registration.component').then(m => m.PatientRegistrationComponent)
      },
      {
        path: 'search-patient',
        loadComponent: () => import('./pages/search-patient/search-patient.component').then(m => m.SearchPatientComponent)
      },
      {
        path: 'check-in',
        loadComponent: () => import('./pages/check-in/check-in.component').then(m => m.CheckInComponent)
      },
      {
        path: 'doctor-dashboard',
        loadComponent: () => import('./pages/doctor-dashboard/doctor-dashboard.component').then(m => m.DoctorDashboardComponent)
      },
      {
        path: 'doctor-queue',
        loadComponent: () => import('./pages/doctor-queue/doctor-queue.component').then(m => m.DoctorQueueComponent)
      },
      {
        path: 'doctor-consultation/:id',
        loadComponent: () => import('./pages/consultation/consultation.component').then(m => m.ConsultationComponent)
      },
      {
        path: 'doctor-eprescription',
        loadComponent: () => import('./pages/doctor-eprescription/doctor-eprescription.component').then(m => m.DoctorEprescriptionComponent)
      },
      {
        path: 'doctor-patient-records',
        loadComponent: () => import('./pages/doctor-patient-records/doctor-patient-records.component').then(m => m.DoctorPatientRecordsComponent)
      },
      {
        path: 'admin-dashboard',
        loadComponent: () => import('./pages/admin-dashboard/admin-dashboard.component').then(m => m.AdminDashboardComponent)
      },
      {
        path: 'admin-users',
        loadComponent: () => import('./pages/admin-users/admin-users.component').then(m => m.AdminUsersComponent)
      },
      {
        path: 'admin-doctors',
        loadComponent: () => import('./pages/admin-doctors/admin-doctors.component').then(m => m.AdminDoctorsComponent)
      },
      {
        path: 'admin-reports',
        loadComponent: () => import('./pages/admin-reports/admin-reports.component').then(m => m.AdminReportsComponent)
      },
      {
        path: 'admin-audit',
        loadComponent: () => import('./pages/admin-audit/admin-audit.component').then(m => m.AdminAuditComponent)
      },
      {
        path: 'admin-settings',
        loadComponent: () => import('./pages/admin-settings/admin-settings.component').then(m => m.AdminSettingsComponent)
      },
    ]
  },
  { path: '**', redirectTo: 'login' }
];
