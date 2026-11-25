from pathlib import Path
p = Path(r"D:\WorkSpace\ERPAethereon\frontend\src\app\pages\finance\finance.component.ts")
s = p.read_text(encoding="utf-8", errors="replace")
idx = s.find("@if (tab === 'treasury')")
out = Path(r"D:\WorkSpace\ERPAethereon\_treasury_out3.txt")
if idx < 0:
    out.write_text("NO", encoding="utf-8")
else:
    out.write_text(s[idx:idx+3500], encoding="utf-8")
print("done")
