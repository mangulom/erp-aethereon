import re
from pathlib import Path

p = Path(r"D:\WorkSpace\ERPAethereon\frontend\src\app\pages\finance\finance.component.ts")
s = p.read_text(encoding="utf-8", errors="replace")
orig = s

# Insert panels before config
if "@if (tab === 'accounts')" in s:
    print("PANELS ALREADY THERE")
else:
    # Find config block start
    cfg = "        @if (tab === 'config') {"
    if cfg not in s:
        print("CONFIG NOT FOUND")
    else:
        panels = """        @if (tab === 'accounts') {
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
"""
        s = s.replace(cfg, panels + cfg, 1)
        print("PANELS INSERTED")
        p.write_text(s, encoding="utf-8")
        print("WROTE")
