import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-materiales',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section style="padding:24px;color:#e8edf5;">
      <h2 style="margin:0 0 6px;">WMS · Ítems (Materiales)</h2>
      <p style="color:#94a3b8;max-width:760px;">Lista desde <code>/api/wms/materiales</code>. Si no ves datos, verifica que el servicio WMS esté en 18005 y que tengas sesión WMS (usa el módulo Logística para conectar si es necesario).</p>
      <div style="display:flex;gap:8px;margin:12px 0;flex-wrap:wrap;">
        <input [(ngModel)]="q" placeholder="Buscar..." style="padding:8px 10px;border-radius:8px;border:1px solid #334155;background:#0b1422;color:#e8edf5;min-width:220px;" (keyup.enter)="load()" />
        <button type="button" (click)="load()" style="padding:8px 14px;border-radius:8px;border:1px solid #43c6b0;background:#43c6b0;color:#072622;font-weight:600;cursor:pointer;">Buscar / Actualizar</button>
        <a routerLink="/logistics/wms" style="padding:8px 14px;border-radius:8px;border:1px solid #555;color:#ccc;text-decoration:none;">← Panel WMS</a>
      </div>
      @if (loading) { <p style="color:#94a3b8;">Cargando…</p> }
      @if (error) { <p style="color:#fca5a5;">{{ error }}</p> }
      @if (!loading && !error) {
        <div style="overflow:auto;border:1px solid #2a3448;border-radius:10px;">
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead><tr style="text-align:left;background:#111a2b;color:#8fa0b3;">
              @for (c of cols; track c) { <th style="padding:10px 12px;border-bottom:1px solid #2a3448;">{{ c }}</th> }
            </tr></thead>
            <tbody>
              @for (row of rows; track row.id ?? $index) {
                <tr style="border-bottom:1px solid #1e293b;">
                  @for (c of cols; track c) { <td style="padding:10px 12px;">{{ fmt(row[c]) }}</td> }
                </tr>
              }
              @if (!rows.length) { <tr><td [attr.colspan]="cols.length" style="padding:16px;color:#94a3b8;">Sin registros (si la BD tiene datos en public.wms_* verifica que el backend use DB_SCHEMA=public y que la tabla sea 'materiales' en public).</td></tr> }
            </tbody>
          </table>
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
  cols: string[] = ['codigo_sap', 'nombre', 'unidad_medida', 'stock_minimo', 'stock_maximo', 'activo'];
  ngOnInit(): void { this.load(); }
  private authHeaders(): { headers?: HttpHeaders } {
    const t = localStorage.getItem('aethereon.wms_access_token');
    return t ? { headers: new HttpHeaders({ Authorization: `Bearer ${t}` }) } : {};
  }
  load(): void {
    this.loading = true;
    this.error = '';
    let params = new HttpParams().set('page', '1').set('per_page', '100');
    if (this.q.trim()) params = params.set('search', this.q.trim());
    this.http.get<any>('/api/wms/materiales', { params, ...this.authHeaders() }).subscribe({
      next: (r) => {
        const data = Array.isArray(r) ? r : (r?.items || r?.data || r?.results || []);
        this.rows = Array.isArray(data) ? data : [];
        if (this.rows.length) {
          const preferred = ['codigo_sap', 'nombre', 'unidad_medida', 'stock_minimo', 'stock_maximo', 'activo'];
          this.cols = preferred.filter(c => c in this.rows[0]);
        }
        this.loading = false;
      },
      error: (e) => {
        this.rows = [];
        this.loading = false;
        if (e?.status === 401) {
          this.error = 'No autorizado en WMS. Conéctate desde el módulo Logística (botón Conectar WMS) o verifica el token.';
        } else {
          this.error = e?.error?.detail || 'No se pudo cargar materiales. Verifica que el backend logística esté en 18005 y la BD en public.';
        }
      }
    });
  }
  fmt(v: any): string { if (v == null || v === '') return '—'; if (typeof v === 'boolean') return v ? 'Sí' : 'No'; return String(v); }
}
