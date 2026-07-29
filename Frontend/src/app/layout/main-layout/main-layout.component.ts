import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, SidebarComponent],
  templateUrl: './main-layout.component.html',
  styleUrl: './main-layout.component.scss'
})
export class MainLayoutComponent {
  sidebarOpen = false;

  constructor(public auth: AuthService) {}

  /**
   * Must be a void method, not an inline `sidebarOpen = false` binding: Angular
   * calls preventDefault() whenever a handler expression evaluates to false, and
   * this one sits on the wrapper around every page — it was cancelling the default
   * action of every click in the app (e.g. file inputs never opened their picker).
   */
  closeSidebar(): void {
    this.sidebarOpen = false;
  }

  get initials(): string {
    const name = this.auth.getUser()?.name ?? '';
    return name.split(' ').slice(0, 2).map((w: string) => w[0]).join('').toUpperCase();
  }
}
