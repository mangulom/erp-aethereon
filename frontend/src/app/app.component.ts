import { Component, OnInit, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { AuthService } from './core/auth.service';
import { LanguageService } from './core/language.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.component.html',
})
export class AppComponent implements OnInit {
  showIntro = true;
  readonly mobileMenuOpen = signal(false);
  readonly profileMenuOpen = signal(false);
  readonly expandedGroups = signal<string[]>(['maintenance']);
  readonly searchValue = signal('');
  readonly user;
  readonly language;
  readonly todayLabel = signal('');
  readonly companies = signal<Array<{id:string;legal_name:string;trade_name?:string;default_currency:string}>>([]);
  readonly selectedCompanyId = signal(localStorage.getItem('aethereon.selected_company') || '');
  readonly activeCompanyName = signal('');

  constructor(private readonly router: Router, private readonly auth: AuthService, private readonly languageService: LanguageService, private readonly http: HttpClient) {
    this.user = this.auth.user;
    this.language = this.languageService.language;
    this.todayLabel.set(this.dateLabel());
  }

  ngOnInit(): void {
    this.loadCompanies();
    if (this.auth.user()?.is_platform_admin) this.expandedGroups.update((groups) => groups.includes('maintenance') ? groups : [...groups, 'maintenance']);
    this.router.events.pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd)).subscribe(() => {
      this.mobileMenuOpen.set(false);
      this.profileMenuOpen.set(false);
      if (this.auth.token && !this.companies().length) this.loadCompanies();
      if (this.router.url.split('?')[0] === '/login') this.auth.logout();
    });
    window.setTimeout(() => {
      this.showIntro = false;
      const navigateIfRoot = () => {
        const path = this.router.url.split('?')[0];
        if (path === '/' || !path) void this.router.navigate([this.auth.token ? '/dashboard' : '/login'], { replaceUrl: true });
      };
      if (this.router.navigated) navigateIfRoot();
      else this.router.events.pipe(filter((event) => event instanceof NavigationEnd), filter(() => this.router.navigated)).subscribe({ next: navigateIfRoot });
    }, 2000);
  }

  get loggedIn(): boolean { return !!this.auth.token; }
  get loginRoute(): boolean { return this.router.url.startsWith('/login'); }
  logout(): void { this.auth.logout(); this.mobileMenuOpen.set(false); void this.router.navigate(['/login']); }
  loadCompanies(): void {
    if (!this.auth.token) return;
    this.http.get<Array<{id:string;legal_name:string;trade_name?:string;default_currency:string}>>('/api/v1/auth/companies').subscribe({
      next: (companies) => {
        this.companies.set(companies);
        const stored = localStorage.getItem('aethereon.selected_company') || this.selectedCompanyId();
        const chosen = companies.find((company) => company.id === stored)?.id || companies[0]?.id || '';
        this.selectedCompanyId.set(chosen);
        const active = companies.find((company) => company.id === chosen);
        this.activeCompanyName.set(active ? (active.trade_name || active.legal_name) : '');
        if (chosen) localStorage.setItem('aethereon.selected_company', chosen);
      },
    });
  }
  selectCompany(companyId: string): void {
    if (!companyId || companyId === this.selectedCompanyId()) return;
    this.http.post<{access_token:string}>('/api/v1/auth/select-company', null, { params: { company_id: companyId } }).subscribe({
      next: (response) => {
        this.auth.updateToken(response.access_token);
        this.selectedCompanyId.set(companyId);
        const active = this.companies().find((company) => company.id === companyId);
        this.activeCompanyName.set(active ? (active.trade_name || active.legal_name) : '');
        localStorage.setItem('aethereon.selected_company', companyId);
        window.location.reload();
      },
    });
  }
  toggleProfileMenu(): void { this.profileMenuOpen.update((open) => !open); }
  closeProfileMenu(): void { this.profileMenuOpen.set(false); }
  onProfileKeydown(event: KeyboardEvent): void { if (event.key === 'Escape') this.closeProfileMenu(); }
  t(spanish: string, english: string): string { return this.languageService.text(spanish, english); }
  toggleLanguage(): void { this.languageService.toggle(); this.todayLabel.set(this.dateLabel()); }

  isGroupExpanded(group: string): boolean { return this.expandedGroups().includes(group); }

  toggleGroup(group: string): void {
    this.expandedGroups.update((groups) => groups.includes(group) ? groups.filter((item) => item !== group) : [...groups, group]);
  }

  onShellWheel(event: WheelEvent): void {
    const sidebar = (event.target as HTMLElement | null)?.closest('.sidebar-nav') as HTMLElement | null;
    const main = (event.target as HTMLElement | null)?.closest('.command-main') as HTMLElement | null;
    if (sidebar && sidebar.scrollHeight > sidebar.clientHeight) {
      sidebar.scrollTop += event.deltaY;
      event.preventDefault();
    } else if (main && main.scrollHeight > main.clientHeight) {
      main.scrollTop += event.deltaY;
      event.preventDefault();
    }
  }

  onSearchKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter') return;
    const query = this.searchValue().trim().toLowerCase();
    const match = query ? this.moduleRoutes.find((module) => module.search.some((term) => term.includes(query))) : undefined;
    if (match) void this.router.navigate([match.route]);
    else if (query) void this.router.navigate(['/modules']);
  }

  private dateLabel(): string {
    const locale = this.languageService.language() === 'es' ? 'es-PE' : 'en-US';
    return new Intl.DateTimeFormat(locale, { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date());
  }

  private readonly moduleRoutes = [
    { route: '/dashboard', search: ['dashboard', 'inicio', 'principal', 'overview', 'resumen'] },
    { route: '/modules', search: ['modulos', 'módulos', 'modulo', 'módulo', 'finanzas', 'contabilidad', 'ventas', 'crm', 'compras', 'inventario', 'logistica', 'logística', 'rr. hh.', 'nomina', 'nómina', 'produccion', 'producción', 'proyectos', 'mantenimiento', 'calidad', 'seguridad', 'legal', 'documentos', 'cliente', 'bi', 'inteligencia', 'ia', 'comercio', 'innovacion', 'innovación', 'workflows', 'agents'] },
    { route: '/settings', search: ['administracion', 'administración', 'configuracion', 'configuración', 'seguridad', 'plataforma', 'settings'] },
  ];
}
