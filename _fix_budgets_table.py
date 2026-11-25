from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\budgets\budgets.component.ts')
s = p.read_text(encoding='utf-8', errors='replace')

# header
oldh = "<thead><tr><th>N°</th><th>{{ t('Fecha','Date') }}</th><th>CDP</th><th>{{ t('Referencia','Reference') }}</th><th>{{ t('Monto','Amount') }}</th><th>{{ t('Estado','Status') }}</th><th></th></tr></thead>"
newh = "<thead><tr><th>N°</th><th>{{ t('Fecha','Date') }}</th><th>CDP</th><th>{{ t('Proveedor','Supplier') }}</th><th>{{ t('Referencia','Reference') }}</th><th>{{ t('Monto','Amount') }}</th><th>{{ t('Estado','Status') }}</th><th></th></tr></thead>"
if oldh not in s:
    print('NO HEADER')
else:
    s = s.replace(oldh, newh, 1)
    # body
    oldb = "<tr><td>{{ c.number }}</td><td>{{ c.date }}</td><td>{{ c.cdp_id ? (cdpNumber(c.cdp_id) || c.cdp_id) : '—' }}</td><td>{{ c.reference }}</td><td>{{ c.amount }}</td><td>{{ c.status }}</td><td><button class=\"fin-secondary\" type=\"button\" (click)=\"removeCommit(c.id)\">{{ t('Eliminar','Delete') }}</button></td></tr>"
    newb = "<tr><td>{{ c.number }}</td><td>{{ c.date }}</td><td>{{ c.cdp_id ? (cdpNumber(c.cdp_id) || c.cdp_id) : '—' }}</td><td>{{ c.supplier_id ? supplierName(c.supplier_id) : '—' }}</td><td>{{ c.reference }}</td><td>{{ c.amount }}</td><td>{{ c.status }}</td><td><button class=\"fin-secondary\" type=\"button\" (click)=\"removeCommit(c.id)\">{{ t('Eliminar','Delete') }}</button></td></tr>"
    if oldb not in s:
        print('NO BODY')
    else:
        s = s.replace(oldb, newb, 1)
        # colspan
        s = s.replace("<tr><td colspan=\"7\" class=\"fin-empty\">", "<tr><td colspan=\"8\" class=\"fin-empty\">", 1)
        p.write_text(s, encoding='utf-8')
        print('OK')
