import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { WmsTabsComponent } from './wms-tabs.component';
@Component({
  selector: 'app-wms-materiales',
  standalone: true,
  imports: [CommonModule, FormsModule, WmsTabsComponent],
  template: `
    <section class="fin-workspace">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">WMS</span>
          <h1 class="fin-title-main">Materiales</h1>
          <p class="fin-subtitle-desc">{{ total }} materiales registrados. Lista desde /api/v1/wms/materiales (Aetheron ERP).</p>
        </div>
        <div class="fin-header-actions">
          <button class="fin-primary" type="button" (click)="openCreate()">+ Nuevo Material</button>
        </div>
      </header>

      <app-wms-tabs></app-wms-tabs>

      <div class="fin-panel">
        <div class="fin-form-grid" style="grid-template-columns: 1fr auto; align-items: end;">
          <label>Buscar
            <input [(ngModel)]="q" placeholder="Buscar por código o nombre..." (keyup.enter)="load()" />
          </label>
          <div style="display:flex;gap:8px;">
            <button class="fin-secondary" type="button" (click)="load()">Buscar</button>
          </div>
        </div>
      </div>

      @if (loading) { <div class="fin-notice">Cargando…</div> }
      @if (error) { <div class="fin-alert fin-alert-error" role="alert">{{ error }}</div> }

      @if (!loading) {
        <div class="fin-panel">
          @if (rows.length === 0) {
            <div class="fin-empty">Sin resultados. Si esperas datos, verifica sesión Aetheron y que el servicio logística esté en 18005 con BD en public.</div>
          } @else {
            <div class="fin-table-wrap">
              <table class="fin-table">
                <thead>
                  <tr>
                    <th>Código SAP</th>
                    <th>Material</th>
                    <th>Categoría</th>
                    <th>Unidad</th>
                    <th style="text-align:right;">Stock</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  @for (row of rows; track row.id ?? $index) {
                    <tr>
                      <td><b>{{ row.codigo_sap || '—' }}</b></td>
                      <td>{{ row.nombre || '—' }}</td>
                      <td>{{ row.categoria || '—' }}</td>
                      <td>{{ row.unidad_medida || '—' }}</td>
                      <td style="text-align:right;">{{ fmtNum(row.stock_actual) }}</td>
                      <td>{{ row.activo === false ? 'Inactivo' : 'Activo' }}</td>
                      <td>
                        <button class="fin-secondary" type="button" (click)="openEdit(row)">Editar</button>
                        <button class="fin-secondary" type="button" (click)="confirmDelete(row)" style="margin-left:6px;">Eliminar</button>
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
            @if (totalPages > 1) {
              <div style="display:flex;justify-content:space-between;align-items:center;padding-top:12px;color:var(--muted);font-size:13px;flex-wrap:wrap;gap:8px;">
                <span>Página {{ page }} de {{ totalPages }} ({{ total }} registros)</span>
                <div style="display:flex;gap:4px;">
                  <button class="fin-secondary" type="button" [disabled]="page<=1" (click)="goPage(page-1)">«</button>
                  <button class="fin-secondary" type="button" [disabled]="page>=totalPages" (click)="goPage(page+1)">»</button>
                </div>
              </div>
            }
          }
        </div>
      }

      @if (showForm) {
        <div class="fin-panel" style="margin-top:12px;">
          <h3 style="margin:0 0 12px;">{{ editItem ? 'Editar Material' : 'Nuevo Material' }}</h3>
          <div class="fin-form-grid">
            <label>Código SAP *<input [(ngModel)]="form.codigo_sap" [disabled]="!!editItem" /></label>
            <label>Unidad<select [(ngModel)]="form.unidad_medida"><option *ngFor="let u of unidades" [value]="u">{{u}}</option></select></label>
            <label>Nombre *<input [(ngModel)]="form.nombre" /></label>
            <label>Categoría<input [(ngModel)]="form.categoria" placeholder="Opcional" /></label>
            <label>Stock mínimo<input type="number" [(ngModel)]="form.stock_minimo" /></label>
            <label>Stock máximo<input type="number" [(ngModel)]="form.stock_maximo" /></label>
            <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" [(ngModel)]="form.es_peligroso" /> Material peligroso (MATPEL)</label>
          </div>
          <div style="display:flex;gap:8px;margin-top:12px;">
            <button class="fin-primary" type="button" (click)="save()" [disabled]="saving">{{ saving ? 'Guardando…' : (editItem ? 'Guardar' : 'Crear') }}</button>
            <button class="fin-secondary" type="button" (click)="closeForm()">Cancelar</button>
          </div>
        </div>
      }

      @if (deleteTarget) {
        <div class="fin-panel" style="margin-top:12px;border-color:#f87171;">
          <p style="margin:0 0 12px;">¿Eliminar <b>{{ deleteTarget.codigo_sap }}</b> - {{ deleteTarget.nombre }}?</p>
          <div style="display:flex;gap:8px;">
            <button class="fin-primary" type="button" (click)="doDelete()">Eliminar</button>
            <button class="fin-secondary" type="button" (click)="deleteTarget=null">Cancelar</button>
          </div>
        </div>
      }
    </section>
  `
})
export class WmsMaterialesComponent implements OnInit {
  private readonly http = inject(HttpClient);
  q = '';
  loading = false;
  error = '';
  rows: any[] = [];
  total = 0;
  page = 1;
  perPage = 25;
  totalPages = 1;
  unidades = ['UN', 'KG', 'LT', 'MT', 'M2', 'TN', 'GL', 'PAR'];

