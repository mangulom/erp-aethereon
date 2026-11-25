from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\budgets\budgets.component.ts')
s = p.read_text(encoding='utf-8', errors='replace')

# Add supplier to commitment form: insert after CDP line
old = '''                <label>{{ t('CDP (opcional)','CDP (optional)') }}<select [(ngModel)]="commitForm.cdp_id"><option value="">{{ t('Sin CDP','No CDP') }}</option>@for(cd of cdps; track cd.id){<option [value]="cd.id">{{ cd.number }} - {{ cd.requester_area||'' }}</option>}</select></label>
                <label>{{ t('Referencia','Reference') }}<input [(ngModel)]="commitForm.reference" placeholder="OC-001"></label>'''
new = '''                <label>{{ t('CDP (opcional)','CDP (optional)') }}<select [(ngModel)]="commitForm.cdp_id"><option value="">{{ t('Sin CDP','No CDP') }}</option>@for(cd of cdps; track cd.id){<option [value]="cd.id">{{ cd.number }} - {{ cd.requester_area||'' }}</option>}</select></label>
                <label>{{ t('Proveedor','Supplier') }}<select [(ngModel)]="commitForm.supplier_id"><option value="">{{ t('Sin proveedor','No supplier') }}</option>@for(sp of suppliers; track sp.id){<option [value]="sp.id">{{ sp.code }} - {{ sp.name }}</option>}</select></label>
                <label>{{ t('Referencia','Reference') }}<input [(ngModel)]="commitForm.reference" placeholder="OC-001"></label>'''
if old not in s:
    print('NO COMMIT FORM')
else:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')
    print('OK COMMIT FORM')
