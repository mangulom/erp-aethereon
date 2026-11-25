from pathlib import Path

p = Path(r"D:\WorkSpace\ERPAethereon\frontend\src\app\pages\finance\finance.component.ts")
s = p.read_text(encoding="utf-8", errors="replace")

old = """        @if (tab === 'treasury') {
          <div class="fin-panel">
            <div class="fin-panel-title"><div><span class="panel-kicker">{{ t('TESORERÍA', 'TREASURY') }}</span><h3>{{ t('Cuentas bancarias', 'Bank accounts') }}</h3></div><button class="fin-primary" type="button" (click)="loadBankAccounts()" [disabled]="bankLoading">{{ bankLoading ? t('Cargando…', 'Loading…') : t('Actualizar', 'Refresh') }}</button></div>
            @if (bankAccounts.length === 0 && !bankLoading) { <div class="fin-empty">{{ t('No hay cuentas bancarias configuradas.', 'No bank accounts configured.') }}</div> }
            @else {
              <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Banco', 'Bank') }}</th><th>{{ t('Número', 'Number') }}</th><th>{{ t('Moneda', 'Currency') }}</th><th>{{ t('Cuenta contable', 'GL account') }}</th></tr></thead><tbody>@for (b of bankAccounts; track b.id) { <tr><td><b>{{ b.bank_name || '—' }}</b></td><td>{{ b.account_number || '—' }}</td><td>{{ b.currency || 'PEN' }}</td><td>{{ b.account_id || '—' }}</td></tr> }</tbody></table></div>
              <div class="fin-form-grid fin-books-filters" style="margin-top:12px;">
                <label>{{ t('Ver movimientos de', 'View movements for') }}
                  <select [(ngModel)]="selectedBankAccountId" (ngModelChange)="loadStatementLines()">
                    <option value="">{{ t('Seleccione cuenta', 'Select account') }}</option>
                    @for (b of bankAccounts; track b.id) { <option [value]="b.id">{{ b.bank_name }} - {{ b.account_number }}</option> }
                  </select>
                </label>
              </div>
              @if (statementLoading) { <div class="fin-notice">{{ t('Cargando movimientos…', 'Loading movements…') }}</div> }
              @else if (selectedBankAccountId && bankStatementLines.length === 0) { <div class="fin-empty">{{ t('Sin movimientos registrados.', 'No statement lines.') }}</div> }
              @else if (bankStatementLines.length > 0) { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Fecha', 'Date') }}</th><th>{{ t('Descripción', 'Description') }}</th><th>{{ t('Monto', 'Amount') }}</th><th>{{ t('Referencia', 'Reference') }}</th></tr></thead><tbody>@for (s of bankStatementLines; track s.id) { <tr><td>{{ s.transaction_date || s.date || '—' }}</td><td>{{ s.description || '—' }}</td><td>{{ s.amount || '—' }}</td><td>{{ s.reference || '—' }}</td></tr> }</tbody></table></div> }
            }
          </div>
        }"""

# Try to match with the actual (possibly mangled) text in file? Probably easier to reconstruct by finding the start and end
# But since we have the file, let's do a targeted replacement by locating the block
start = s.find("@if (tab === 'treasury') {")
if start < 0:
    print("NO TREASURY")
else:
    # find the matching closing of this block before "@if (tab === 'accounts')"
    accounts_start = s.find("@if (tab === 'accounts')", start)
    if accounts_start < 0:
        print("NO ACCOUNTS AFTER")
    else:
        # the treasury block ends just before accounts_start (with some whitespace)
        end = accounts_start
        # trim trailing whitespace/newlines
        block = s[start:end]
        print("FOUND len=", len(block))
        # write for inspection
        Path(r"D:\WorkSpace\ERPAethereon\_treasury_block.txt").write_text(block, encoding="utf-8")
        print("WROTE BLOCK")
