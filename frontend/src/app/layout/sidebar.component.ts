import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
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

  t(es: string, en: string): string {
    return this.language === 'es' ? es : en;
  }
  toggleGroup(group: string) { this.toggleGroupEvent.emit(group); }
  logout() { this.logoutEvent.emit(); }
  toggleProfileMenu() { this.toggleProfileMenuEvent.emit(); }
}
