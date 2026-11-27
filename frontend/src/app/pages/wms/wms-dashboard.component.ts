import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { WmsTabsComponent } from './wms-tabs.component';

@Component({
  selector: 'app-wms-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, WmsTabsComponent],
  template: `
    <section class="fin-workspace" style="padding:24px;color:#e8edf5;">
      <header class="fin-header fin-header-advanced" style="margin-bottom:16px;">
        <div class="fin-header-main">
          <span class="panel-kicker">WMS REPSOL · AETHEREON</span>
          <h1 class="fin-title-main">Gestión de Almacén (WMS)</h1>
          <p class="fin-subtitle-desc">Control operativo integral: materiales, inventario, lotes, recepciones, despachos, cumplimiento regulatorio e integración.</p>
        </div>
      </header>

      <app-wms-tabs></app-wms-tabs>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0;">
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;background:#101321;"><div style="font-size:11px;color:#8fa0b3;font-weight:700;">MATERIALES</div><div style="font-size:24px;font-weight:700;margin-top:4px;">{{ summary['materiales'] ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;background:#101321;"><div style="font-size:11px;color:#8fa0b3;font-weight:700;">ALMACENES</div><div style="font-size:24px;font-weight:700;margin-top:4px;">{{ summary['almacenes'] ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;background:#101321;"><div style="font-size:11px;color:#8fa0b3;font-weight:700;">RECEPCIONES</div><div style="font-size:24px;font-weight:700;margin-top:4px;">{{ summary['recepciones'] ?? '—' }}</div></div>
        <div style="border:1px solid #2a3448;border-radius:10px;padding:14px;background:#101321;"><div style="font-size:11px;color:#8fa0b3;font-weight:700;">DESPACHOS</div><div style="font-size:24px;font-weight:700;margin-top:4px;">{{ summary['despachos'] ?? '—' }}</div></div>
      </div>
      @if (error) { <p style="color:#fca5a5;">{{ error }}</p> }
    </section>
  `
})
export class WmsDashboardComponent implements OnInit {
  private readonly http = inject(HttpClient);
  summary: Record<string, any> = {};
  error = '';
  ngOnInit(): void {
    this.http.get<any>('/api/v1/wms/materiales/dashboard/summary').subscribe({
      next: (r) => (this.summary = r || {}),
      error: () => { this.error = 'No se pudo cargar resumen WMS (verifica servicio en 18005 y auth si aplica).'; }
    });
  }
}
