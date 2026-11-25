from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\budgets\budgets.component.ts')
s = p.read_text(encoding='utf-8', errors='replace')

# insert after closeCdpModal
old = "  closeCdpModal() { this.showCdpModal = false; this.editingCdpId = null; }\n  removeCdp"
if old not in s:
    print('NO')
else:
    insert = """  closeCdpModal() { this.showCdpModal = false; this.editingCdpId = null; }
  openCommitModal(item?: any) {
    this.showCommitModal = true; this.error = '';
    if (item) { this.editingCommitId = item.id; this.commitForm = { number: item.number||'', date: item.date||'', reference: item.reference||'', amount: item.amount||0, status: item.status||'comprometido', cdp_id: item.cdp_id||'', supplier_id: item.supplier_id||'' }; }
    else { this.editingCommitId = null; this.commitForm = { number:'', date:'', reference:'', amount:0, status:'comprometido', cdp_id:'', supplier_id:'' }; }
  }
  closeCommitModal() { this.showCommitModal = false; this.editingCommitId = null; }
  openPayModal(item?: any) {
    this.showPayModal = true; this.error = '';
    if (item) { this.editingPayId = item.id; this.payForm = { number: item.number||'', date: item.date||'', payee: item.payee||'', amount: item.amount||0, status: item.status||'emitida', supplier_id: item.supplier_id||'' }; }
    else { this.editingPayId = null; this.payForm = { number:'', date:'', payee:'', amount:0, status:'emitida', supplier_id:'' }; }
  }
  closePayModal() { this.showPayModal = false; this.editingPayId = null; }
  removeCdp"""
    s2 = s.replace(old, insert, 1)
    p.write_text(s2, encoding='utf-8')
    print('OK')
