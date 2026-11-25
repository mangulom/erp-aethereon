import { CommonModule } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CompanyService } from '../../core/company.service';
import { LanguageService } from '../../core/language.service';

type FinanceTab = 'overview' | 'documents' | 'auxiliaries' | 'clients' | 'suppliers' | 'receivables' | 'payables' | 'treasury' | 'assets' | 'projects' | 'config' | 'accounts';

interface AccountRow {
  id: string;
  code: string;
  name: string;
  account_type: string;
  account_subtype?: string | null;
  is_group: boolean;
  allow_posting: boolean;
  is_active: boolean;
  currency: string;
}

interface AuxiliaryRow {
  id: string;
  code: string;
  name: string;
  auxiliary_type: string;
  tax_id?: string | null;
  email?: string | null;
  phone?: string | null;
  is_active: boolean;
}

interface JournalRow {
  id: string;
  entry_number: string;
  entry_date: string;
  description?: string | null;
  reference?: string | null;
  status: string;
  total_debit: number | string;
  total_credit: number | string;
  currency: string;
}

interface FiscalYearRow {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_closed: boolean;
}

@Component({
  selector: 'app-finance',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="fin-workspace finance-advanced">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">{{ t('MÓDULO', 'MODULE') }}</span>
          <h1 class="fin-title-main">{{ t('Finanzas y Tesorería', 'Finance & Treasury') }}</h1>
          <p class="fin-subtitle-desc">{{ t('Control integral: plan de cuentas, asientos, libros, tesorería, activos y proyectos.', 'Full control: accounts, journals, books, treasury, assets, and projects.') }}</p>
        </div>
        <div class="fin-header-actions">
          <a class="fin-secondary fin-link-btn" routerLink="/inteligencia-ia">{{ t('Ir a Inteligencia IA', 'Go to AI Intelligence') }}</a>
        </div>
      </header>

      @if (!hasCompany) {
        <div class="fin-alert" role="alert">{{ t('Selecciona una empresa activa en el encabezado para operar el módulo de Finanzas.', 'Select an active company in the header to use Finance.') }}</div>
      }
      @if (error) {
        <div class="fin-alert fin-alert-error" role="alert">{{ error }}</div>
      }

      @if (hasCompany) {
        <nav class="fin-tabs" aria-label="Secciones de Finanzas">
          <button type="button" [class.active]="tab === 'overview'" (click)="setTab('overview')">{{ t('Resumen', 'Overview') }}</button>
          <button type="button" [class.active]="tab === 'documents'" (click)="setTab('documents')">{{ t('Comprobantes', 'Documents') }}</button>
          <button type="button" [class.active]="tab === 'accounts'" (click)="setTab('accounts')">{{ t('Cuentas contables', 'Chart of accounts') }}</button>
          <button type="button" [class.active]="tab === 'clients'" (click)="setTab('clients')">{{ t('Clientes', 'Customers') }}</button>
          <button type="button" [class.active]="tab === 'suppliers'" (click)="setTab('suppliers')">{{ t('Proveedores', 'Suppliers') }}</button>
          <button type="button" [class.active]="tab === 'auxiliaries'" (click)="setTab('auxiliaries')">{{ t('Auxiliares', 'Auxiliaries') }}</button>
          <button type="button" [class.active]="tab === 'receivables'" (click)="setTab('receivables')">{{ t('Cuentas por cobrar', 'Receivables') }}</button>
          <button type="button" [class.active]="tab === 'payables'" (click)="setTab('payables')">{{ t('Cuentas por pagar', 'Payables') }}</button>
          <button type="button" [class.active]="tab === 'treasury'" (click)="setTab('treasury')">{{ t('Tesorería', 'Treasury') }}</button>
          <button type="button" [class.active]="tab === 'assets'" (click)="setTab('assets')">{{ t('Activos fijos', 'Fixed assets') }}</button>
          <button type="button" [class.active]="tab === 'projects'" (click)="setTab('projects')">{{ t('Proyectos / CC', 'Projects / Cost centers') }}</button>
          <button type="button" [class.active]="tab === 'config'" (click)="setTab('config')">{{ t('Configuración', 'Configuration') }}</button>
        </nav>

        @if (loading) { <div class="fin-notice">{{ t('Cargando datos…', 'Loading data…') }}</div> }

        @if (tab === 'overview') {
          <div class="fin-overview-grid">
            <article class="fin-kpi-card"><span class="panel-kicker">{{ t('AUXILIARES', 'AUXILIARIES') }}</span><div class="fin-kpi-value">{{ auxiliaries.length }}</div><p class="fin-kpi-sub">{{ t('Terceros contables', 'Accounting third parties') }}</p><button class="fin-secondary" type="button" (click)="setTab('auxiliaries')">{{ t('Gestionar', 'Manage') }}</button></article>
            <article class="fin-kpi-card"><span class="panel-kicker">{{ t('CONTABILIDAD', 'ACCOUNTING') }}</span><div class="fin-kpi-value">→</div><p class="fin-kpi-sub">{{ t('Plan de cuentas, asientos y libros.', 'Chart, journals and books.') }}</p><a class="fin-secondary fin-link-btn" routerLink="/accounting">{{ t('Abrir', 'Open') }}</a></article>
            <article class="fin-kpi-card"><span class="panel-kicker">{{ t('PRESUPUESTOS', 'BUDGETS') }}</span><div class="fin-kpi-value">→</div><p class="fin-kpi-sub">{{ t('Planificación y control.', 'Planning and control.') }}</p><a class="fin-secondary fin-link-btn" routerLink="/budgets">{{ t('Abrir', 'Open') }}</a></article>
            <article class="fin-kpi-card fin-kpi-accent"><span class="panel-kicker">{{ t('IA FINANCIERA', 'FINANCIAL AI') }}</span><div class="fin-kpi-value">AI</div><p class="fin-kpi-sub">{{ t('Pronósticos y análisis inteligente.', 'Forecasts and smart analytics.') }}</p><a class="fin-primary fin-link-btn" routerLink="/inteligencia-ia">{{ t('Abrir IA', 'Open AI') }}</a></article>
          </div>
          <div class="fin-panel"><div class="fin-panel-title"><div><span class="panel-kicker">{{ t('EJERCICIOS FISCALES', 'FISCAL YEARS') }}</span><h3>{{ t('Años fiscales', 'Fiscal years') }}</h3></div><button class="fin-secondary" type="button" (click)="loadFiscalYears()">{{ t('Actualizar', 'Refresh') }}</button></div>
            @if (fiscalYears.length === 0) { <div class="fin-empty">{{ t('Sin ejercicios fiscales.', 'No fiscal years.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Nombre', 'Name') }}</th><th>{{ t('Inicio', 'Start') }}</th><th>{{ t('Fin', 'End') }}</th><th>{{ t('Estado', 'Status') }}</th></tr></thead><tbody>@for (fy of fiscalYears; track fy.id) { <tr><td><b>{{ fy.name }}</b></td><td>{{ fy.start_date }}</td><td>{{ fy.end_date }}</td><td>{{ fy.is_closed ? t('Cerrado', 'Closed') : t('Abierto', 'Open') }}</td></tr> }</tbody></table></div> }
          </div>
        }

        @if (tab === 'documents') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('COMPROBANTES', 'DOCUMENTS') }}</span><h3>{{ t('Documentos financieros', 'Financial documents') }}</h3></div><button class="fin-primary" type="button" (click)="loadDocuments()" [disabled]="docsLoading">{{ docsLoading ? t('Cargando…','Loading…') : t('Actualizar','Refresh') }}</button></div>
            @if (documents.length === 0 && !docsLoading) { <div class="fin-empty">{{ t('No hay comprobantes registrados.', 'No documents registered.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Tipo','Type') }}</th><th>{{ t('Serie/Número','Series/Number') }}</th><th>{{ t('Fecha','Date') }}</th><th>{{ t('Tercero','Party') }}</th><th>{{ t('Total','Total') }}</th><th>{{ t('Estado','Status') }}</th></tr></thead><tbody>@for (d of documents; track d.id) { <tr><td>{{ d.document_type }}</td><td>{{ d.series }}-{{ d.number }}</td><td>{{ d.issue_date }}</td><td>{{ d.party_name || '—' }}</td><td>{{ d.total_amount }} {{ d.currency }}</td><td>{{ d.status }}</td></tr> }</tbody></table></div> }
          </div>
        }

        @if (tab === 'auxiliaries') {
          <div class="fin-panel"><div class="fin-panel-title"><div><span class="panel-kicker">{{ t('AUXILIARES', 'AUXILIARIES') }}</span><h3>{{ t('Terceros contables', 'Accounting third parties') }}</h3></div><button class="fin-primary" type="button" (click)="loadAuxiliaries()" [disabled]="loadingAux">{{ loadingAux ? t('Cargando…', 'Loading…') : t('Actualizar', 'Refresh') }}</button></div>
            @if (auxiliaries.length === 0 && !loadingAux) { <div class="fin-empty">{{ t('No hay auxiliares.', 'No auxiliaries.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Código', 'Code') }}</th><th>{{ t('Nombre', 'Name') }}</th><th>{{ t('Tipo', 'Type') }}</th><th>{{ t('RUC/DNI', 'Tax ID') }}</th><th>{{ t('Estado', 'Status') }}</th></tr></thead><tbody>@for (x of auxiliaries; track x.id) { <tr><td>{{ x.code }}</td><td><b>{{ x.name }}</b></td><td>{{ x.auxiliary_type }}</td><td>{{ x.tax_id || '—' }}</td><td>{{ x.is_active ? t('Activo', 'Active') : t('Inactivo', 'Inactive') }}</td></tr> }</tbody></table></div> }
          </div>
        }

        @if (tab === 'receivables') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('CUENTAS POR COBRAR', 'ACCOUNTS RECEIVABLE') }}</span><h3>{{ t('Aging de cartera', 'Receivables aging') }}</h3></div><button class="fin-primary" type="button" (click)="loadReceivablesAging()" [disabled]="arLoading">{{ arLoading ? t('Cargando…', 'Loading…') : t('Actualizar', 'Refresh') }}</button></div>
            <div class="fin-form-grid fin-books-filters">
              <label>{{ t('Fecha corte', 'As of date') }}<input type="date" [(ngModel)]="agingAsOf"></label>
              <button class="fin-secondary" type="button" (click)="loadReceivablesAging()" [disabled]="arLoading">{{ t('Consultar', 'Query') }}</button>
            </div>
            @if (receivablesAging) {
              <div class="fin-report-summary">
                <span>{{ t('0-30 días', '0-30 days') }}: <b>{{ receivablesAging.buckets?.['0_30'] || '0' }}</b></span>
                <span>{{ t('31-60 días', '31-60 days') }}: <b>{{ receivablesAging.buckets?.['31_60'] || '0' }}</b></span>
                <span>{{ t('61-90 días', '61-90 days') }}: <b>{{ receivablesAging.buckets?.['61_90'] || '0' }}</b></span>
                <span>{{ t('90+ días', '90+ days') }}: <b>{{ receivablesAging.buckets?.['90_plus'] || '0' }}</b></span>
                <span>{{ t('Total', 'Total') }}: <b>{{ receivablesAging.total || '0' }}</b></span>
              </div>
            } @else {
              <div class="fin-empty">{{ t('Consulta el aging de cartera para ver resultados.', 'Query receivables aging to see results.') }}</div>
            }
            <h4 class="fin-subtitle" style="margin-top:1rem;">{{ t('Documentos de venta (recientes)', 'Sales documents (recent)') }}</h4>
            @if (docsLoading) { <div class="fin-notice">{{ t('Cargando documentos…', 'Loading documents…') }}</div> }
            @else if (receivableDocs.length === 0) { <div class="fin-empty">{{ t('No hay documentos de venta cargados.', 'No sales documents loaded.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Tipo', 'Type') }}</th><th>{{ t('Serie/Número', 'Series/No') }}</th><th>{{ t('Fecha', 'Date') }}</th><th>{{ t('Total', 'Total') }}</th><th>{{ t('Estado', 'Status') }}</th></tr></thead><tbody>@for (d of receivableDocs; track d.id) { <tr><td>{{ d.document_type || '—' }}</td><td>{{ d.series || '' }}-{{ d.voucher_number || d.number || '—' }}</td><td>{{ d.issue_date || d.date || '—' }}</td><td>{{ d.total_amount || d.total || '—' }}</td><td>{{ d.status || '—' }}</td></tr> }</tbody></table></div> }
          </div>
        }

        @if (tab === 'payables') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('CUENTAS POR PAGAR', 'ACCOUNTS PAYABLE') }}</span><h3>{{ t('Aging de obligaciones', 'Payables aging') }}</h3></div><button class="fin-primary" type="button" (click)="loadPayablesAging()" [disabled]="apLoading">{{ apLoading ? t('Cargando…', 'Loading…') : t('Actualizar', 'Refresh') }}</button></div>
            <div class="fin-form-grid fin-books-filters">
              <label>{{ t('Fecha corte', 'As of date') }}<input type="date" [(ngModel)]="agingAsOf"></label>
              <button class="fin-secondary" type="button" (click)="loadPayablesAging()" [disabled]="apLoading">{{ t('Consultar', 'Query') }}</button>
            </div>
            @if (payablesAging) {
              <div class="fin-report-summary">
                <span>{{ t('0-30 días', '0-30 days') }}: <b>{{ payablesAging.buckets?.['0_30'] || '0' }}</b></span>
                <span>{{ t('31-60 días', '31-60 days') }}: <b>{{ payablesAging.buckets?.['31_60'] || '0' }}</b></span>
                <span>{{ t('61-90 días', '61-90 days') }}: <b>{{ payablesAging.buckets?.['61_90'] || '0' }}</b></span>
                <span>{{ t('90+ días', '90+ days') }}: <b>{{ payablesAging.buckets?.['90_plus'] || '0' }}</b></span>
                <span>{{ t('Total', 'Total') }}: <b>{{ payablesAging.total || '0' }}</b></span>
              </div>
            } @else {
              <div class="fin-empty">{{ t('Consulta el aging de obligaciones para ver resultados.', 'Query payables aging to see results.') }}</div>
            }
            <h4 class="fin-subtitle" style="margin-top:1rem;">{{ t('Documentos de compra (recientes)', 'Purchase documents (recent)') }}</h4>
            @if (docsLoading) { <div class="fin-notice">{{ t('Cargando documentos…', 'Loading documents…') }}</div> }
            @else if (payableDocs.length === 0) { <div class="fin-empty">{{ t('No hay documentos de compra cargados.', 'No purchase documents loaded.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Tipo', 'Type') }}</th><th>{{ t('Serie/Número', 'Series/No') }}</th><th>{{ t('Fecha', 'Date') }}</th><th>{{ t('Total', 'Total') }}</th><th>{{ t('Estado', 'Status') }}</th></tr></thead><tbody>@for (d of payableDocs; track d.id) { <tr><td>{{ d.document_type || '—' }}</td><td>{{ d.series || '' }}-{{ d.voucher_number || d.number || '—' }}</td><td>{{ d.issue_date || d.date || '—' }}</td><td>{{ d.total_amount || d.total || '—' }}</td><td>{{ d.status || '—' }}</td></tr> }</tbody></table></div> }
          </div>
        }

                @if (tab === 'treasury') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('TESORERÍA', 'TREASURY') }}</span><h3>{{ t('Cuentas bancarias', 'Bank accounts') }}</h3></div><div style="display:flex;gap:8px;"><button class="fin-secondary" type="button" (click)="loadBankAccounts()" [disabled]="bankLoading">{{ bankLoading ? t('Cargando…', 'Loading…') : t('Actualizar', 'Refresh') }}</button><button class="fin-primary" type="button" (click)="openBankForm()">{{ t('Nueva cuenta bancaria', 'New bank account') }}</button></div></div>
            @if (showBankForm) {
              <div class="fin-form-grid" style="margin:12px 0;">
                <label>{{ t('Cuenta contable (caja/banco)', 'GL account (cash/bank)') }}<select [(ngModel)]="bankForm.account_id"><option value="">{{ t('Seleccione', 'Select') }}</option>@for (a of accounts; track a.id) { @if (a.account_subtype==='cash' || a.account_subtype==='bank' || a.account_type==='asset') { <option [value]="a.id">{{ a.code }} - {{ a.name }}</option> } }</select></label>
                <label>{{ t('Banco (catálogo)', 'Bank (catalog)') }}<select [(ngModel)]="bankForm.bank_id"><option value="">{{ t('Seleccione...', 'Select...') }}</option>@for (bk of banks; track bk.id) { <option [value]="bk.id">{{ bk.name }}</option> }</select></label>
                @if (!bankForm.bank_id) { <label>{{ t('Nombre banco (manual)', 'Bank name (manual)') }}<input [(ngModel)]="bankForm.bank_name"></label> }
                <label>{{ t('Nombre cuenta', 'Account name') }}<input [(ngModel)]="bankForm.account_name"></label>
                <label>{{ t('Nº/Enmascarado', 'Number masked') }}<input [(ngModel)]="bankForm.account_number_masked"></label>
                <label>{{ t('Moneda', 'Currency') }}<input [(ngModel)]="bankForm.currency"></label>
                <label>{{ t('Activa', 'Active') }}<select [(ngModel)]="bankForm.is_active"><option [ngValue]="true">{{ t('Sí','Yes') }}</option><option [ngValue]="false">{{ t('No','No') }}</option></select></label>
              </div>
              <div style="display:flex;gap:8px;margin-bottom:12px;"><button class="fin-primary" type="button" [disabled]="bankFormSaving" (click)="saveBankAccount()">{{ bankFormSaving ? t('Guardando…','Saving…') : t('Guardar','Save') }}</button><button class="fin-secondary" type="button" (click)="closeBankForm()">{{ t('Cancelar','Cancel') }}</button></div>
            }
            @if (bankAccounts.length === 0 && !bankLoading) { <div class="fin-empty">{{ t('No hay cuentas bancarias configuradas.', 'No bank accounts configured.') }}</div> }
            @else {
              <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Banco', 'Bank') }}</th><th>{{ t('Número', 'Number') }}</th><th>{{ t('Moneda', 'Currency') }}</th><th>{{ t('Cuenta contable', 'GL account') }}</th><th>{{ t('Acciones','Actions') }}</th></tr></thead><tbody>@for (b of bankAccounts; track b.id) { <tr><td><b>{{ b.bank_name || '—' }}</b></td><td>{{ b.account_number_masked || b.account_number || '—' }}</td><td>{{ b.currency || 'PEN' }}</td><td>{{ b.account_code || b.account_id || '—' }}</td><td><button class="fin-secondary" type="button" (click)="openBankForm(b)">{{ t('Editar','Edit') }}</button> <button class="fin-secondary" type="button" (click)="deleteBankAccount(b.id)">{{ t('Eliminar','Delete') }}</button></td></tr> }</tbody></table></div>
              <div class="fin-form-grid fin-books-filters" style="margin-top:12px;">
                <label>{{ t('Ver movimientos de', 'View movements for') }}
                  <select [(ngModel)]="selectedBankAccountId" (ngModelChange)="loadStatementLines()">
                    <option value="">{{ t('Seleccione cuenta', 'Select account') }}</option>
                    @for (b of bankAccounts; track b.id) { <option [value]="b.id">{{ b.bank_name }} - {{ b.account_number_masked || b.account_number }}</option> }
                  </select>
                </label>
              </div>
              @if (statementLoading) { <div class="fin-notice">{{ t('Cargando movimientos…', 'Loading movements…') }}</div> }
              @else if (selectedBankAccountId && bankStatementLines.length === 0) { <div class="fin-empty">{{ t('Sin movimientos registrados.', 'No statement lines.') }}</div> }
              @else if (bankStatementLines.length > 0) { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Fecha', 'Date') }}</th><th>{{ t('Descripción', 'Description') }}</th><th>{{ t('Monto', 'Amount') }}</th><th>{{ t('Referencia', 'Reference') }}</th></tr></thead><tbody>@for (s of bankStatementLines; track s.id) { <tr><td>{{ s.transaction_date || s.date || '—' }}</td><td>{{ s.description || '—' }}</td><td>{{ s.amount || '—' }}</td><td>{{ s.reference || '—' }}</td></tr> }</tbody></table></div> }
            }
          </div>
        }
