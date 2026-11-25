from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\budgets\budgets.component.ts')
s = p.read_text(encoding='utf-8', errors='replace')

old = "  closeCdpModal() { this.showCdpModal = false; this.editingCdpId = null; }\n  removeCdp(id: string) { alert(this.t('Eliminar no implementado en backend a�n.','Delete not implemented in backend yet.')); }"
if old not in s:
    print('NO1')
else:
    new = """  openCdpModal(item?: any) {
    this.showCdpModal = true; this.error = '';
    if (item) { this.editingCdpId = item.id; this.cdpForm = { number: item.number||'', date: item.date||'', line: item.line||'', amount: item.amount||0, status: item.status||'vigente', requester_area: item.requester_area||'Logística' }; }
    else { this.editingCdpId = null; this.cdpForm = { number:'', date:'', line:'', amount:0, status:'vigente', requester_area:'Logística' }; }
  }
  closeCdpModal() { this.showCdpModal = false; this.editingCdpId = null; }
  removeCdp(id: string) { alert(this.t('Eliminar no implementado en backend aún.','Delete not implemented in backend yet.')); }"""
    s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')
    print('OK1')
