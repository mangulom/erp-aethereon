import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, firstValueFrom } from 'rxjs';

export interface CompanyInfo {
  id: string;
  legal_name: string;
  trade_name?: string;
  tax_id?: string;
  country_code?: string;
  default_currency?: string;
  timezone?: string;
  is_active?: boolean;
}

export interface CompanyContext {
  companies: CompanyInfo[];
  selectedCompanyId: string;
  activeCompany: CompanyInfo | null;
  activeCompanyName: string;
  hasActiveCompany: boolean;
  loaded: boolean;
}

const EMPTY_CONTEXT: CompanyContext = {
  companies: [],
  selectedCompanyId: '',
  activeCompany: null,
  activeCompanyName: '',
  hasActiveCompany: false,
  loaded: false,
};

@Injectable({ providedIn: 'root' })
export class CompanyService {
  private readonly storageKey = 'aethereon.selected_company';
  private readonly contextSubject = new BehaviorSubject<CompanyContext>(EMPTY_CONTEXT);
  readonly context$ = this.contextSubject.asObservable();

  // Signals retained for existing Angular templates; all are projected from contextSubject.
  readonly companies = signal<CompanyInfo[]>([]);
  readonly companiesLoaded = signal(false);
  readonly selectedCompanyId = signal('');

  constructor(private readonly http: HttpClient) {
    const stored = localStorage.getItem(this.storageKey) || '';
    this.publish({ ...EMPTY_CONTEXT, selectedCompanyId: stored });
  }

  get context(): CompanyContext { return this.contextSubject.value; }
  get hasActiveCompany(): boolean { return this.context.hasActiveCompany; }
  get activeCompany(): CompanyInfo | undefined { return this.context.activeCompany || undefined; }
  get activeCompanyName(): string { return this.context.activeCompanyName; }

  private publish(patch: Partial<CompanyContext>): void {
    const previous = this.contextSubject.value;
    const companies = patch.companies ?? previous.companies;
    const selectedCompanyId = patch.selectedCompanyId ?? previous.selectedCompanyId;
    const activeCompany = companies.find(company => company.id === selectedCompanyId) || null;
    const next: CompanyContext = {
      companies,
      selectedCompanyId: activeCompany ? selectedCompanyId : '',
      activeCompany,
      activeCompanyName: activeCompany ? (activeCompany.trade_name || activeCompany.legal_name) : '',
      hasActiveCompany: !!activeCompany,
      loaded: patch.loaded ?? previous.loaded,
    };
    this.contextSubject.next(next);
    this.companies.set(next.companies);
    this.companiesLoaded.set(next.loaded);
    this.selectedCompanyId.set(next.selectedCompanyId);
  }

  async loadCompanies(): Promise<void> {
    try {
      const companies = await firstValueFrom(this.http.get<CompanyInfo[]>('/api/v1/auth/companies'));
      const stored = localStorage.getItem(this.storageKey) || this.context.selectedCompanyId;
      const selectedCompanyId = stored && companies.some(company => company.id === stored) ? stored : '';
      this.publish({ companies, selectedCompanyId, loaded: true });
      if (selectedCompanyId) localStorage.setItem(this.storageKey, selectedCompanyId);
      else localStorage.removeItem(this.storageKey);
    } catch {
      this.publish({ companies: [], selectedCompanyId: '', loaded: true });
      localStorage.removeItem(this.storageKey);
    }
  }

  async selectCompany(companyId: string): Promise<void> {
    if (!companyId) {
      this.publish({ selectedCompanyId: '' });
      localStorage.removeItem(this.storageKey);
      return;
    }
    if (!this.context.companies.some(company => company.id === companyId)) return;
    if (companyId === this.context.selectedCompanyId && this.context.hasActiveCompany) return;

    try {
      const response = await firstValueFrom(
        this.http.post<{ access_token: string }>('/api/v1/auth/select-company', null, { params: { company_id: companyId } }),
      );
      localStorage.setItem('aethereon.access_token', response.access_token);
      localStorage.setItem(this.storageKey, companyId);
      // One synchronous state emission updates the header, Finance, and every other consumer.
      this.publish({ selectedCompanyId: companyId, loaded: true });
    } catch {
      // Keep the last valid selection if the server rejects the change.
    }
  }

  syncCompany(updated: CompanyInfo): void {
    const companies = this.context.companies.map(company => company.id === updated.id ? { ...company, ...updated } : company);
    this.publish({ companies, loaded: true });
  }

  syncCompanies(companies: CompanyInfo[], selectedCompanyId = this.context.selectedCompanyId): void {
    const keepSelected = selectedCompanyId && companies.some(company => company.id === selectedCompanyId && company.is_active !== false)
      ? selectedCompanyId
      : '';
    this.publish({ companies, selectedCompanyId: keepSelected, loaded: true });
    if (keepSelected) localStorage.setItem(this.storageKey, keepSelected);
    else localStorage.removeItem(this.storageKey);
  }
}
