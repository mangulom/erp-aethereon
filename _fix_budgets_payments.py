from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\budgets\budgets.component.ts')
s = p.read_text(encoding='utf-8', errors='replace')

# form
oldf = """                <label>{{ t('Beneficiario','Payee') }}<input [(ngModel)]="payForm.payee"></label>
                <label>{{ t('Monto','Amount') }}<input type="number" [(ngModel)]="payForm.amount"></label>"""
newf = """                <label>{{ t('Beneficiario','Payee') }}<input [(ngModel)]="payForm.payee"></label>
                <label>{{ t('Proveedor','Supplier') }}<select [(ngModel)]="payForm.supplier_id"><option value="">{{ t('Sin proveedor','No supplier') }}</option>@for(sp of suppliers; track sp.id){<option [value]="sp.id">{{ sp.code }} - {{ sp.name }}</option>}</select></label>
                <label>{{ t('Monto','Amount') }}<input type="number" [(ngModel)]="payForm.amount"></label>"""
if oldf not in s:
    print('NO PAY FORM')
else:
    s = s.replace(oldf, newf, 1)
    # table header
    oldh = "<thead><tr><th>N°</th><th>{{ t('Fecha','Date') }}</th><th>{{ t('Beneficiario','Payee') }}</th><th>{{ t('Monto','Amount') }}</th><th>{{ t('Estado','Status') }}</th><th></th></tr></thead>"
    newh = "<thead><tr><th>N°</th><th>{{ t('Fecha','Date') }}</th><th>{{ t('Beneficiario','Payee') }}</th><th>{{ t('Proveedor','Supplier') }}</th><th>{{ t('Monto','Amount') }}</th><th>{{ t('Estado','Status') }}</th><th></th></tr></thead>"
    if oldh not in s:
        print('NO PAY HEADER')
    else:
        s = s.replace(oldh, newh, 1)
        # table body
        oldb = "<tr><td>{{ p.number }}</td><td>{{ p.date }}</td><td>{{ p.payee }}</td><td>{{ p.amount }}</td><td>{{ p.status }}</td><td><button class=\"fin-secondary\" type=\"button\" (click)=\"removePay(p.id)\">{{ t('Eliminar','Delete') }}</button></td></tr>"
        newb = "<tr><td>{{ p.number }}</td><td>{{ p.date }}</td><td>{{ p.payee }}</td><td>{{ p.supplier_id ? supplierName(p.supplier_id) : '—' }}</td><td>{{ p.amount }}</td><td>{{ p.status }}</td><td><button class=\"fin-secondary\" type=\"button\" (click)=\"removePay(p.id)\">{{ t('Eliminar','Delete') }}</button></td></tr>"
        if oldb not in s:
            print('NO PAY BODY')
        else:
            s = s.replace(oldb, newb, 1)
            s = s.replace('<tr><td colspan="6" class="fin-empty">', '<tr><td colspan="7" class="fin-empty">', 1)
            p.write_text(s, encoding='utf-8')
            print('OK PAY')
