from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\finance\finance.component.ts')
lines = p.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)

# Replace lines 233-251 (0-based 232-250) with new config block
# 233 is index 232 in 0-based if counting from 1? Let us check: line 233 is the 233rd line (1-based) => index 232
new_block = """        @if (tab === 'config') {
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
            @if (banks.length > 0) { <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>{{ t('Código','Code') }}</th><th>{{ t('Nombre','Name') }}</th><th>{{ t('Activo','Active') }}</th><th>{{ t('Acciones','Actions') }}</th></tr></thead><tbody>@for (bk of banks; track bk.id) { <tr><td>{{ bk.code || '—' }}</td><td>{{ bk.name }}</td><td>{{ bk.is_active ? t('Sí','Yes') : t('No','No') }}</td><td><button class="fin-secondary" type="button" (click)="openBankEntityForm(bk)">{{ t('Editar','Edit') }}</button> <button class="fin-secondary" type="button" (click)="deleteBankEntity(bk.id)">{{ t('Eliminar','Delete') }}</button></td></tr> }}</tbody></table></div> }
          </div>
        }
"""
# Replace lines 232-251 (0-based: line 233 is index 232, line 251 is index 250) - so from index 232 to 251 inclusive? Let us count
# Line 233 is index 232, line 251 is index 250 (0-based). So slice [232:251+1] = [232:252] gives lines 233-252
result = lines[:232] + [new_block] + lines[252:]
p.write_text(''.join(result), encoding='utf-8')
print('done')
