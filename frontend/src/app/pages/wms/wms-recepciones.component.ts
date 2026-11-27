import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { WmsTabsComponent } from './wms-tabs.component';

@Component({
  selector: 'app-wms-recepciones',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, WmsTabsComponent],
  template: `
    <section class="fin-workspace">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">Logística · WMS</span>
          <h1 class="fin-title-main">Recepciones</h1>
          <p class="fin-subtitle-desc">Listado de recepciones desde el módulo WMS.</p>
        </div>
        <div class="fin-header-actions">
          <a class="fin-primary fin-link-btn" routerLink="/logistics/wms/recepciones/nueva">+ Nueva recepción</a>
        </div>
      </header>

      <app-wms-tabs></app-wms-tabs>
      <div class="fin-panel">
        <div class="fin-form-grid" style="grid-template-columns: 1fr auto; align-items: end;">
          <label>Buscar<input [(ngModel)]="q" placeholder="Buscar..." (keyup.enter)="load()" /></label>
          <button class="fin-secondary" type="button" (click)="load()">Buscar</button>
        </div>
      </div>
      @if (loading) { <div class="fin-notice">Cargando…</div> }
      @if (error) { <div class="fin-alert fin-alert-error">{{ error }}</div> }
      @if (!loading) {
        <div class="fin-panel">
          @if (!rows.length) { <div class="fin-empty">Sin registros.</div> } @else {
            <div class="fin-table-wrap">
              <table class="fin-table">
                <thead><tr>@for (c of cols; track c) { <th>{{ c }}</th> }<th>Acciones</th></tr></thead>
                <tbody>@for (row of rows; track row.id ?? $index) { <tr>@for (c of cols; track c) { <td>{{ row[c] ?? '—' }}</td> }<td><a class="fin-secondary fin-link-btn" [routerLink]="['/logistics/wms/recepciones', row.id]" style="margin-right:6px;">Ver/Editar</a><button class="fin-secondary" type="button" (click)="confirmDelete(row)">Eliminar</button></td></tr> }</tbody>
              </table>
            </div>
          }
        </div>
      }
      @if (deleteTarget) {
        <div class="fin-panel" style="margin-top:12px;border-color:#f87171;">
          <p style="margin:0 0 12px;">¿Eliminar recepción <b>{{ deleteTarget.numero || deleteTarget.id }}</b>?</p>
          <div style="display:flex;gap:8px;">
            <button class="fin-primary" type="button" (click)="doDelete()">Eliminar</button>
            <button class="fin-secondary" type="button" (click)="deleteTarget=null">Cancelar</button>
          </div>
        </div>
      }
    </section>
  `
})
export class WmsRecepcionesComponent implements OnInit {
  private readonly http = inject(HttpClient);
  q = ''; loading = false; error = ''; rows: any[] = []; cols: string[] = ['numero', 'orden_compra', 'proveedor_id', 'planta_id', 'estado', 'fecha'];
  deleteTarget: any = null;
  ngOnInit(): void { this.load(); }
  private authHeaders(): { headers?: HttpHeaders } {
    const t = localStorage.getItem('aethereon.access_token');
    return t ? { headers: new HttpHeaders({ Authorization: `Bearer ${t}` }) } : {};
  }
  load(): void {
    this.loading = true; this.error = '';
    let params = new HttpParams().set('page', '1').set('per_page', '100');
    if (this.q.trim()) params = params.set('search', this.q.trim());
    this.http.get<any>('/api/v1/wms/recepciones', { params, ...this.authHeaders() }).subscribe({
      next: (r) => { const d = Array.isArray(r) ? r : (r?.items || r?.data || r?.results || []); this.rows = Array.isArray(d) ? d : []; if (this.rows.length) this.cols = Object.keys(this.rows[0]).slice(0, 8); this.loading = false; },
      error: (e) => { this.rows = []; this.loading = false; this.error = e?.error?.detail || 'No se pudo cargar recepciones.'; }
    });
  }
  confirmDelete(row: any) { this.deleteTarget = row; }
  doDelete() {
    if (!this.deleteTarget?.id) return;
    this.http.delete(`/api/v1/wms/recepciones/${this.deleteTarget.id}`, this.authHeaders()).subscribe({
      next: () => { this.deleteTarget = null; this.load(); },
      error: (e) => { this.error = e?.error?.detail || 'No se pudo eliminar.'; this.deleteTarget = null; }
    });
  }
}