  showForm = false;
  editItem: any = null;
  saving = false;
  form: any = { codigo_sap: '', nombre: '', categoria: '', unidad_medida: 'UN', es_peligroso: false, stock_minimo: '', stock_maximo: '' };

  deleteTarget: any = null;

  ngOnInit(): void { this.load(); }
  private authHeaders(): { headers?: HttpHeaders } {
    const t = localStorage.getItem('aethereon.access_token');
    return t ? { headers: new HttpHeaders({ Authorization: `Bearer ${t}` }) } : {};
  }
  load(): void {
    this.loading = true;
    this.error = '';
    let params = new HttpParams().set('page', String(this.page)).set('per_page', String(this.perPage));
    if (this.q.trim()) params = params.set('search', this.q.trim());
    this.http.get<any>('/api/v1/wms/materiales', { params, ...this.authHeaders() }).subscribe({
      next: (r) => {
        if (Array.isArray(r)) {
          this.rows = r;
          this.total = r.length;
        } else {
          this.rows = r?.items || r?.data || r?.results || [];
          this.total = r?.total ?? r?.pagination?.total ?? this.rows.length;
        }
        this.totalPages = Math.max(1, Math.ceil(this.total / this.perPage));
        this.loading = false;
      },
      error: (e) => {
        this.rows = [];
        this.loading = false;
        if (e?.status === 401) this.error = 'No autorizado. Inicia sesión en Aetheron ERP.';
        else this.error = e?.error?.detail || 'No se pudo cargar materiales.';
      }
    });
  }
  goPage(p: number) { this.page = p; this.load(); }
  fmtNum(v: any): string { if (v == null || v === '') return '—'; const n = Number(v); return isNaN(n) ? String(v) : n.toLocaleString(); }
  openCreate() {
    this.editItem = null;
    this.form = { codigo_sap: '', nombre: '', categoria: '', unidad_medida: 'UN', es_peligroso: false, stock_minimo: '', stock_maximo: '' };
    this.showForm = true;
  }
  openEdit(row: any) {
    this.editItem = row;
    this.form = {
      codigo_sap: row.codigo_sap || '',
      nombre: row.nombre || '',
      categoria: row.categoria || '',
      unidad_medida: row.unidad_medida || 'UN',
      es_peligroso: !!row.es_peligroso,
      stock_minimo: row.stock_minimo ?? '',
      stock_maximo: row.stock_maximo ?? '',
    };
    this.showForm = true;
  }
  closeForm() { this.showForm = false; this.editItem = null; }
  save() {
    if (!this.form.codigo_sap?.trim() || !this.form.nombre?.trim()) { this.error = 'Código SAP y Nombre son requeridos.'; return; }
    this.saving = true;
    this.error = '';
    const payload: any = {
      codigo_sap: this.form.codigo_sap.trim(),
      nombre: this.form.nombre.trim(),
      categoria: this.form.categoria?.trim() || null,
      unidad_medida: this.form.unidad_medida || 'UN',
      es_peligroso: !!this.form.es_peligroso,
      stock_minimo: this.form.stock_minimo === '' || this.form.stock_minimo == null ? null : Number(this.form.stock_minimo),
      stock_maximo: this.form.stock_maximo === '' || this.form.stock_maximo == null ? null : Number(this.form.stock_maximo),
    };
    const req = this.editItem
      ? this.http.put(`/api/v1/wms/materiales/${this.editItem.id}`, payload, this.authHeaders())
      : this.http.post('/api/v1/wms/materiales', payload, this.authHeaders());
    req.subscribe({
      next: () => { this.saving = false; this.closeForm(); this.load(); },
      error: (e) => { this.saving = false; this.error = e?.error?.detail || 'No se pudo guardar el material.'; }
    });
  }
  confirmDelete(row: any) { this.deleteTarget = row; }
  doDelete() {
    if (!this.deleteTarget) return;
    this.http.delete(`/api/v1/wms/materiales/${this.deleteTarget.id}`, this.authHeaders()).subscribe({
      next: () => { this.deleteTarget = null; this.load(); },
      error: (e) => { this.error = e?.error?.detail || 'No se pudo eliminar.'; this.deleteTarget = null; }
    });
  }
}
