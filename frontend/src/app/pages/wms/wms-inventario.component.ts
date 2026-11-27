import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { WmsTabsComponent } from './wms-tabs.component';

@Component({
  selector: 'app-wms-inventario',
  standalone: true,
  imports: [CommonModule, RouterLink, WmsTabsComponent],
  template: `
    <section class="fin-workspace">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">Logística · Inventario</span>
          <h1 class="fin-title-main">Inventario</h1>
          <p class="fin-subtitle-desc">Resumen y accesos a stock, movimientos y conteos.</p>
        </div>
        <div class="fin-header-actions"></div>
      </header>

      <app-wms-tabs></app-wms-tabs>
      @if (error) { <div class="fin-alert fin-alert-error">{{ error }}</div> }
      <div class="fin-panel">
        <div class="fin-overview-grid">
          <article class="fin-kpi-card"><span class="panel-kicker">Total SKUs</span><div class="fin-kpi-value">{{ data?.total_skus ?? '—' }}</div></article>
          <article class="fin-kpi-card"><span class="panel-kicker">Valor</span><div class="fin-kpi-value">{{ data?.valor ?? '—' }}</div></article>
          <article class="fin-kpi-card"><span class="panel-kicker">Mov. hoy</span><div class="fin-kpi-value">{{ data?.movimientos_hoy ?? '—' }}</div></article>
          <article class="fin-kpi-card"><span class="panel-kicker">Alertas</span><div class="fin-kpi-value">{{ data?.alertas ?? '—' }}</div></article>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:16px;">
          <a class="fin-primary fin-link-btn" routerLink="/logistics/wms/inventario/stock">Consulta Stock</a>
          <a class="fin-secondary fin-link-btn" routerLink="/logistics/wms/inventario/movimientos">Movimientos</a>
          <a class="fin-secondary fin-link-btn" routerLink="/logistics/wms/inventario/conteos">Conteos</a>
          <a class="fin-secondary fin-link-btn" routerLink="/logistics/wms/lotes">Lotes</a>
        </div>
      </div>
    </section>
  `
})
export class WmsInventarioComponent implements OnInit {
  private readonly http = inject(HttpClient);
  data: any = null;
  error = '';
  ngOnInit(): void {
    this.http.get<any>('/api/v1/wms/inventario/dashboard').subscribe({
      next: (r) => (this.data = r || null),
      error: () => { this.error = 'No se pudo cargar dashboard de inventario (verifica API WMS y sesión Aetheron).'; }
    });
  }
}
