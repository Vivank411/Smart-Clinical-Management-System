import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

interface AppConfig {
  apiUrl: string;
}

@Injectable({ providedIn: 'root' })
export class ConfigService {
  private config: AppConfig = { apiUrl: 'http://localhost:8000' };

  constructor(private http: HttpClient) {}

  load(): Promise<void> {
    return firstValueFrom(this.http.get<AppConfig>('/config.json'))
      .then(cfg => { this.config = cfg; })
      .catch(() => { /* keep default if file unreachable */ });
  }

  get apiUrl(): string {
    return this.config.apiUrl;
  }
}
