import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ThemeService } from '../core/theme.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, FormsModule],
  templateUrl: './sidebar.component.html',
})
export class SidebarComponent {
  @Input() user: any;
  @Input() mobileMenuOpen = false;
  @Input() language: 'es' | 'en' = 'es';
  @Input() isGroupExpanded: (g: string) => boolean = () => true;
  @Output() toggleGroupEvent = new EventEmitter<string>();
  @Output() logoutEvent = new EventEmitter<void>();
  @Output() toggleProfileMenuEvent = new EventEmitter<void>();
  @Output() closeMobileMenu = new EventEmitter<void>();

  readonly theme = inject(ThemeService);
  showThemeModal = false;
  wmsExpanded = true;

  t(es: string, en: string): string {
    return this.language === 'es' ? es : en;
  }
  toggleGroup(group: string) { this.toggleGroupEvent.emit(group); }
  toggleWms() { this.wmsExpanded = !this.wmsExpanded; }
  logout() { this.logoutEvent.emit(); }
  toggleProfileMenu() { this.toggleProfileMenuEvent.emit(); }
  openThemeModal() { this.showThemeModal = true; }
  closeThemeModal() { this.showThemeModal = false; }
  onAccentChange(ev: Event) {
    const v = (ev.target as HTMLInputElement).value;
    this.theme.setAccent(v);
  }
  resetTheme() {
    this.theme.resetToDefault();
  }
}
