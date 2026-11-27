import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { WmsTabsComponent } from './wms-tabs.component';

@Component({
  selector: 'app-wms-lotes',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, WmsTabsComponent],
  template: `
    <section class="fin-workspace">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">Logística · Lotes</span>
          <h1 class="fin-title-main">Lotes / Subítems</h1>
        </div>
        <div class="fin-header-actions"></div>
      </header>

      <app-wms-tabs></app-wms-tabs>
      <div class="fin-panel">
        <div class="fin-form-grid" style="grid-template-columns: 1fr auto; align-items: end;">
          <label>Buscar<input [(ngModel)]="q" placeholder="Buscar lote..." (keyup.enter)="load()" /></label>
          <button class="fin-secondary" type="button" (click)="load()">Buscar</button>
        </div>
      </div>
      @if (loading) { <div class="fin-notice">Cargando…</div> }
      @if (error) { <div class="fin-alert fin-alert-error">{{ error }}</div> }
      @if (!loading) {
        <div class="fin-panel">
          @if (!rows.length) { <div class="fin-empty">Sin registros.</div> } @else {
            <div class="fin-table-wrap">
              <table class="fin-table"><thead><tr>@for (c of cols; track c) { <th>{{ c }}</th> }</tr></thead>
                <tbody>@for (row of rows; track row.id ?? $index) { <tr><td><a [routerLink]="['/logistics/wms/lotes', row.id]" style="color:var(--accent);">{{ row.numero || row.id || '—' }}</a></td>@for (c of cols.slice(1); track c) { <td>{{ row[c] ?? '—' }}</td> }</tr> }</tbody>
              </table>
            </div>
          }
        </div>
      }
    </section>
  `
})
export class WmsLotesComponent implements OnInit {
  private readonly http = inject(HttpClient);
  q = ''; loading = false; error = ''; rows: any[] = []; cols: string[] = ['numero', 'material_id', 'fecha_fabricacion', 'fecha_vencimiento', 'cantidad', 'estado'];
  ngOnInit(): void { this.load(); }
  private authHeaders(): { headers?: HttpHeaders } {
    const t = localStorage.getItem('aethereon.access_token');
    return t ? { headers: new HttpHeaders({ Authorization: `Bearer ${t}` }) } : {};
  }
  load(): void {
    this.loading = true; this.error = '';
    let params = new HttpParams().set('page', '1').set('per_page', '100');
    if (this.q.trim()) params = params.set('search', this.q.trim());
    this.http.get<any>('/api/v1/wms/lotes', { params, ...this.authHeaders() }).subscribe({
      next: (r) => { const d = Array.isArray(r) ? r : (r?.items || r?.data || r?.results || []); this.rows = Array.isArray(d) ? d : []; if (this.rows.length) this.cols = Object.keys(this.rows[0]).slice(0, 8); this.loading = false; },
      error: (e) => { this.rows = []; this.loading = false; this.error = e?.error?.detail || 'No se pudo cargar lotes.'; }
    });
  }
}
