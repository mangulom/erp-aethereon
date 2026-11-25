from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\budgets\budgets.component.ts')
s = p.read_text(encoding='utf-8', errors='replace')
# Try to find with flexible matching
if 'Área solicitante' in s or 'rea solicitante' in s:
    # replace the line containing requester_area select
    lines = s.splitlines(keepends=True)
    for i,l in enumerate(lines):
        if 'requester_area' in l and 'select' in l:
            lines[i] = '                <label>{{ t(\'Área solicitante\',\'Requester area\') }}<select [(ngModel)]="cdpForm.requester_area"><option value="Logística">Logística (Compras/Servicios)</option><option value="Recursos Humanos">Recursos Humanos (Planillas/Nómina y otros)</option><option value="Otro">{{ t(\'Otro\',\'Other\') }}</option></select></label>\n'
            break
    p.write_text(''.join(lines), encoding='utf-8')
    print('OK')
else:
    print('NO')
