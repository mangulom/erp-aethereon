import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section style="padding:24px;color:#e8edf5;">
      <h1 style="margin:0 0 8px;">WMS · Panel</h1>
      <p style="color:#94a3b8;max-width:760px;">Panel integrado (migración desde React). Datos desde <code>/api/wms</code> cuando el servicio WMS esté activo en 18005.</p>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0;">
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;"><div style="font-size:11px;color:#8fa0b3;">MATERIALES</div><div style="font-size:24px;font-weight:700;">{{ summary['materiales'] ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;"><div style="font-size:11px;color:#8fa0b3;">ALMACENES</div><div style="font-size:24px;font-weight:700;">{{ summary['almacenes'] ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;"><div style="font-size:11px;color:#8fa0b3;">RECEPCIONES</div><div style="font-size:24px;font-weight:700;">{{ summary['recepciones'] ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;"><div style="font-size:11px;color:#8fa0b3;">DESPACHOS</div><div style="font-size:24px;font-weight:700;">{{ summary['despachos'] ?? '—' }}</div></div>
      </div>
      @if (error) { <p style="color:#fca5a5;">{{ error }}</p> }
      <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:16px;">
        <a routerLink="/logistics/wms/materiales" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Ítems (Materiales)</a>
        <a routerLink="/logistics/wms/inventario" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Inventario / Stock</a>
        <a routerLink="/logistics/wms/recepciones" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Recepciones</a>
        <a routerLink="/logistics/wms/despachos" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Despachos</a>
        <a routerLink="/logistics/wms/lotes" style="padding:10px 14px;border:1px solid #43c6b0;border-radius:8px;color:#43c6b0;text-decoration:none;">Lotes / Subítems</a>
        <a routerLink="/logistics/wms/matpel" style="padding:10px 14px;border:1px solid #555;border-radius:8px;color:#ccc;text-decoration:none;">MATPEL</a>
        <a routerLink="/logistics/wms/sap" style="padding:10px 14px;border:1px solid #555;border-radius:8px;color:#ccc;text-decoration:none;">SAP</a>
        <a routerLink="/logistics/wms/ia" style="padding:10px 14px;border:1px solid #555;border-radius:8px;color:#ccc;text-decoration:none;">Motor IA</a>
        <a routerLink="/logistics" style="padding:10px 14px;border:1px solid #555;border-radius:8px;color:#ccc;text-decoration:none;">← Logística</a>
      </div>
    </section>
  `
})
export class WmsDashboardComponent implements OnInit {
  private readonly http = inject(HttpClient);
  summary: Record<string, any> = {};
  error = '';
  ngOnInit(): void {
    this.http.get<any>('/api/wms/materiales/dashboard/summary').subscribe({
      next: (r) => (this.summary = r || {}),
      error: () => { this.error = 'No se pudo cargar resumen WMS (verifica servicio en 18005 y auth si aplica).'; }
    });
  }
}
