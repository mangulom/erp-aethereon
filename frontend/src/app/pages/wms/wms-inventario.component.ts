import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-inventario',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section style="padding:24px;color:#e8edf5;">
      <h2>WMS · Inventario</h2>
      <p style="color:#94a3b8;">Resumen y accesos rápidos (datos desde /api/wms).</p>
      @if (error) { <p style="color:#fca5a5;">{{ error }}</p> }
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0;">
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;"><div style="font-size:11px;color:#8fa0b3;">Total SKUs</div><div style="font-size:22px;font-weight:700;">{{ data?.total_skus ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;"><div style="font-size:11px;color:#8fa0b3;">Valor</div><div style="font-size:22px;font-weight:700;">{{ data?.valor ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;"><div style="font-size:11px;color:#8fa0b3;">Mov. hoy</div><div style="font-size:22px;font-weight:700;">{{ data?.movimientos_hoy ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;"><div style="font-size:11px;color:#8fa0b3;">Alertas</div><div style="font-size:22px;font-weight:700;">{{ data?.alertas ?? '—' }}</div></div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;">
        <a routerLink="/logistics/wms/inventario/stock" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Consulta Stock</a>
        <a routerLink="/logistics/wms/inventario/movimientos" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Movimientos</a>
        <a routerLink="/logistics/wms/inventario/conteos" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Conteos</a>
        <a routerLink="/logistics/wms/lotes" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Lotes</a>
        <a routerLink="/logistics/wms" style="padding:10px 14px;border:1px solid #555;border-radius:8px;color:#ccc;text-decoration:none;">← Panel WMS</a>
      </div>
    </section>
  `
})
export class WmsInventarioComponent implements OnInit {
  private readonly http = inject(HttpClient);
  data: any = null;
  error = '';
  ngOnInit(): void {
    this.http.get<any>('/api/wms/inventario/dashboard').subscribe({
      next: (r) => (this.data = r || null),
      error: () => { this.error = 'No se pudo cargar dashboard de inventario (verifica API WMS).'; }
    });
  }
}