@if (tab === 'accounts') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('CONTABILIDAD', 'ACCOUNTING') }}</span><h3>{{ t('Cuentas contables', 'Chart of accounts') }}</h3></div><button class="fin-secondary" type="button" (click)="loadAccounts()">{{ t('Actualizar', 'Refresh') }}</button></div>
            @if (loadingAccounts) { <div class="fin-notice">{{ t('Cargando…', 'Loading…') }}</div> }
            @if (!loadingAccounts && accounts.length === 0) { <div class="fin-empty">{{ t('Sin cuentas.', 'No accounts.') }}</div> }
            @if (accounts.length > 0) { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Código', 'Code') }}</th><th>{{ t('Nombre', 'Name') }}</th><th>{{ t('Tipo', 'Type') }}</th><th>{{ t('Activa', 'Active') }}</th></tr></thead><tbody>@for (a of accounts; track a.id) { <tr><td>{{ a.code }}</td><td>{{ a.name }}</td><td>{{ a.account_type }}</td><td>{{ a.is_active ? t('Sí','Yes') : t('No','No') }}</td></tr> }</tbody></table></div> }
          </div>
        }
        @if (tab === 'clients' || tab === 'suppliers' || tab === 'auxiliaries') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('TERCEROS', 'THIRD PARTIES') }}</span><h3>{{ tab==='clients' ? t('Clientes','Customers') : (tab==='suppliers' ? t('Proveedores','Suppliers') : t('Auxiliares','Auxiliaries')) }}</h3></div><div style="display:flex;gap:8px;"><button class="fin-secondary" type="button" (click)="loadAuxiliaries()">{{ t('Actualizar','Refresh') }}</button><button class="fin-primary" type="button" (click)="openAuxForm()">{{ t('Nuevo','New') }}</button></div></div>
            @if (showAuxForm) {
              <div class="fin-form-grid" style="margin:12px 0;">
                <label>{{ t('Código','Code') }}<input [(ngModel)]="auxForm.code"></label>
                <label>{{ t('Nombre','Name') }}<input [(ngModel)]="auxForm.name"></label>
                <label>{{ t('Tipo','Type') }}<select [(ngModel)]="auxForm.auxiliary_type"><option value="customer">{{ t('Cliente','Customer') }}</option><option value="supplier">{{ t('Proveedor','Supplier') }}</option><option value="employee">{{ t('Empleado','Employee') }}</option><option value="other">{{ t('Otro','Other') }}</option></select></label>
                <label>{{ t('RUC/ID','Tax ID') }}<input [(ngModel)]="auxForm.tax_id"></label>
                <label>{{ t('Email','Email') }}<input [(ngModel)]="auxForm.email"></label>
                <label>{{ t('Teléfono','Phone') }}<input [(ngModel)]="auxForm.phone"></label>
              </div>
              <div style="display:flex;gap:8px;margin-bottom:12px;"><button class="fin-primary" type="button" [disabled]="auxFormSaving" (click)="saveAuxiliary()">{{ auxFormSaving ? t('Guardando…','Saving…') : t('Guardar','Save') }}</button><button class="fin-secondary" type="button" (click)="closeAuxForm()">{{ t('Cancelar','Cancel') }}</button></div>
            }
            @if (loadingAux) { <div class="fin-notice">{{ t('Cargando…','Loading…') }}</div> }
            @if (!loadingAux && filteredAuxiliaries().length === 0) { <div class="fin-empty">{{ t('Sin registros.','No records.') }}</div> }
            @if (filteredAuxiliaries().length > 0) { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Código','Code') }}</th><th>{{ t('Nombre','Name') }}</th><th>{{ t('Tipo','Type') }}</th><th>{{ t('RUC/ID','Tax ID') }}</th><th>{{ t('Acciones','Actions') }}</th></tr></thead><tbody>@for (a of filteredAuxiliaries(); track a.id) { <tr><td>{{ a.code }}</td><td>{{ a.name }}</td><td>{{ a.auxiliary_type }}</td><td>{{ a.tax_id || '—' }}</td><td><button class="fin-secondary" type="button" (click)="openAuxForm(a)">{{ t('Editar','Edit') }}</button> <button class="fin-secondary" type="button" (click)="deactivateAux(a)">{{ t('Desactivar','Deactivate') }}</button></td></tr> }</tbody></table></div> }
          </div>
        }
        @if (tab === 'config') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('CONFIGURACIÓN FINANCIERA', 'FINANCE CONFIGURATION') }}</span><h3>{{ t('Parámetros y ejercicios', 'Parameters and fiscal setup') }}</h3></div></div>
            <p class="fin-hint">{{ t('Desde aquí puedes revisar ejercicios fiscales y el catálogo de bancos para cuentas bancarias.', 'Review fiscal years and bank catalog for bank accounts.') }}</p>
            <div class="fin-panel-title" style="margin-top:1rem;"><div><h4 class="fin-subtitle" style="margin:0;">{{ t('Ejercicios fiscales', 'Fiscal years') }}</h4></div><button class="fin-secondary" type="button" (click)="loadFiscalYears()">{{ t('Actualizar', 'Refresh') }}</button></div>
            @if (fiscalYears.length === 0) { <div class="fin-empty">{{ t('Sin ejercicios fiscales.', 'No fiscal years.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Nombre', 'Name') }}</th><th>{{ t('Inicio', 'Start') }}</th><th>{{ t('Fin', 'End') }}</th><th>{{ t('Cerrado', 'Closed') }}</th></tr></thead><tbody>@for (fy of fiscalYears; track fy.id) { <tr><td>{{ fy.name }}</td><td>{{ fy.start_date }}</td><td>{{ fy.end_date }}</td><td>{{ fy.is_closed ? t('Sí', 'Yes') : t('No', 'No') }}</td></tr> }</tbody></table></div> }
            <div class="fin-panel-title" style="margin-top:1.5rem;"><div><h4 class="fin-subtitle" style="margin:0;">{{ t('Bancos (catálogo)', 'Banks (catalog)') }}</h4></div><div style="display:flex;gap:8px;"><button class="fin-secondary" type="button" (click)="loadBanks()">{{ t('Actualizar','Refresh') }}</button><button class="fin-primary" type="button" (click)="openBankEntityForm()">{{ t('Nuevo banco','New bank') }}</button></div></div>
            @if (showBankEntityForm) {
              <div class="fin-form-grid" style="margin:12px 0;">
                <label>{{ t('Código','Code') }}<input [(ngModel)]="bankEntityForm.code"></label>
                <label>{{ t('Nombre','Name') }}<input [(ngModel)]="bankEntityForm.name"></label>
                <label>{{ t('Activo','Active') }}<select [(ngModel)]="bankEntityForm.is_active"><option [ngValue]="true">{{ t('Sí','Yes') }}</option><option [ngValue]="false">{{ t('No','No') }}</option></select></label>
              </div>
              <div style="display:flex;gap:8px;margin-bottom:12px;"><button class="fin-primary" type="button" [disabled]="bankEntitySaving" (click)="saveBankEntity()">{{ bankEntitySaving ? t('Guardando…','Saving…') : t('Guardar','Save') }}</button><button class="fin-secondary" type="button" (click)="closeBankEntityForm()">{{ t('Cancelar','Cancel') }}</button></div>
            }
            @if (banks.length === 0) { <div class="fin-empty">{{ t('Sin bancos en catálogo.', 'No banks in catalog.') }}</div> }
            @if (banks.length > 0) { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Código','Code') }}</th><th>{{ t('Nombre','Name') }}</th><th>{{ t('Activo','Active') }}</th><th>{{ t('Acciones','Actions') }}</th></tr></thead><tbody>@for (bk of banks; track bk.id) { <tr><td>{{ bk.code || '—' }}</td><td>{{ bk.name }}</td><td>{{ bk.is_active ? t('Sí','Yes') : t('No','No') }}</td><td><button class="fin-secondary" type="button" (click)="openBankEntityForm(bk)">{{ t('Editar','Edit') }}</button> <button class="fin-secondary" type="button" (click)="deleteBankEntity(bk.id)">{{ t('Eliminar','Delete') }}</button></td></tr> }</tbody></table></div> }
          </div>
        }
      }
    </section>
  `,
})
export class FinanceComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly companies = inject(CompanyService);
  private readonly language = inject(LanguageService);

  tab: FinanceTab = 'overview';
  loading = false;
  loadingAccounts = false;
  loadingAux = false;
  loadingJournals = false;
  error = '';

  accounts: AccountRow[] = [];
  auxiliaries: AuxiliaryRow[] = [];
  auxTypeFilter: 'all' | 'customer' | 'supplier' = 'all';
  showAuxForm = false;
  auxFormSaving = false;
  editingAuxId: string | null = null;
  auxForm: any = { code: '', name: '', auxiliary_type: 'customer', tax_id: '', email: '', phone: '', address: '', is_active: true };
  journals: JournalRow[] = [];
  fiscalYears: FiscalYearRow[] = [];
  selectedJournal: any = null;
  journalDetailLoading = false;

  showJournalForm = false;
  journalFormLoading = false;
  journalForm: any = {
    entry_number: '',
    entry_date: this.isoDate(0),
    reference: '',
    description: '',
    currency: 'PEN',
    lines: [
      { account_id: '', description: '', debit_amount: '0', credit_amount: '0' },
      { account_id: '', description: '', debit_amount: '0', credit_amount: '0' }
    ]
  };

  bookType: 'journal' | 'cash' = 'journal';
  bookStart = this.isoDate(-30);
  bookEnd = this.isoDate(0);
  bookLoading = false;
  bookResult: any = null;

  assets: any[] = [];
  assetsLoading = false;

  projects: any[] = [];
  costCenters: any[] = [];
  pcLoading = false;

  agingAsOf = this.isoDate(0);
  receivablesAging: any = null;
  payablesAging: any = null;
  arLoading = false;
  apLoading = false;
  receivableDocs: any[] = [];
  payableDocs: any[] = [];
  docsLoading = false;
  documents: any[] = [];

  bankAccounts: any[] = [];
  banks: any[] = [];
  bankLoading = false;
  selectedBankAccountId = '';
  bankStatementLines: any[] = [];
  statementLoading = false;
  showBankForm = false;
  bankFormSaving = false;
  editingBankId: string | null = null;
  bankForm: any = { account_id: '', bank_id: '', bank_name: '', account_name: '', account_number_masked: '', currency: 'PEN', is_active: true };
  showBankEntityForm = false;
  bankEntitySaving = false;
  editingBankEntityId: string | null = null;
  bankEntityForm: any = { code: '', name: '', is_active: true };

  get companyId(): string {
    return this.companies.hasActiveCompany ? this.companies.context.selectedCompanyId : '';
  }
  get hasCompany(): boolean {
    return this.companies.hasActiveCompany;
  }
  get isSpanish(): boolean {
    return this.language.language() === 'es';
  }
  t(es: string, en: string): string {
    return this.isSpanish ? es : en;
  }

  ngOnInit(): void {
    if (this.hasCompany) this.loadOverviewData();
  }

  setTab(t: FinanceTab): void {
    this.tab = t;
    this.error = '';
    if (!this.hasCompany) return;
    if (t === 'overview') this.loadOverviewData();
    if (t === 'documents') this.loadDocuments();
    if (t === 'auxiliaries') { this.auxTypeFilter = 'all'; this.loadAuxiliaries(); }
    if (t === 'clients') { this.auxTypeFilter = 'customer'; this.loadAuxiliaries(); }
    if (t === 'suppliers') { this.auxTypeFilter = 'supplier'; this.loadAuxiliaries(); }
    if (t === 'accounts') this.loadAccounts();
    if (t === 'assets') this.loadAssets();
    if (t === 'projects') this.loadProjectsAndCostCenters();
    if (t === 'receivables') this.loadReceivablesAging();
    if (t === 'payables') this.loadPayablesAging();
    if (t === 'treasury') this.loadBankAccounts();
    if (t === 'config') { this.loadFiscalYears(); this.loadBanks(); }
  }

  private isoDate(offsetDays: number): string {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    return d.toISOString().slice(0, 10);
  }
  private params(): Record<string, string> {
    return { company_id: this.companyId };
  }

  docsSummary: any = null;
  loadOverviewData(): void {
    this.loading = true;
    this.loadFiscalYears();
    this.loadAuxiliaries(true);
    this.http.get<any>('/api/v1/finance/documents-summary', { params: this.params() }).subscribe({
      next: (r) => (this.docsSummary = r),
      error: () => (this.docsSummary = null)
    });
    setTimeout(() => (this.loading = false), 400);
  }

  loadFiscalYears(): void {
    this.http.get<FiscalYearRow[]>('/api/v1/finance/fiscal-years', { params: this.params() }).subscribe({
      next: (r) => (this.fiscalYears = r || []),
      error: (e) => this.handleError(e)
    });
  }

  loadAccounts(silent = false): void {
    if (!silent) this.loadingAccounts = true;
    this.http.get<AccountRow[]>('/api/v1/finance/accounts', { params: this.params() }).subscribe({
      next: (r) => { this.accounts = r || []; this.loadingAccounts = false; },
      error: (e) => { this.handleError(e); this.loadingAccounts = false; }
    });
  }

  loadAuxiliaries(silent = false): void {
    if (!silent) this.loadingAux = true;
    this.http.get<AuxiliaryRow[]>('/api/v1/finance/auxiliaries', { params: this.params() }).subscribe({
      next: (r) => { this.auxiliaries = r || []; this.loadingAux = false; },
      error: (e) => { this.handleError(e); this.loadingAux = false; }
    });
  }
  filteredAuxiliaries(): AuxiliaryRow[] {
    if (this.auxTypeFilter === 'all') return this.auxiliaries;
    return this.auxiliaries.filter(a => (a as any).auxiliary_type === this.auxTypeFilter);
  }
  openAuxForm(a?: any): void {
    this.showAuxForm = true; this.error = '';
    if (a) {
      this.editingAuxId = a.id;
      this.auxForm = { code: a.code || '', name: a.name || '', auxiliary_type: a.auxiliary_type || 'customer', tax_id: a.tax_id || '', email: a.email || '', phone: a.phone || '', address: a.address || '', is_active: a.is_active !== false };
    } else {
      this.editingAuxId = null;
      this.auxForm = { code: '', name: '', auxiliary_type: this.auxTypeFilter === 'supplier' ? 'supplier' : 'customer', tax_id: '', email: '', phone: '', address: '', is_active: true };
    }
  }
  closeAuxForm(): void { this.showAuxForm = false; this.editingAuxId = null; }
  saveAuxiliary(): void {
    if (!this.auxForm.code || !this.auxForm.name) { this.error = this.t('Código y nombre son obligatorios.', 'Code and name are required.'); return; }
    this.auxFormSaving = true;
    const payload: any = { ...this.auxForm };
    if (this.editingAuxId) {
      this.http.patch(`/api/v1/finance/auxiliaries/${this.editingAuxId}`, payload).subscribe({
        next: () => { this.auxFormSaving = false; this.closeAuxForm(); this.loadAuxiliaries(); },
        error: (e) => { this.handleError(e); this.auxFormSaving = false; }
      });
    } else {
      payload.company_id = this.companyId;
      this.http.post('/api/v1/finance/auxiliaries', payload).subscribe({
        next: () => { this.auxFormSaving = false; this.closeAuxForm(); this.loadAuxiliaries(); },
        error: (e) => { this.handleError(e); this.auxFormSaving = false; }
      });
    }
  }
  deactivateAux(a: any): void {
    if (!confirm(this.t('¿Desactivar este auxiliar?', 'Deactivate this auxiliary?'))) return;
    this.http.delete(`/api/v1/finance/auxiliaries/${a.id}`).subscribe({
      next: () => this.loadAuxiliaries(),
      error: (e) => this.handleError(e)
    });
  }

  loadJournals(silent = false): void {
    if (!silent) this.loadingJournals = true;
    this.selectedJournal = null;
    this.http.get<JournalRow[]>('/api/v1/finance/journal-entries', { params: this.params() }).subscribe({
      next: (r) => { this.journals = (r || []).slice(0, 50); this.loadingJournals = false; },
      error: (e) => { this.handleError(e); this.loadingJournals = false; }
    });
  }

  openJournal(id: string): void {
    this.journalDetailLoading = true;
    this.selectedJournal = null;
    this.http.get<any>(`/api/v1/finance/journal-entries/${id}`, { params: this.params() }).subscribe({
      next: (r) => { this.selectedJournal = r; this.journalDetailLoading = false; },
      error: (e) => { this.handleError(e); this.journalDetailLoading = false; }
    });
  }

  closeJournal(): void {
    this.selectedJournal = null;
  }

  openJournalForm(): void {
    this.showJournalForm = true;
    this.error = '';
    if (this.accounts.length === 0) this.loadAccounts(true);
    this.journalForm = {
      entry_number: '',
      entry_date: this.isoDate(0),
      reference: '',
      description: '',
      currency: 'PEN',
      lines: [
        { account_id: '', description: '', debit_amount: '0', credit_amount: '0', line_number: 1 },
        { account_id: '', description: '', debit_amount: '0', credit_amount: '0', line_number: 2 }
      ]
    };
  }

  closeJournalForm(): void {
    this.showJournalForm = false;
  }

  addJournalLine(): void {
    const n = this.journalForm.lines.length + 1;
    this.journalForm.lines.push({ account_id: '', description: '', debit_amount: '0', credit_amount: '0', line_number: n });
  }

  removeJournalLine(i: number): void {
    if (this.journalForm.lines.length <= 2) return;
    this.journalForm.lines.splice(i, 1);
    this.journalForm.lines.forEach((ln: any, idx: number) => ln.line_number = idx + 1);
  }

  createJournal(): void {
    const fy = this.fiscalYears.find(f => !f.is_closed) || this.fiscalYears[0];
    if (!fy) { this.error = this.t('No hay ejercicio fiscal disponible.', 'No fiscal year available.'); return; }
    if (!this.journalForm.entry_number || !this.journalForm.entry_date) {
      this.error = this.t('Número y fecha son obligatorios.', 'Number and date are required.'); return;
    }
    const lines = this.journalForm.lines.map((ln: any, idx: number) => ({
      account_id: ln.account_id,
      line_number: idx + 1,
      description: ln.description || null,
      debit_amount: String(ln.debit_amount || '0'),
      credit_amount: String(ln.credit_amount || '0')
    })).filter((ln: any) => ln.account_id);
    if (lines.length < 2) { this.error = this.t('Debe haber al menos 2 líneas con cuenta.', 'At least 2 lines with account are required.'); return; }
    const payload = {
      company_id: this.companyId,
      fiscal_year_id: fy.id,
      entry_number: this.journalForm.entry_number,
      entry_date: this.journalForm.entry_date,
      reference: this.journalForm.reference || null,
      description: this.journalForm.description || null,
      currency: this.journalForm.currency || 'PEN',
      exchange_rate: '1',
      lines
    };
    this.journalFormLoading = true;
    this.http.post('/api/v1/finance/journal-entries', payload).subscribe({
      next: () => {
        this.journalFormLoading = false;
        this.showJournalForm = false;
        this.loadJournals();
      },
      error: (e) => { this.error = e?.error?.detail || this.t('Error al crear asiento.', 'Error creating journal entry.'); this.journalFormLoading = false; }
    });
  }

  loadBook(): void {
    this.bookLoading = true;
    this.bookResult = null;
    const p = { ...this.params(), start_date: this.bookStart, end_date: this.bookEnd };
    const url = this.bookType === 'journal' ? '/api/v1/finance/reports/journal-book' : '/api/v1/finance/registers/cash-book';
    this.http.get<any>(url, { params: p }).subscribe({
      next: (r) => { this.bookResult = r; this.bookLoading = false; },
      error: (e) => { this.handleError(e); this.bookLoading = false; }
    });
  }

  loadAssets(): void {
    this.assetsLoading = true;
    this.http.get<any[]>('/api/v1/finance/fixed-assets', { params: this.params() }).subscribe({
      next: (r) => { this.assets = r || []; this.assetsLoading = false; },
      error: (e) => { this.handleError(e); this.assetsLoading = false; }
    });
  }

  loadProjectsAndCostCenters(): void {
    this.pcLoading = true;
    this.http.get<any[]>('/api/v1/finance/projects', { params: this.params() }).subscribe({
      next: (r) => (this.projects = r || []),
      error: (e) => this.handleError(e)
    });
    this.http.get<any[]>('/api/v1/finance/cost-centers', { params: this.params() }).subscribe({
      next: (r) => { this.costCenters = r || []; this.pcLoading = false; },
      error: (e) => { this.handleError(e); this.pcLoading = false; }
    });
  }

  loadReceivablesAging(): void {
    this.arLoading = true;
    const p = { ...this.params(), as_of: this.agingAsOf };
    this.http.get<any>('/api/v1/finance/reports/receivables-aging', { params: p }).subscribe({
      next: (r) => { this.receivablesAging = r; this.arLoading = false; },
      error: (e) => { this.handleError(e); this.arLoading = false; }
    });
    // also load docs
    this.docsLoading = true;
    this.http.get<any>('/api/v1/finance/documents', { params: { ...this.params(), document_type: 'sales_invoice' } }).subscribe({
      next: (r) => { this.receivableDocs = Array.isArray(r) ? r.slice(0, 30) : (r.items || []).slice(0, 30); this.docsLoading = false; },
      error: () => { this.docsLoading = false; }
    });
  }

  loadPayablesAging(): void {
    this.apLoading = true;
    const p = { ...this.params(), as_of: this.agingAsOf };
    this.http.get<any>('/api/v1/finance/reports/payables-aging', { params: p }).subscribe({
      next: (r) => { this.payablesAging = r; this.apLoading = false; },
      error: (e) => { this.handleError(e); this.apLoading = false; }
    });
    this.docsLoading = true;
    this.http.get<any>('/api/v1/finance/documents', { params: { ...this.params(), document_type: 'purchase_bill' } }).subscribe({
      next: (r) => { this.payableDocs = Array.isArray(r) ? r.slice(0, 30) : (r.items || []).slice(0, 30); this.docsLoading = false; },
      error: () => { this.docsLoading = false; }
    });
  }

  loadBanks(): void {
    this.http.get<any[]>('/api/v1/finance/banks', { params: this.params() }).subscribe({
      next: (r) => { this.banks = r || []; },
      error: () => {}
    });
  }
  loadBankAccounts(): void {
    this.bankLoading = true;
    this.selectedBankAccountId = '';
    this.bankStatementLines = [];
    this.loadBanks();
    this.http.get<any[]>('/api/v1/finance/bank-accounts', { params: this.params() }).subscribe({
      next: (r) => { this.bankAccounts = r || []; this.bankLoading = false; },
      error: (e) => { this.handleError(e); this.bankLoading = false; }
    });
  }
  openBankEntityForm(b?: any): void {
    this.showBankEntityForm = true; this.error = '';
    if (b) { this.editingBankEntityId = b.id; this.bankEntityForm = { code: b.code||'', name: b.name||'', is_active: b.is_active!==false }; }
    else { this.editingBankEntityId = null; this.bankEntityForm = { code: '', name: '', is_active: true }; }
  }
  closeBankEntityForm(): void { this.showBankEntityForm = false; this.editingBankEntityId = null; }
  saveBankEntity(): void {
    if (!this.bankEntityForm.name) { this.error = this.t('Nombre del banco requerido.','Bank name required.'); return; }
    this.bankEntitySaving = true;
    const payload: any = { ...this.bankEntityForm, company_id: this.companyId };
    if (this.editingBankEntityId) {
      this.http.patch(`/api/v1/finance/banks/${this.editingBankEntityId}`, payload).subscribe({
        next: () => { this.bankEntitySaving = false; this.closeBankEntityForm(); this.loadBanks(); },
        error: (e) => { this.handleError(e); this.bankEntitySaving = false; }
      });
    } else {
      this.http.post('/api/v1/finance/banks', payload).subscribe({
        next: () => { this.bankEntitySaving = false; this.closeBankEntityForm(); this.loadBanks(); },
        error: (e) => { this.handleError(e); this.bankEntitySaving = false; }
      });
    }
  }
  deleteBankEntity(id: string): void {
    if (!confirm(this.t('¿Eliminar este banco del catálogo?','Delete this bank from catalog?'))) return;
    this.http.delete(`/api/v1/finance/banks/${id}`).subscribe({
      next: () => this.loadBanks(),
      error: (e) => this.handleError(e)
    });
  }
  openBankForm(b?: any): void {
    this.showBankForm = true;
    this.error = '';
    if (this.accounts.length === 0) this.loadAccounts(true);
    this.loadBanks();
    if (b) {
      this.editingBankId = b.id;
      this.bankForm = { account_id: b.account_id, bank_id: b.bank_id || '', bank_name: b.bank_name || '', account_name: b.account_name || '', account_number_masked: b.account_number_masked || '', currency: b.currency || 'PEN', is_active: b.is_active !== false };
    } else {
      this.editingBankId = null;
      this.bankForm = { account_id: '', bank_id: '', bank_name: '', account_name: '', account_number_masked: '', currency: 'PEN', is_active: true };
    }
  }
  closeBankForm(): void { this.showBankForm = false; this.editingBankId = null; }
  saveBankAccount(): void {
    if (!this.bankForm.account_id || !this.bankForm.account_name) { this.error = this.t('Cuenta contable y nombre son obligatorios.', 'GL account and name are required.'); return; }
    this.bankFormSaving = true;
    const payload: any = { ...this.bankForm };
    if (payload.bank_id) {
      const b = this.banks.find((x: any) => x.id === payload.bank_id);
      if (b) payload.bank_name = b.name;
    }
    if (!payload.bank_name) payload.bank_name = '';
    if (this.editingBankId) {
      this.http.patch(`/api/v1/finance/bank-accounts/${this.editingBankId}`, payload).subscribe({
        next: () => { this.bankFormSaving = false; this.closeBankForm(); this.loadBankAccounts(); },
        error: (e) => { this.handleError(e); this.bankFormSaving = false; }
      });
    } else {
      this.http.post('/api/v1/finance/bank-accounts', payload, { params: this.params() }).subscribe({
        next: () => { this.bankFormSaving = false; this.closeBankForm(); this.loadBankAccounts(); },
        error: (e) => { this.handleError(e); this.bankFormSaving = false; }
      });
    }
  }
  deleteBankAccount(id: string): void {
    if (!confirm(this.t('¿Eliminar esta cuenta bancaria?', 'Delete this bank account?'))) return;
    this.http.delete(`/api/v1/finance/bank-accounts/${id}`).subscribe({
      next: () => this.loadBankAccounts(),
      error: (e) => this.handleError(e)
    });
  }

  loadDocuments(): void {
    this.docsLoading = true;
    this.http.get<any>('/api/v1/finance/documents', { params: this.params() }).subscribe({
      next: (r) => { this.documents = Array.isArray(r) ? r : (r.items || []); this.docsLoading = false; },
      error: (e) => { this.handleError(e); this.docsLoading = false; }
    });
  }

  loadStatementLines(): void {
    if (!this.selectedBankAccountId) { this.bankStatementLines = []; return; }
    this.statementLoading = true;
    this.http.get<any[]>(`/api/v1/finance/bank-accounts/${this.selectedBankAccountId}/statement-lines`, { params: this.params() }).subscribe({
      next: (r) => { this.bankStatementLines = r || []; this.statementLoading = false; },
      error: (e) => { this.handleError(e); this.statementLoading = false; }
    });
  }

  private handleError(e: any): void {
    const msg = e?.error?.detail || e?.message || this.t('Ocurrió un error al cargar datos.', 'An error occurred while loading data.');
    this.error = msg;
  }
}
