import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-conteos',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="fin-workspace">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">Logística · Inventario</span>
          <h1 class="fin-title-main">Conteos cíclicos</h1>
          <p class="fin-subtitle-desc">Listado básico desde API WMS.</p>
        </div>
        <div class="fin-header-actions">
          <a class="fin-secondary fin-link-btn" routerLink="/logistics/wms/inventario">← Inventario</a>
        </div>
      </header>
      @if (loading) { <div class="fin-notice">Cargando…</div> }
      @if (error) { <div class="fin-alert fin-alert-error">{{ error }}</div> }
      @if (!loading) {
        <div class="fin-panel">
          @if (!rows.length) { <div class="fin-empty">Sin registros.</div> } @else {
            <div class="fin-table-wrap">
              <table class="fin-table"><thead><tr>@for (c of cols; track c) { <th>{{ c }}</th> }</tr></thead>
                <tbody>@for (row of rows; track $index) { <tr>@for (c of cols; track c) { <td>{{ row[c] ?? '—' }}</td> }</tr> }</tbody>
              </table>
            </div>
          }
        </div>
      }
    </section>
  `
})
export class WmsConteosComponent implements OnInit {
  private readonly http = inject(HttpClient);
  loading = false; error = ''; rows: any[] = []; cols: string[] = ['id', 'estado', 'fecha', 'planta_id'];
  ngOnInit(): void {
    this.loading = true;
    const t = localStorage.getItem('aethereon.access_token');
    const headers = t ? new HttpHeaders({ Authorization: `Bearer ${t}` }) : undefined;
    this.http.get<any>('/api/v1/wms/inventario/conteos', { headers }).subscribe({
      next: (r) => { const d = Array.isArray(r) ? r : (r?.items || r?.data || r?.results || []); this.rows = Array.isArray(d) ? d : []; if (this.rows.length) this.cols = Object.keys(this.rows[0]).slice(0, 8); this.loading = false; },
      error: (e) => { this.rows = []; this.loading = false; this.error = e?.error?.detail || 'No se pudo cargar conteos.'; }
    });
  }
}
