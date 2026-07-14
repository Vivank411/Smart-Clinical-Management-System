import { Injectable } from '@angular/core';

/** Reads the admin System Settings persisted by AdminSettingsComponent (localStorage). */
@Injectable({ providedIn: 'root' })
export class SettingsService {
  private static readonly KEY = 'mc_admin_settings';

  private read(): any {
    try {
      const raw = localStorage.getItem(SettingsService.KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  /** Registration is on unless an admin has explicitly turned it off. */
  get registrationEnabled(): boolean {
    return this.read()?.general?.enableRegistration !== false;
  }

  get maintenanceMode(): boolean {
    return this.read()?.general?.maintenanceMode === true;
  }
}
