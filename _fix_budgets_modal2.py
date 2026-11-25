from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\budgets\budgets.component.ts')
lines = p.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
# replace line 161 (0-based 160) and 162 (161)
lines[160] = """  openCdpModal(item?: any) {
    this.showCdpModal = true; this.error = '';
    if (item) { this.editingCdpId = item.id; this.cdpForm = { number: item.number||'', date: item.date||'', line: item.line||'', amount: item.amount||0, status: item.status||'vigente', requester_area: item.requester_area||'Logística' }; }
    else { this.editingCdpId = null; this.cdpForm = { number:'', date:'', line:'', amount:0, status:'vigente', requester_area:'Logística' }; }
  }
  closeCdpModal() { this.showCdpModal = false; this.editingCdpId = null; }
"""
lines[161] = "  removeCdp(id: string) { alert(this.t('Eliminar no implementado en backend aún.','Delete not implemented in backend yet.')); }\n"
p.write_text(''.join(lines), encoding='utf-8')
print('done')
