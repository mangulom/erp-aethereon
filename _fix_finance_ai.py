from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\finance-ai\finance-ai.component.ts')
s = p.read_text(encoding='utf-8', errors='replace')
s2 = s.replace("AETHEREON INTELLIGENCE", "SOPHIA INTELLIGENCE")
if s != s2:
    p.write_text(s2, encoding='utf-8')
    print('replaced')
else:
    print('no change')
