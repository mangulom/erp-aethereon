import { CommonModule } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { CompanyService } from '../../core/company.service';
import { LanguageService } from '../../core/language.service';

type AccTab = 'accounts' | 'journals' | 'books';
type BookType = 'journal' | 'ledger' | 'purchase' | 'sales' | 'cash';

@Component({
  selector: 'app-accounting',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="fin-workspace finance-advanced">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">{{ t('MÓDULO', 'MODULE') }}</span>
          <h1 class="fin-title-main">{{ t('Contabilidad', 'Accounting') }}</h1>
          <p class="fin-subtitle-desc">{{ t('Plan de cuentas, asientos y libros: Diario, Mayor, Compras, Ventas y Caja.', 'Chart of accounts, entries and books: Journal, Ledger, Purchases, Sales, Cash.') }}</p>
        </div>
      </header>

      @if (!hasCompany) {
        <div class="fin-alert" role="alert">{{ t('Selecciona una empresa activa.', 'Select an active company.') }}</div>
      }
      @if (error) { <div class="fin-alert fin-alert-error" role="alert">{{ error }}</div> }

      @if (hasCompany) {
        <nav class="fin-tabs" aria-label="Contabilidad">
          <button type="button" [class.active]="tab==='accounts'" (click)="setTab('accounts')">{{ t('Plan de cuentas', 'Chart of accounts') }}</button>
          <button type="button" [class.active]="tab==='journals'" (click)="setTab('journals')">{{ t('Asientos', 'Journal entries') }}</button>
          <button type="button" [class.active]="tab==='books'" (click)="setTab('books')">{{ t('Libros', 'Books') }}</button>
        </nav>

        @if (tab==='accounts') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('PLAN DE CUENTAS', 'CHART OF ACCOUNTS') }}</span><h3>{{ t('Cuentas contables', 'General ledger accounts') }}</h3></div><div style="display:flex;gap:8px;"><button class="fin-primary" type="button" (click)="openAccountForm()">{{ t('Nueva cuenta','New account') }}</button><button class="fin-secondary" type="button" (click)="loadAccounts()" [disabled]="loadingAccounts">{{ loadingAccounts ? t('Cargando…','Loading…') : t('Actualizar','Refresh') }}</button></div></div>
            @if (accounts.length===0 && !loadingAccounts) { <div class="fin-empty">{{ t('No hay cuentas registradas.', 'No accounts registered.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Código','Code') }}</th><th>{{ t('Nombre','Name') }}</th><th>{{ t('Tipo','Type') }}</th><th>{{ t('Subtipo','Subtype') }}</th><th>{{ t('Moneda','Currency') }}</th><th>{{ t('Estado','Status') }}</th><th>{{ t('Acciones','Actions') }}</th></tr></thead><tbody>@for (a of accounts; track a.id) { <tr><td><b>{{ a.code }}</b></td><td>{{ a.name }}</td><td>{{ a.account_type }}</td><td>{{ a.account_subtype||'—' }}</td><td>{{ a.currency }}</td><td>{{ a.is_active?t('Activo','Active'):t('Inactivo','Inactive') }}</td><td><button class="fin-secondary" type="button" (click)="openAccountForm(a)">{{ t('Editar','Edit') }}</button> <button class="fin-secondary" type="button" (click)="confirmDeleteAccount(a)">{{ t('Eliminar','Delete') }}</button></td></tr> }</tbody></table></div> }
          </div>
          @if (showAccountForm) {
            <div class="fin-panel" style="margin-top:12px;">
              <h3 style="margin:0 0 12px;">{{ editingAccount ? t('Editar cuenta','Edit account') : t('Nueva cuenta','New account') }}</h3>
              <div class="fin-form-grid">
                <label>{{ t('Código','Code') }}<input [(ngModel)]="accountForm.code" [disabled]="!!editingAccount"></label>
                <label>{{ t('Nombre','Name') }}<input [(ngModel)]="accountForm.name"></label>
                <label>{{ t('Tipo','Type') }}<select [(ngModel)]="accountForm.account_type"><option value="asset">Asset</option><option value="liability">Liability</option><option value="equity">Equity</option><option value="revenue">Revenue</option><option value="expense">Expense</option></select></label>
                <label>{{ t('Subtipo','Subtype') }}<input [(ngModel)]="accountForm.account_subtype" placeholder="opcional"></label>
                <label>{{ t('Moneda','Currency') }}<input [(ngModel)]="accountForm.currency" maxlength="3"></label>
                <label>{{ t('Es grupo','Is group') }}<select [(ngModel)]="accountForm.is_group"><option [ngValue]="false">No</option><option [ngValue]="true">Yes</option></select></label>
                <label>{{ t('Permite registro','Allow posting') }}<select [(ngModel)]="accountForm.allow_posting"><option [ngValue]="true">Yes</option><option [ngValue]="false">No</option></select></label>
                <label>{{ t('Activa','Active') }}<select [(ngModel)]="accountForm.is_active"><option [ngValue]="true">Yes</option><option [ngValue]="false">No</option></select></label>
              </div>
              <div style="display:flex;gap:8px;margin-top:12px;"><button class="fin-primary" type="button" [disabled]="savingAccount" (click)="saveAccount()">{{ savingAccount?t('Guardando…','Saving…'):t('Guardar','Save') }}</button><button class="fin-secondary" type="button" (click)="closeAccountForm()">{{ t('Cancelar','Cancel') }}</button></div>
            </div>
          }
          @if (deleteAccountTarget) {
            <div class="fin-panel" style="margin-top:12px;border-color:#f87171;">
              <p style="margin:0 0 12px;">{{ t('¿Eliminar la cuenta','Delete account') }} <b>{{ deleteAccountTarget.code }}</b>?</p>
              <div style="display:flex;gap:8px;"><button class="fin-primary" type="button" (click)="doDeleteAccount()">{{ t('Eliminar','Delete') }}</button><button class="fin-secondary" type="button" (click)="deleteAccountTarget=null">{{ t('Cancelar','Cancel') }}</button></div>
            </div>
          }
        }

        @if (tab==='journals') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('ASIENTOS', 'JOURNAL ENTRIES') }}</span><h3>{{ t('Asientos contables', 'Journal entries') }}</h3></div><button class="fin-primary" type="button" (click)="loadJournals()" [disabled]="loadingJournals">{{ loadingJournals ? t('Cargando…','Loading…') : t('Actualizar','Refresh') }}</button></div>
            <p class="fin-hint">{{ t('Para crear asientos usa el módulo Finanzas (pestaña Asientos) o próximamente aquí.', 'Create entries from Finance module (Journals tab) or soon here.') }}</p>
            @if (journals.length===0 && !loadingJournals) { <div class="fin-empty">{{ t('No hay asientos.', 'No journal entries.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Número','Number') }}</th><th>{{ t('Fecha','Date') }}</th><th>{{ t('Referencia','Reference') }}</th><th>{{ t('Estado','Status') }}</th><th>{{ t('Débito','Debit') }}</th><th>{{ t('Crédito','Credit') }}</th></tr></thead><tbody>@for (j of journals; track j.id) { <tr><td><b>{{ j.entry_number }}</b></td><td>{{ j.entry_date }}</td><td>{{ j.reference||'—' }}</td><td>{{ j.status }}</td><td>{{ j.total_debit }}</td><td>{{ j.total_credit }}</td></tr> }</tbody></table></div> }
          </div>
        }

        @if (tab==='books') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('LIBROS', 'BOOKS') }}</span><h3>{{ t('Libros contables y registros', 'Accounting books and registers') }}</h3></div></div>
            <div class="fin-form-grid fin-books-filters">
              <label>{{ t('Tipo de libro','Book type') }}
                <select [(ngModel)]="bookType">
                  <option value="journal">{{ t('Libro Diario','General Journal') }}</option>
                  <option value="ledger">{{ t('Libro Mayor','General Ledger') }}</option>
                  <option value="purchase">{{ t('Registro de Compras','Purchase Register (journal)') }}</option>
                  <option value="sales">{{ t('Registro de Ventas','Sales Register (journal)') }}</option>
                  <option value="cash">{{ t('Libro Caja/Bancos','Cash & Bank') }}</option>
                </select>
              </label>
              @if (bookType === 'ledger') {
                <label>{{ t('Año fiscal','Fiscal year') }}<select [(ngModel)]="ledgerFiscalYearId"><option value="">{{ t('Seleccione','Select') }}</option>@for(fy of fiscalYears; track fy.id){<option [value]="fy.id">{{ fy.name }}</option>}</select></label>
                <label>{{ t('Cuenta','Account') }}<select [(ngModel)]="ledgerAccountId"><option value="">{{ t('Seleccione','Select') }}</option>@for(a of accounts; track a.id){<option [value]="a.id">{{ a.code }} - {{ a.name }}</option>}</select></label>
              }
              <label>{{ t('Desde','From') }}<input type="date" [(ngModel)]="bookStart"></label>
              <label>{{ t('Hasta','To') }}<input type="date" [(ngModel)]="bookEnd"></label>
              <button class="fin-primary" type="button" (click)="loadBook()" [disabled]="bookLoading">{{ bookLoading? t('Consultando…','Loading…'):t('Consultar','Query') }}</button>
            </div>
            @if (bookResult) {
              <div class="fin-report-summary">
                @if (bookType==='journal') { <span>{{ t('Débito','Debit') }}: <b>{{ bookResult.total_debit }}</b></span><span>{{ t('Crédito','Credit') }}: <b>{{ bookResult.total_credit }}</b></span> }
                @else if (bookType==='cash') { <span>{{ t('Entradas','Inflows') }}: <b>{{ bookResult.total_inflows }}</b></span><span>{{ t('Salidas','Outflows') }}: <b>{{ bookResult.total_outflows }}</b></span><span>{{ t('Neto','Net') }}: <b>{{ bookResult.net_flow }}</b></span> }
                @else if (bookType==='ledger') { <span>{{ t('Cuenta','Account') }}: <b>{{ bookResult.account_code }} {{ bookResult.account_name }}</b></span><span>{{ t('Saldo inicial','Opening') }}: <b>{{ bookResult.opening_balance }}</b></span><span>{{ t('Saldo final','Closing') }}: <b>{{ bookResult.closing_balance }}</b></span> }
                @else if (bookType==='purchase') { <span>{{ t('Débito','Debit') }}: <b>{{ bookResult.total_debit }}</b></span><span>{{ t('Crédito','Credit') }}: <b>{{ bookResult.total_credit }}</b></span><span>{{ t('Neto','Net') }}: <b>{{ bookResult.net }}</b></span> }
                @else if (bookType==='sales') { <span>{{ t('Débito','Debit') }}: <b>{{ bookResult.total_debit }}</b></span><span>{{ t('Crédito','Credit') }}: <b>{{ bookResult.total_credit }}</b></span><span>{{ t('Neto','Net') }}: <b>{{ bookResult.net }}</b></span> }
              </div>
              <div class="fin-table-wrap"><table class="fin-table">
                @if (bookType==='journal') {
                  <thead><tr><th>{{ t('Fecha','Date') }}</th><th>{{ t('Asiento','Entry') }}</th><th>{{ t('Cuenta','Account') }}</th><th>{{ t('Debe','Debit') }}</th><th>{{ t('Haber','Credit') }}</th></tr></thead>
                  <tbody>@for (row of (bookResult.lines||[]); track $index) { <tr><td>{{ row.entry_date }}</td><td>{{ row.entry_number }}</td><td>{{ row.account_code }} - {{ row.account_name }}</td><td>{{ row.debit }}</td><td>{{ row.credit }}</td></tr> }</tbody>
                } @else if (bookType==='cash') {
                  <thead><tr><th>{{ t('Fecha','Date') }}</th><th>{{ t('Asiento','Entry') }}</th><th>{{ t('Cuenta','Account') }}</th><th>{{ t('Descripción','Description') }}</th><th>{{ t('Debe','Debit') }}</th><th>{{ t('Haber','Credit') }}</th></tr></thead>
                  <tbody>@for (row of (bookResult.movements||[]); track $index) { <tr><td>{{ row.entry_date }}</td><td>{{ row.entry_number }}</td><td>{{ row.account_code }} - {{ row.account_name }}</td><td>{{ row.description||'—' }}</td><td>{{ row.debit }}</td><td>{{ row.credit }}</td></tr> }</tbody>
                } @else if (bookType==='ledger') {
                  <thead><tr><th>{{ t('Fecha','Date') }}</th><th>{{ t('Asiento','Entry') }}</th><th>{{ t('Descripción','Description') }}</th><th>{{ t('Debe','Debit') }}</th><th>{{ t('Haber','Credit') }}</th><th>{{ t('Saldo','Balance') }}</th></tr></thead>
                  <tbody>@for (row of (bookResult.lines||[]); track $index) { <tr><td>{{ row.journal_date || row.entry_date }}</td><td>{{ row.entry_number }}</td><td>{{ row.description||'—' }}</td><td>{{ row.debit_amount||row.debit }}</td><td>{{ row.credit_amount||row.credit }}</td><td>{{ row.running_balance }}</td></tr> }</tbody>
                } @else if (bookType==='purchase' || bookType==='sales') {
                  <thead><tr><th>{{ t('Fecha','Date') }}</th><th>{{ t('Asiento','Entry') }}</th><th>{{ t('Cuenta','Account') }}</th><th>{{ t('Auxiliar','Auxiliary') }}</th><th>{{ t('Debe','Debit') }}</th><th>{{ t('Haber','Credit') }}</th></tr></thead>
                  <tbody>@for (row of (bookResult.movements||[]); track $index) { <tr><td>{{ row.journal_date }}</td><td>{{ row.entry_number }}</td><td>{{ row.account_code }} - {{ row.account_name }}</td><td>{{ row.auxiliary_name||row.auxiliary_code||'—' }}</td><td>{{ row.debit_amount||row.debit }}</td><td>{{ row.credit_amount||row.credit }}</td></tr> }</tbody>
                }
              </table></div>
            } @else if (!bookLoading) {
              <div class="fin-empty">{{ t('Selecciona filtros y consulta.', 'Select filters and query.') }}</div>
            }
          </div>
          <div class="fin-panel" style="margin-top:12px;">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('TIPOS/SERIES DE COMPROBANTE', 'DOCUMENT SERIES') }}</span><h3>{{ t('Facturas, Boletas y otros', 'Invoices, Receipts, etc.') }}</h3></div><button class="fin-secondary" type="button" (click)="loadInvoiceSeries()">{{ t('Cargar series','Load series') }}</button></div>
            <div class="fin-form-grid" style="margin-bottom:8px;">
              <label>{{ t('Tipo','Type') }}<input [(ngModel)]="seriesForm.document_type_code" placeholder="FACTURA/BOLETA"></label>
              <label>{{ t('Serie','Series') }}<input [(ngModel)]="seriesForm.series" placeholder="F001"></label>
              <label>{{ t('Descripción','Description') }}<input [(ngModel)]="seriesForm.description"></label>
              <label><input type="checkbox" [(ngModel)]="seriesForm.is_electronic"> {{ t('Electrónico','Electronic') }}</label>
            </div>
            <button class="fin-primary" type="button" (click)="createInvoiceSeries()">{{ t('Crear serie','Create series') }}</button>
            @if (invoiceSeries.length>0) {
              <div class="fin-table-wrap" style="margin-top:8px;"><table class="fin-table"><thead><tr><th>{{ t('Tipo','Type') }}</th><th>{{ t('Serie','Series') }}</th><th>{{ t('Descripción','Desc.') }}</th><th>{{ t('Electrónico','Electronic') }}</th></tr></thead><tbody>@for(s of invoiceSeries; track s.id){<tr><td>{{ s.document_type_code }}</td><td>{{ s.series }}</td><td>{{ s.description||'—' }}</td><td>{{ s.is_electronic?'Sí':'No' }}</td></tr>}</tbody></table></div>
            }
          </div>
        }
      }
    </section>
  `,
})
export class AccountingComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly companies = inject(CompanyService);
  private readonly language = inject(LanguageService);

  tab: AccTab = 'accounts';
  error = '';
  loadingAccounts = false;
  loadingJournals = false;
  accounts: any[] = [];
  journals: any[] = [];
  fiscalYears: any[] = [];
  bookType: BookType = 'journal';
  bookStart = new Date(Date.now() - 30*86400000).toISOString().slice(0,10);
  bookEnd = new Date().toISOString().slice(0,10);
  bookLoading = false;
  bookResult: any = null;
  ledgerFiscalYearId = '';
  ledgerAccountId = '';
  invoiceSeries: any[] = [];
  seriesLoading = false;
  seriesForm: any = { document_type_code: 'FACTURA', series: '', description: '', is_electronic: false, is_default: false, is_active: true };

  get hasCompany() { return this.companies.hasActiveCompany; }
  get isSpanish() { return this.language.language() === 'es'; }
  t(es: string, en: string) { return this.isSpanish ? es : en; }
  private params() { return { company_id: this.companies.context.selectedCompanyId }; }

  ngOnInit(): void { if (this.hasCompany) { this.loadAccounts(); this.loadFiscalYears(); } }
  setTab(t: AccTab) { this.tab = t; this.error = ''; if (t==='accounts') this.loadAccounts(); if (t==='journals') this.loadJournals(); if (t==='books') { this.loadAccounts(); this.loadFiscalYears(); this.loadInvoiceSeries(); } }
  showAccountForm = false;
  editingAccount: any = null;
  savingAccount = false;
  accountForm: any = { code:'', name:'', account_type:'asset', account_subtype:'', is_group:false, allow_posting:true, is_active:true, currency:'PEN' };
  deleteAccountTarget: any = null;
  loadAccounts() { this.loadingAccounts = true; this.http.get<any[]>('/api/v1/finance/accounts', { params: this.params() }).subscribe({ next: r=>{this.accounts=r||[];this.loadingAccounts=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.loadingAccounts=false;} }); }
  openAccountForm(acc?: any) {
    this.error = '';
    if (acc) { this.editingAccount = acc; this.accountForm = { code:acc.code, name:acc.name, account_type:acc.account_type, account_subtype:acc.account_subtype||'', is_group:!!acc.is_group, allow_posting:acc.allow_posting!==false, is_active:acc.is_active!==false, currency:acc.currency||'PEN' }; }
    else { this.editingAccount = null; this.accountForm = { code:'', name:'', account_type:'asset', account_subtype:'', is_group:false, allow_posting:true, is_active:true, currency:'PEN' }; }
    this.showAccountForm = true;
  }
  closeAccountForm() { this.showAccountForm = false; this.editingAccount = null; }
  saveAccount() {
    if (!this.accountForm.code?.trim() || !this.accountForm.name?.trim()) { this.error = this.t('Código y nombre son requeridos.','Code and name are required.'); return; }
    this.savingAccount = true; this.error = '';
    const payload: any = { ...this.accountForm, account_subtype: this.accountForm.account_subtype || null };
    const req = this.editingAccount
      ? this.http.put(`/api/v1/finance/accounts/${this.editingAccount.id}`, payload)
      : this.http.post('/api/v1/finance/accounts', { company_id: this.companies.context.selectedCompanyId, ...payload });
    req.subscribe({ next: ()=>{ this.savingAccount=false; this.closeAccountForm(); this.loadAccounts(); }, error: e=>{ this.savingAccount=false; this.error=e?.error?.detail||this.t('No se pudo guardar.','Could not save.'); } });
  }
  confirmDeleteAccount(acc: any) { this.deleteAccountTarget = acc; }
  doDeleteAccount() {
    if (!this.deleteAccountTarget) return;
    this.http.delete(`/api/v1/finance/accounts/${this.deleteAccountTarget.id}`).subscribe({ next: ()=>{ this.deleteAccountTarget=null; this.loadAccounts(); }, error: e=>{ this.error=e?.error?.detail||this.t('No se pudo eliminar.','Could not delete.'); this.deleteAccountTarget=null; } });
  }
  loadFiscalYears() { this.http.get<any[]>('/api/v1/finance/fiscal-years', { params: this.params() }).subscribe({ next: r=>{this.fiscalYears=r||[]; if(!this.ledgerFiscalYearId && r?.length) this.ledgerFiscalYearId = r.find((x:any)=>!x.is_closed)?.id || r[0]?.id || '';}, error: ()=>{} }); }
  loadJournals() { this.loadingJournals = true; this.http.get<any[]>('/api/v1/finance/journal-entries', { params: this.params() }).subscribe({ next: r=>{this.journals=(r||[]).slice(0,50);this.loadingJournals=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.loadingJournals=false;} }); }
  loadInvoiceSeries() { this.seriesLoading = true; this.http.get<any[]>('/api/v1/finance/invoice-series', { params: this.params() }).subscribe({ next: r=>{this.invoiceSeries=r||[];this.seriesLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.seriesLoading=false;} }); }
  createInvoiceSeries() {
    if (!this.seriesForm.series) return;
    const payload = { company_id: this.companies.context.selectedCompanyId, ...this.seriesForm };
    this.http.post('/api/v1/finance/invoice-series', payload).subscribe({ next: ()=>{ this.loadInvoiceSeries(); this.seriesForm = { document_type_code:'FACTURA', series:'', description:'', is_electronic:false, is_default:false, is_active:true }; }, error: e=>{ this.error=e?.error?.detail||'Error'; } });
  }
  loadBook() {
    this.bookLoading = true; this.bookResult = null;
    const base = this.params();
    if (this.bookType === 'journal') {
      this.http.get<any>('/api/v1/finance/reports/journal-book', { params: { ...base, start_date: this.bookStart, end_date: this.bookEnd } }).subscribe({ next: r=>{this.bookResult=r;this.bookLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.bookLoading=false;} });
    } else if (this.bookType === 'cash') {
      this.http.get<any>('/api/v1/finance/registers/cash-book', { params: { ...base, start_date: this.bookStart, end_date: this.bookEnd } }).subscribe({ next: r=>{this.bookResult=r;this.bookLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.bookLoading=false;} });
    } else if (this.bookType === 'ledger') {
      if (!this.ledgerFiscalYearId || !this.ledgerAccountId) { this.error = this.t('Seleccione año fiscal y cuenta.', 'Select fiscal year and account.'); this.bookLoading=false; return; }
      this.http.get<any>('/api/v1/finance/reports/general-ledger', { params: { ...base, fiscal_year_id: this.ledgerFiscalYearId, account_id: this.ledgerAccountId } }).subscribe({ next: r=>{this.bookResult=r;this.bookLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.bookLoading=false;} });
    } else if (this.bookType === 'purchase') {
      this.http.get<any>('/api/v1/finance/registers/purchase-journal', { params: { ...base, start_date: this.bookStart, end_date: this.bookEnd } }).subscribe({ next: r=>{this.bookResult=r;this.bookLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.bookLoading=false;} });
    } else if (this.bookType === 'sales') {
      this.http.get<any>('/api/v1/finance/registers/sales-journal', { params: { ...base, start_date: this.bookStart, end_date: this.bookEnd } }).subscribe({ next: r=>{this.bookResult=r;this.bookLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.bookLoading=false;} });
    } else { this.bookLoading = false; }
  }
}
