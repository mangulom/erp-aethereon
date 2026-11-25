from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\package.json')
s = p.read_text(encoding='utf-8')
if '"aethereon-erp-shell"' in s:
    s2 = s.replace('"aethereon-erp-shell"', '"sophia-erp-shell"')
    p.write_text(s2, encoding='utf-8')
    print('done')
else:
    print('not found')
