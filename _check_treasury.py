from pathlib import Path
p = Path(r"D:\WorkSpace\ERPAethereon\frontend\src\app\pages\finance\finance.component.ts")
s = p.read_text(encoding="utf-8", errors="replace")
idx = s.find("tab === 'treasury'")
if idx < 0:
    print("NO")
else:
    print(repr(s[idx:idx+2000]))
