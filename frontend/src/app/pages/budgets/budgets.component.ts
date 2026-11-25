import { CommonModule } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { CompanyService } from '../../core/company.service';
import { LanguageService } from '../../core/language.service';

type BudgetTab = 'list' | 'pia' | 'execution' | 'cdp' | 'commitment' | 'payments';

@Component({
  selector: 'app-budgets',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="fin-workspace finance-advanced">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">{{ t('MÓDULO', 'MODULE') }}</span>
          <h1 class="fin-title-main">{{ t('Presupuestos', 'Budgets') }}</h1>
          <p class="fin-subtitle-desc">{{ t('Ciclo presupuestal: apropiación, CDP, compromiso, devengo y pago.', 'Budget cycle: appropriation, CDP, commitment, accrual and payment.') }}</p>
        </div>
      </header>
      @if (!hasCompany) { <div class="fin-alert" role="alert">{{ t('Selecciona una empresa activa.', 'Select an active company.') }}</div> }
      @if (error) { <div class="fin-alert fin-alert-error" role="alert">{{ error }}</div> }
      @if (hasCompany) {
        <nav class="fin-tabs" aria-label="Presupuestos">
          <button type="button" [class.active]="tab==='list'" (click)="tab='list'">{{ t('Presupuestos', 'Budgets') }}</button>
          <button type="button" [class.active]="tab==='pia'" (click)="tab='pia'">{{ t('Apropiación inicial', 'PIA') }}</button>
          <button type="button" [class.active]="tab==='execution'" (click)="tab='execution'">{{ t('Ejecución', 'Execution') }}</button>
          <button type="button" [class.active]="tab==='cdp'" (click)="tab='cdp'">{{ t('CDP', 'CDP') }}</button>
          <button type="button" [class.active]="tab==='commitment'" (click)="tab='commitment'">{{ t('Compromisos', 'Commitments') }}</button>
          <button type="button" [class.active]="tab==='payments'" (click)="tab='payments'">{{ t('Órdenes de pago', 'Payment Orders') }}</button>
        </nav>

        @if (tab==='list') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('PRESUPUESTOS', 'BUDGETS') }}</span><h3>{{ t('Listado', 'List') }}</h3></div><button class="fin-primary" type="button" (click)="loadBudgets()" [disabled]="loading">{{ loading?t('...','...'):t('Actualizar','Refresh') }}</button></div>
            @if (budgets.length===0 && !loading) { <div class="fin-empty">{{ t('No hay presupuestos.', 'No budgets.') }}</div> }
            @else { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Nombre','Name') }}</th><th>{{ t('Estado','Status') }}</th><th>{{ t('Moneda','Currency') }}</th></tr></thead><tbody>@for (b of budgets; track b.id) { <tr><td><b>{{ b.name }}</b></td><td>{{ b.status }}</td><td>{{ b.currency }}</td></tr> }</tbody></table></div> }
          </div>
        }

        @if (tab==='cdp') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">CDP</span><h3>{{ t('Certificados de Disponibilidad Presupuestal', 'Budget Availability Certificates') }}</h3></div><button class="fin-primary" type="button" (click)="showCdpForm = !showCdpForm">{{ showCdpForm ? t('Cancelar','Cancel') : t('Nuevo CDP','New CDP') }}</button></div>
            <p class="fin-hint">{{ t('Efecto contable: usualmente es control presupuestal (no asiento obligatorio); reserva saldo. Al comprometer se usa el CDP; al devengar se registra la obligación/gasto según política.', 'Accounting effect: typically budgetary control (no mandatory journal in all systems); reserves balance. Used when committing; accrual recognized per policy.') }}</p>
            @if (showCdpForm) {
              <div class="fin-form-grid" style="margin:12px 0;">
                <label>{{ t('Número','Number') }}<input [(ngModel)]="cdpForm.number" placeholder="CDP-2026-001"></label>
                <label>{{ t('Fecha','Date') }}<input type="date" [(ngModel)]="cdpForm.date"></label>
                <label>{{ t('Área solicitante','Requester area') }}<select [(ngModel)]="cdpForm.requester_area"><option value="Logística">Logística (Compras/Servicios)</option><option value="Recursos Humanos">Recursos Humanos (Planillas/Nómina y otros)</option><option value="Otro">{{ t('Otro','Other') }}</option></select></label>
                <label>{{ t('Partida','Line') }}<input [(ngModel)]="cdpForm.line" placeholder="2.3.1.01"></label>
                <label>{{ t('Monto','Amount') }}<input type="number" [(ngModel)]="cdpForm.amount"></label>
                <label>{{ t('Estado','Status') }}<select [(ngModel)]="cdpForm.status"><option value="vigente">{{ t('Vigente','Active') }}</option><option value="utilizado">{{ t('Utilizado','Used') }}</option><option value="anulado">{{ t('Anulado','Cancelled') }}</option></select></label>
              </div>
              <button class="fin-primary" type="button" (click)="addCdp()">{{ t('Guardar CDP', 'Save CDP') }}</button>
            }
            <div class="fin-table-wrap" style="margin-top:12px;"><table class="fin-table"><thead><tr><th>N°</th><th>{{ t('Fecha','Date') }}</th><th>{{ t('Área','Area') }}</th><th>{{ t('Partida','Line') }}</th><th>{{ t('Monto','Amount') }}</th><th>{{ t('Estado','Status') }}</th><th></th></tr></thead><tbody>
              @for (c of cdps; track c.id) { <tr><td>{{ c.number }}</td><td>{{ c.date }}</td><td>{{ c.requester_area || '—' }}</td><td>{{ c.line }}</td><td>{{ c.amount }}</td><td>{{ c.status }}</td><td><button class="fin-secondary" type="button" (click)="removeCdp(c.id)">{{ t('Eliminar','Delete') }}</button></td></tr> }
              @if (cdps.length===0) { <tr><td colspan="8" class="fin-empty">{{ t('Sin registros.','No records.') }}</td></tr> }
            </tbody></table></div>
          </div>
        }

        @if (tab==='commitment') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('COMPROMISOS','COMMITMENTS') }}</span><h3>{{ t('Compromisos presupuestales', 'Budget commitments') }}</h3></div><button class="fin-primary" type="button" (click)="showCommitForm = !showCommitForm">{{ showCommitForm ? t('Cancelar','Cancel') : t('Nuevo compromiso','New commitment') }}</button></div>
            <p class="fin-hint">{{ t('Efecto contable: al comprometer se reserva presupuesto (control). Al devengar (recibir bien/servicio o factura) se reconoce gasto/obligación: Dr. Gasto/Activo, Cr. Cuentas por pagar (según caso), y se reduce compromiso.', 'Accounting effect: commitment reserves budget. On accrual (goods/service received/invoice) recognize expense/liability: Dr Expense/Asset, Cr Accounts Payable, reducing commitment.') }}</p>
            @if (showCommitForm) {
              <div class="fin-form-grid" style="margin:12px 0;">
                <label>{{ t('Número','Number') }}<input [(ngModel)]="commitForm.number" placeholder="COMP-001"></label>
                <label>{{ t('Fecha','Date') }}<input type="date" [(ngModel)]="commitForm.date"></label>
                <label>{{ t('CDP (opcional)','CDP (optional)') }}<select [(ngModel)]="commitForm.cdp_id"><option value="">{{ t('Sin CDP','No CDP') }}</option>@for(cd of cdps; track cd.id){<option [value]="cd.id">{{ cd.number }} - {{ cd.requester_area||'' }}</option>}</select></label>
                <label>{{ t('Proveedor','Supplier') }}<select [(ngModel)]="commitForm.supplier_id"><option value="">{{ t('Sin proveedor','No supplier') }}</option>@for(sp of suppliers; track sp.id){<option [value]="sp.id">{{ sp.code }} - {{ sp.name }}</option>}</select></label>
                <label>{{ t('Referencia','Reference') }}<input [(ngModel)]="commitForm.reference" placeholder="OC-001"></label>
                <label>{{ t('Monto','Amount') }}<input type="number" [(ngModel)]="commitForm.amount"></label>
                <label>{{ t('Estado','Status') }}<select [(ngModel)]="commitForm.status"><option value="comprometido">{{ t('Comprometido','Committed') }}</option><option value="devengado">{{ t('Devengado','Accrued') }}</option><option value="anulado">{{ t('Anulado','Cancelled') }}</option></select></label>
              </div>
              <button class="fin-primary" type="button" (click)="addCommit()">{{ t('Guardar compromiso', 'Save commitment') }}</button>
            }
            <div class="fin-table-wrap" style="margin-top:12px;"><table class="fin-table"><thead><tr><th>N°</th><th>{{ t('Fecha','Date') }}</th><th>CDP</th><th>{{ t('Proveedor','Supplier') }}</th><th>{{ t('Referencia','Reference') }}</th><th>{{ t('Monto','Amount') }}</th><th>{{ t('Estado','Status') }}</th><th></th></tr></thead><tbody>
              @for (c of commitments; track c.id) { <tr><td>{{ c.number }}</td><td>{{ c.date }}</td><td>{{ c.cdp_id ? (cdpNumber(c.cdp_id) || c.cdp_id) : '—' }}</td><td>{{ c.supplier_id ? supplierName(c.supplier_id) : '—' }}</td><td>{{ c.reference }}</td><td>{{ c.amount }}</td><td>{{ c.status }}</td><td><button class="fin-secondary" type="button" (click)="removeCommit(c.id)">{{ t('Eliminar','Delete') }}</button></td></tr> }
              @if (commitments.length===0) { <tr><td colspan="7" class="fin-empty">{{ t('Sin registros.','No records.') }}</td></tr> }
            </tbody></table></div>
          </div>
        }

        @if (tab==='payments') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('ÓRDENES DE PAGO','PAYMENT ORDERS') }}</span><h3>{{ t('Órdenes de pago', 'Payment orders') }}</h3></div><button class="fin-primary" type="button" (click)="showPayForm = !showPayForm">{{ showPayForm ? t('Cancelar','Cancel') : t('Nueva orden','New order') }}</button></div>
            <p class="fin-hint">{{ t('Efecto contable: al pagar se registra Dr. Cuentas por pagar (o Compromiso/Devengado) y Cr. Caja/Bancos en Tesorería/Contabilidad, reduciendo la obligación.', 'Accounting effect: on payment Dr Accounts Payable (or commitment/accrual) and Cr Cash/Bank in Treasury/Accounting, reducing the liability.') }}</p>
            @if (showPayForm) {
              <div class="fin-form-grid" style="margin:12px 0;">
                <label>{{ t('Número','Number') }}<input [(ngModel)]="payForm.number" placeholder="OP-2026-001"></label>
                <label>{{ t('Fecha','Date') }}<input type="date" [(ngModel)]="payForm.date"></label>
                <label>{{ t('Beneficiario','Payee') }}<input [(ngModel)]="payForm.payee"></label>
                <label>{{ t('Proveedor','Supplier') }}<select [(ngModel)]="payForm.supplier_id"><option value="">{{ t('Sin proveedor','No supplier') }}</option>@for(sp of suppliers; track sp.id){<option [value]="sp.id">{{ sp.code }} - {{ sp.name }}</option>}</select></label>
                <label>{{ t('Cuenta bancaria','Bank account') }}<select [(ngModel)]="payForm.bank_account_id"><option value="">{{ t('Seleccionar...','Select...') }}</option>@for(ba of bankAccounts; track ba.id){<option [value]="ba.id">{{ ba.bank_name || ba.account_name }} ({{ ba.currency }})</option>}</select></label>
                <label>{{ t('Monto','Amount') }}<input type="number" [(ngModel)]="payForm.amount"></label>
                <label>{{ t('Estado','Status') }}<select [(ngModel)]="payForm.status"><option value="emitida">{{ t('Emitida','Issued') }}</option><option value="pagada">{{ t('Pagada','Paid') }}</option><option value="anulada">{{ t('Anulada','Cancelled') }}</option></select></label>
              </div>
              <button class="fin-primary" type="button" (click)="addPay()">{{ t('Guardar orden', 'Save order') }}</button>
            }
            <div class="fin-table-wrap" style="margin-top:12px;"><table class="fin-table"><thead><tr><th>N°</th><th>{{ t('Fecha','Date') }}</th><th>{{ t('Beneficiario','Payee') }}</th><th>{{ t('Proveedor','Supplier') }}</th><th>{{ t('Monto','Amount') }}</th><th>{{ t('Estado','Status') }}</th><th></th></tr></thead><tbody>
              @for (p of payments; track p.id) { <tr><td>{{ p.number }}</td><td>{{ p.date }}</td><td>{{ p.payee }}</td><td>{{ p.supplier_id ? supplierName(p.supplier_id) : '—' }}</td><td>{{ p.amount }}</td><td>{{ p.status }}</td><td>
                @if (p.status !== 'pagado' && p.status !== 'pagada') { <button class="fin-secondary" type="button" (click)="markPaid(p)">{{ t('Pagar','Pay') }}</button> }
                <button class="fin-secondary" type="button" (click)="removePay(p.id)">{{ t('Eliminar','Delete') }}</button>
              </td></tr> }
              @if (payments.length===0) { <tr><td colspan="7" class="fin-empty">{{ t('Sin registros.','No records.') }}</td></tr> }
            </tbody></table></div>
          </div>
        }

        @if (tab==='pia') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('APROPIACIÓN INICIAL','PIA') }}</span><h3>{{ t('Presupuestos / Apropiación inicial', 'Budgets / Initial appropriation') }}</h3></div><button class="fin-primary" type="button" (click)="showBudgetForm = !showBudgetForm">{{ showBudgetForm ? t('Cancelar','Cancel') : t('Nueva apropiación','New appropriation') }}</button></div>
            <p class="fin-hint">{{ t('Registra la apropiación inicial por área (Finanzas, Contabilidad, Logística, RR.HH.). Define montos en “Líneas”. Requerido antes de crear CDP.', 'Register initial appropriation by area. Set amounts in “Lines”. Required before creating CDP.') }}</p>
            @if (showBudgetForm) {
              <div class="fin-form-grid" style="margin:12px 0;">
                <label>{{ t('Nombre','Name') }}<input [(ngModel)]="budgetForm.name" placeholder="Apropiación 2026"></label>
                <label>{{ t('Ejercicio fiscal','Fiscal year') }}<select [(ngModel)]="budgetForm.fiscal_year_id"><option value="">{{ t('Seleccionar...','Select...') }}</option>@for(fy of fiscalYears; track fy.id){<option [value]="fy.id">{{ fy.name || fy.year || fy.id }}</option>}</select></label>
                <label>{{ t('Área origen','Origin area') }}<select [(ngModel)]="budgetForm.origin_area"><option value="general">{{ t('General','General') }}</option><option value="finanzas">{{ t('Finanzas','Finance') }}</option><option value="contabilidad">{{ t('Contabilidad','Accounting') }}</option><option value="logistica">{{ t('Logística','Logistics') }}</option><option value="rrhh">{{ t('RR.HH.','HR') }}</option></select></label>
                <label>{{ t('Moneda','Currency') }}<input [(ngModel)]="budgetForm.currency" maxlength="3"></label>
                <label style="grid-column:1/-1;">{{ t('Descripción','Description') }}<input [(ngModel)]="budgetForm.description"></label>
              </div>
              <button class="fin-primary" type="button" (click)="addBudget()">{{ t('Guardar', 'Save') }}</button>
            }
            <div class="fin-table-wrap" style="margin-top:12px;"><table class="fin-table"><thead><tr><th>{{ t('Nombre','Name') }}</th><th>{{ t('Área','Area') }}</th><th>{{ t('Moneda','Currency') }}</th><th>{{ t('Estado','Status') }}</th><th></th></tr></thead><tbody>
              @for (b of budgets; track b.id) {
                <tr>
                  <td><b>{{ b.name }}</b></td><td>{{ b.origin_area || 'general' }}</td><td>{{ b.currency }}</td><td>{{ b.status }}</td>
                  <td><button class="fin-secondary" type="button" (click)="selectBudgetForLines(b)">{{ selectedBudgetId === b.id ? t('Cerrar líneas','Close lines') : t('Líneas / Montos','Lines / Amounts') }}</button></td>
                </tr>
                @if (selectedBudgetId === b.id) {
                  <tr><td colspan="5">
                    <div style="padding:8px 0;">
                      <strong>{{ t('Líneas (montos por cuenta)','Lines (amounts by account)') }}</strong>
                      <div class="fin-form-grid" style="margin:8px 0;">
                        <label>{{ t('Cuenta','Account') }}<select [(ngModel)]="lineForm.account_id"><option value="">{{ t('Seleccionar...','Select...') }}</option>@for(a of accounts; track a.id){<option [value]="a.id">{{ a.code }} - {{ a.name }}</option>}</select></label>
                        <label>{{ t('Monto','Amount') }}<input type="number" [(ngModel)]="lineForm.planned_amount"></label>
                      </div>
                      <button class="fin-primary" type="button" (click)="addBudgetLine()">{{ t('Agregar línea','Add line') }}</button>
                      @if (budgetLinesLoading) { <p>{{ t('Cargando...','Loading...') }}</p> }
                      <table class="fin-table" style="margin-top:8px;"><thead><tr><th>{{ t('Cuenta','Account') }}</th><th>{{ t('Monto','Amount') }}</th><th></th></tr></thead><tbody>
                        @for (ln of budgetLines; track ln.id) { <tr><td>{{ ln.account_code }} - {{ ln.account_name }}</td><td>{{ ln.planned_amount }}</td><td><button class="fin-secondary" type="button" (click)="removeBudgetLine(ln.id)">{{ t('Eliminar','Delete') }}</button></td></tr> }
                        @if (budgetLines.length===0 && !budgetLinesLoading) { <tr><td colspan="3" class="fin-empty">{{ t('Sin líneas.','No lines.') }}</td></tr> }
                      </tbody></table>
                    </div>
                  </td></tr>
                }
              }
              @if (budgets.length===0) { <tr><td colspan="5" class="fin-empty">{{ t('Sin registros.','No records.') }}</td></tr> }
            </tbody></table></div>
          </div>
        }
        @if (tab==='execution') {
          <div class="fin-panel"><p class="fin-hint">{{ t('Sección en desarrollo con datos de ejemplo.', 'Section with sample data.') }}</p></div>
        }
      }
    </section>
  `,
})
export class BudgetsComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly companies = inject(CompanyService);
  private readonly language = inject(LanguageService);
  tab: BudgetTab = 'list';
  budgets: any[] = [];
  loading = false;
  error = '';
  fiscalYears: any[] = [];
  accounts: any[] = [];

  cdps: any[] = [];
  commitments: any[] = [];
  payments: any[] = [];
  suppliers: any[] = [];
  bankAccounts: any[] = [];
  selectedBudgetId: string | null = null;
  budgetLines: any[] = [];
  budgetLinesLoading = false;
  lineForm: any = { account_id: '', planned_amount: 0 };
  cdpLoading = false;
  commitLoading = false;
  payLoading = false;

  cdpForm: any = { number: '', date: '', line: '', amount: 0, status: 'vigente', requester_area: 'Logística' };
  commitForm: any = { number: '', date: '', reference: '', amount: 0, status: 'comprometido', cdp_id: '', supplier_id: '' };
  payForm: any = { number: '', date: '', payee: '', amount: 0, status: 'emitida', supplier_id: '', bank_account_id: '' };
  budgetForm: any = { name: '', fiscal_year_id: '', description: '', currency: 'PEN', origin_area: 'general' };
  showCdpForm = false;
  showCommitForm = false;
  showPayForm = false;
  showBudgetForm = false;
  showCdpModal = false;
  showCommitModal = false;
  showPayModal = false;
  editingCdpId: string | null = null;
  editingCommitId: string | null = null;
  editingPayId: string | null = null;

  get hasCompany() { return this.companies.hasActiveCompany; }
  get isSpanish() { return this.language.language() === 'es'; }
  t(es: string, en: string) { return this.isSpanish ? es : en; }
  private params() { return { company_id: this.companies.context.selectedCompanyId }; }
  ngOnInit(): void { if (this.hasCompany) { this.loadBudgets(); this.loadCdps(); this.loadCommitments(); this.loadPayments(); this.loadSuppliers(); this.loadBankAccounts(); this.loadFiscalYears(); this.loadAccounts(); } }
  loadSuppliers() { this.http.get<any[]>('/api/v1/finance/auxiliaries', { params: { ...this.params(), auxiliary_type: 'supplier' } }).subscribe({ next: r=>{this.suppliers=r||[];}, error: ()=>{} }); }
  loadBankAccounts() { this.http.get<any[]>('/api/v1/finance/bank-accounts', { params: this.params() }).subscribe({ next: r=>{this.bankAccounts=r||[];}, error: ()=>{} }); }
  loadAccounts() { this.http.get<any[]>('/api/v1/finance/accounts', { params: this.params() }).subscribe({ next: r=>{this.accounts=(r||[]).filter((a:any)=>a.allow_posting);}, error: ()=>{} }); }
  loadBudgets() { this.loading = true; this.http.get<any[]>('/api/v1/finance/budgets', { params: this.params() }).subscribe({ next: r=>{this.budgets=r||[];this.loading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.loading=false;} }); }
  loadFiscalYears() { this.http.get<any[]>('/api/v1/finance/fiscal-years', { params: this.params() }).subscribe({ next: r=>{this.fiscalYears=r||[];}, error: ()=>{} }); }
  addBudget() {
    if (!this.budgetForm.name || !this.budgetForm.fiscal_year_id) { this.error = this.t('Nombre y ejercicio fiscal son requeridos.','Name and fiscal year are required.'); return; }
    const payload: any = { company_id: this.companies.context.selectedCompanyId, name: this.budgetForm.name, fiscal_year_id: this.budgetForm.fiscal_year_id, description: this.budgetForm.description, currency: this.budgetForm.currency || 'PEN', origin_area: this.budgetForm.origin_area };
    this.http.post<any>('/api/v1/finance/budgets', payload).subscribe({ next: ()=>{ this.loadBudgets(); this.budgetForm = { name:'', fiscal_year_id:'', description:'', currency:'PEN', origin_area:'general' }; this.showBudgetForm=false; }, error: e=>{ this.error=e?.error?.detail||'Error'; } });
  }
  selectBudgetForLines(b: any) {
    this.selectedBudgetId = this.selectedBudgetId === b.id ? null : b.id;
    this.budgetLines = [];
    if (this.selectedBudgetId) this.loadBudgetLines();
  }
  loadBudgetLines() {
    if (!this.selectedBudgetId) return;
    this.budgetLinesLoading = true;
    this.http.get<any[]>(`/api/v1/finance/budgets/${this.selectedBudgetId}/lines`).subscribe({ next: r=>{this.budgetLines=r||[];this.budgetLinesLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.budgetLinesLoading=false;} });
  }
  addBudgetLine() {
    if (!this.selectedBudgetId || !this.lineForm.account_id) return;
    const payload: any = { account_id: this.lineForm.account_id, planned_amount: Number(this.lineForm.planned_amount)||0 };
    this.http.post<any>(`/api/v1/finance/budgets/${this.selectedBudgetId}/lines`, payload).subscribe({ next: ()=>{ this.loadBudgetLines(); this.lineForm = { account_id:'', planned_amount:0 }; }, error: e=>{ this.error=e?.error?.detail||'Error'; } });
  }
  removeBudgetLine(id: string) {
    if (!confirm(this.t('¿Eliminar esta línea?','Delete this line?'))) return;
    this.http.delete(`/api/v1/finance/budget-lines/${id}`).subscribe({ next: ()=>this.loadBudgetLines(), error: e=>{ this.error=e?.error?.detail||'Error'; } });
  }
  loadCdps() { this.cdpLoading = true; this.http.get<any[]>('/api/v1/finance/budget-cdp', { params: this.params() }).subscribe({ next: r=>{this.cdps=(r||[]).map((x:any)=>({...x, date: x.cdp_date, line: x.line_text, requester_area: x.requester_area})); this.cdpLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.cdpLoading=false;} }); }
  addCdp() {
    if (!this.cdpForm.number) return;
    const payload = { company_id: this.companies.context.selectedCompanyId, number: this.cdpForm.number, cdp_date: this.cdpForm.date, line_text: this.cdpForm.line, requester_area: this.cdpForm.requester_area, amount: Number(this.cdpForm.amount)||0, status: this.cdpForm.status };
    this.http.post<any>('/api/v1/finance/budget-cdp', payload).subscribe({ next: ()=>{ this.loadCdps(); this.cdpForm = { number:'', date:'', line:'', amount:0, status:'vigente', requester_area: 'Logística' }; this.showCdpForm=false; }, error: e=>{ this.error=e?.error?.detail||'Error'; } });
  }
  openCdpModal(item?: any) {
    this.showCdpModal = true; this.error = '';
    if (item) { this.editingCdpId = item.id; this.cdpForm = { number: item.number||'', date: item.date||'', line: item.line||'', amount: item.amount||0, status: item.status||'vigente', requester_area: item.requester_area||'Logística' }; }
    else { this.editingCdpId = null; this.cdpForm = { number:'', date:'', line:'', amount:0, status:'vigente', requester_area:'Logística' }; }
  }
  closeCdpModal() { this.showCdpModal = false; this.editingCdpId = null; }
  openCommitModal(item?: any) {
    this.showCommitModal = true; this.error = '';
    if (item) { this.editingCommitId = item.id; this.commitForm = { number: item.number||'', date: item.date||'', reference: item.reference||'', amount: item.amount||0, status: item.status||'comprometido', cdp_id: item.cdp_id||'', supplier_id: item.supplier_id||'' }; }
    else { this.editingCommitId = null; this.commitForm = { number:'', date:'', reference:'', amount:0, status:'comprometido', cdp_id:'', supplier_id:'' }; }
  }
  closeCommitModal() { this.showCommitModal = false; this.editingCommitId = null; }
  openPayModal(item?: any) {
    this.showPayModal = true; this.error = '';
    if (item) { this.editingPayId = item.id; this.payForm = { number: item.number||'', date: item.date||'', payee: item.payee||'', amount: item.amount||0, status: item.status||'emitida', supplier_id: item.supplier_id||'', bank_account_id: item.bank_account_id||'' }; }
    else { this.editingPayId = null; this.payForm = { number:'', date:'', payee:'', amount:0, status:'emitida', supplier_id:'', bank_account_id:'' }; }
  }
  closePayModal() { this.showPayModal = false; this.editingPayId = null; }
  removeCdp(id: string) {
    if (!confirm(this.t('¿Eliminar este CDP?','Delete this CDP?'))) return;
    this.http.delete(`/api/v1/finance/budget-cdp/${id}`).subscribe({
      next: () => this.loadCdps(),
      error: (e) => { this.error = e?.error?.detail || this.t('No se pudo eliminar.','Could not delete.'); }
    });
  }
  loadCommitments() { this.commitLoading = true; this.http.get<any[]>('/api/v1/finance/budget-commitments', { params: this.params() }).subscribe({ next: r=>{this.commitments=(r||[]).map((x:any)=>({...x, date: x.commitment_date})); this.commitLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.commitLoading=false;} }); }
  addCommit() {
    if (!this.commitForm.number) return;
    const payload: any = { company_id: this.companies.context.selectedCompanyId, number: this.commitForm.number, commitment_date: this.commitForm.date, reference: this.commitForm.reference, amount: Number(this.commitForm.amount)||0, status: this.commitForm.status };
    if (this.commitForm.cdp_id) payload.cdp_id = this.commitForm.cdp_id;
    if (this.commitForm.supplier_id) payload.supplier_id = this.commitForm.supplier_id;
    this.http.post<any>('/api/v1/finance/budget-commitments', payload).subscribe({ next: ()=>{ this.loadCommitments(); this.commitForm = { number:'', date:'', reference:'', amount:0, status:'comprometido', cdp_id: '', supplier_id: '' }; this.showCommitForm=false; }, error: e=>{ this.error=e?.error?.detail||'Error'; } });
  }
  removeCommit(id: string) {
    if (!confirm(this.t('¿Eliminar este compromiso?','Delete this commitment?'))) return;
    this.http.delete(`/api/v1/finance/budget-commitments/${id}`).subscribe({
      next: () => this.loadCommitments(),
      error: (e) => { this.error = e?.error?.detail || this.t('No se pudo eliminar.','Could not delete.'); }
    });
  }
  cdpNumber(id: string): string { const c = this.cdps.find(x => x.id === id); return c ? c.number : id; }
  supplierName(id: string): string { const s = this.suppliers.find(x => x.id === id); return s ? (s.name || s.code || id) : (id || '—'); }
  loadPayments() { this.payLoading = true; this.http.get<any[]>('/api/v1/finance/payment-orders', { params: this.params() }).subscribe({ next: r=>{this.payments=(r||[]).map((x:any)=>({...x, date: x.order_date})); this.payLoading=false;}, error: e=>{this.error=e?.error?.detail||'Error';this.payLoading=false;} }); }
  addPay() {
    if (!this.payForm.number) return;
    const payload: any = { company_id: this.companies.context.selectedCompanyId, number: this.payForm.number, order_date: this.payForm.date, payee: this.payForm.payee, amount: Number(this.payForm.amount)||0, status: this.payForm.status };
    if (this.payForm.supplier_id) payload.supplier_id = this.payForm.supplier_id;
    if (this.payForm.bank_account_id) payload.bank_account_id = this.payForm.bank_account_id;
    this.http.post<any>('/api/v1/finance/payment-orders', payload).subscribe({ next: ()=>{ this.loadPayments(); this.payForm = { number:'', date:'', payee:'', amount:0, status:'emitida', supplier_id: '', bank_account_id: '' }; this.showPayForm=false; }, error: e=>{ this.error=e?.error?.detail||'Error'; } });
  }
  markPaid(p: any) {
    if (!p.commitment_id) { this.error = this.t('La orden debe estar vinculada a un compromiso para generar el asiento.', 'Order must be linked to a commitment to generate journal entry.'); return; }
    if (!p.bank_account_id) { this.error = this.t('Seleccione una cuenta bancaria en la orden antes de pagar (editar).', 'Select a bank account on the order before paying (edit).'); return; }
    this.http.patch(`/api/v1/finance/payment-orders/${p.id}`, { status: 'pagado', bank_account_id: p.bank_account_id }).subscribe({
      next: () => this.loadPayments(),
      error: (e) => { this.error = e?.error?.detail || this.t('No se pudo marcar como pagado.','Could not mark as paid.'); }
    });
  }
  removePay(id: string) {
    if (!confirm(this.t('¿Eliminar esta orden de pago?','Delete this payment order?'))) return;
    this.http.delete(`/api/v1/finance/payment-orders/${id}`).subscribe({
      next: () => this.loadPayments(),
      error: (e) => { this.error = e?.error?.detail || this.t('No se pudo eliminar.','Could not delete.'); }
    });
  }
}
