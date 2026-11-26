import { Injectable, signal } from '@angular/core';

export interface ThemeColors {
  accent: string;
}

const DEFAULT_ACCENT = '#a78bfa';
const STORAGE_KEY = 'sophia_theme_accent';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly accentColor = signal<string>(DEFAULT_ACCENT);

  constructor() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      this.accentColor.set(saved);
      this.apply(saved);
    } else {
      this.apply(DEFAULT_ACCENT);
    }
  }

  setAccent(color: string) {
    this.accentColor.set(color);
    localStorage.setItem(STORAGE_KEY, color);
    this.apply(color);
  }

  resetToDefault() {
    localStorage.removeItem(STORAGE_KEY);
    this.accentColor.set(DEFAULT_ACCENT);
    this.apply(DEFAULT_ACCENT);
  }

  private apply(color: string) {
    const root = document.documentElement;
    root.style.setProperty('--theme-accent', color);
    root.style.setProperty('--theme-accent-strong', color);
    root.style.setProperty('--theme-accent-bg', this.hexToRgba(color, 0.18));
    root.style.setProperty('--theme-btn-start', color);
    root.style.setProperty('--theme-btn-end', this.darkenHex(color, 20));
    root.style.setProperty('--theme-btn-border', color);
  }

  private darkenHex(hex: string, percent: number): string {
    const h = hex.replace('#', '');
    const num = parseInt(h, 16);
    const r = Math.max(0, (num >> 16) - Math.round(2.55 * percent));
    const g = Math.max(0, ((num >> 8) & 0x00FF) - Math.round(2.55 * percent));
    const b = Math.max(0, (num & 0x0000FF) - Math.round(2.55 * percent));
    return '#' + (0x1000000 + r * 0x10000 + g * 0x100 + b).toString(16).slice(1);
  }

  private hexToRgba(hex: string, alpha: number): string {
    const h = hex.replace('#', '');
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
}
