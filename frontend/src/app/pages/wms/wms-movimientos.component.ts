import { CommonModule } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-movimientos',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section style="padding:24px;color:#e8edf5;">
      <h2>WMS · Movimientos</h2>
      <div style="display:flex;gap:8px;margin:12px 0;flex-wrap:wrap;">
        <input [(ngModel)]="q" placeholder="Buscar..." style="padding:8px 10px;border-radius:8px;border:1px solid #334155;background:#0b1422;color:#e8edf5;" (keyup.enter)="load()" />
        <button type="button" (click)="load()" style="padding:8px 14px;border-radius:8px;border:1px solid #43c6b0;background:#43c6b0;color:#072622;font-weight:600;cursor:pointer;">Buscar</button>
        <a routerLink="/logistics/wms/inventario" style="padding:8px 14px;border-radius:8px;border:1px solid #555;color:#ccc;text-decoration:none;">← Inventario</a>
      </div>
      @if (loading) { <p style="color:#94a3b8;">Cargando…</p> }
      @if (error) { <p style="color:#fca5a5;">{{ error }}</p> }
      <div style="overflow:auto;border:1px solid #2a3448;border-radius:10px;">
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <thead><tr style="text-align:left;background:#111a2b;color:#8fa0b3;">@for (c of cols; track c) { <th style="padding:10px 12px;border-bottom:1px solid #2a3448;">{{ c }}</th> }</tr></thead>
          <tbody>
            @for (row of rows; track $index) { <tr style="border-bottom:1px solid #1e293b;">@for (c of cols; track c) { <td style="padding:10px 12px;">{{ row[c] ?? '—' }}</td> }</tr> }
            @if (!rows.length && !loading) { <tr><td [attr.colspan]="cols.length||1" style="padding:16px;color:#94a3b8;">Sin registros.</td></tr> }
          </tbody>
        </table>
      </div>
    </section>
  `
})
export class WmsMovimientosComponent implements OnInit {
  private readonly http = inject(HttpClient);
  q = ''; loading = false; error = ''; rows: any[] = []; cols: string[] = ['fecha', 'tipo', 'material_id', 'cantidad', 'referencia', 'motivo'];
  ngOnInit(): void { this.load(); }
  load(): void {
    this.loading = true; this.error = '';
    let params = new HttpParams().set('page', '1').set('per_page', '100');
    if (this.q.trim()) params = params.set('search', this.q.trim());
    this.http.get<any>('/api/wms/inventario/movimientos', { params }).subscribe({
      next: (r) => { const d = Array.isArray(r) ? r : (r?.items || r?.data || r?.results || []); this.rows = Array.isArray(d) ? d : []; if (this.rows.length) this.cols = Object.keys(this.rows[0]).slice(0, 8); this.loading = false; },
      error: (e) => { this.rows = []; this.loading = false; this.error = e?.error?.detail || 'No se pudo cargar movimientos.'; }
    });
  }
}
