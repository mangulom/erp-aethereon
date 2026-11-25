from pathlib import Path

p = Path(r"D:\WorkSpace\ERPAethereon\frontend\src\app\pages\finance\finance.component.ts")
s = p.read_text(encoding="utf-8", errors="replace")

start = s.find("@if (tab === 'treasury') {")
accounts_start = s.find("@if (tab === 'accounts')", start)
if start < 0 or accounts_start < 0:
    print("NOT FOUND")
else:
    new_block = """        @if (tab === 'treasury') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('TESORERÍA', 'TREASURY') }}</span><h3>{{ t('Cuentas bancarias', 'Bank accounts') }}</h3></div><div style="display:flex;gap:8px;"><button class="fin-secondary" type="button" (click)="loadBankAccounts()" [disabled]="bankLoading">{{ bankLoading ? t('Cargando…', 'Loading…') : t('Actualizar', 'Refresh') }}</button><button class="fin-primary" type="button" (click)="openBankForm()">{{ t('Nueva cuenta bancaria', 'New bank account') }}</button></div></div>
            @if (showBankForm) {
              <div class="fin-form-grid" style="margin:12px 0;">
                <label>{{ t('Cuenta contable (caja/banco)', 'GL account (cash/bank)') }}<select [(ngModel)]="bankForm.account_id"><option value="">{{ t('Seleccione', 'Select') }}</option>@for (a of accounts; track a.id) { @if (a.account_subtype==='cash' || a.account_subtype==='bank' || a.account_type==='asset') { <option [value]="a.id">{{ a.code }} - {{ a.name }}</option> } }</select></label>
                <label>{{ t('Banco', 'Bank') }}<input [(ngModel)]="bankForm.bank_name"></label>
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
"""
    s2 = s[:start] + new_block + s[accounts_start:]
    p.write_text(s2, encoding="utf-8")
    print("REPLACED")
