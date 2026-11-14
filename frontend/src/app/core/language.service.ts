import { Injectable, signal } from '@angular/core';

export type AppLanguage = 'es' | 'en';

const STORAGE_KEY = 'aethereon.language';

@Injectable({ providedIn: 'root' })
export class LanguageService {
  readonly language = signal<AppLanguage>(this.readLanguage());

  setLanguage(language: AppLanguage): void {
    this.language.set(language);
    localStorage.setItem(STORAGE_KEY, language);
  }

  toggle(): void {
    this.setLanguage(this.language() === 'es' ? 'en' : 'es');
  }

  text(spanish: string, english: string): string {
    return this.language() === 'es' ? spanish : english;
  }

  private readLanguage(): AppLanguage {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'es';
    } catch {
      return 'es';
    }
  }
}
