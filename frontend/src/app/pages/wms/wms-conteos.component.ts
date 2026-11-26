import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-conteos',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section style="padding:24px;color:#e8edf5;">
      <h2>WMS · Conteos cíclicos</h2>
      <p style="color:#94a3b8;">Listado básico desde <code>/api/wms/inventario/conteos</code> si existe.</p>
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
      <p style="margin-top:12px;"><a routerLink="/logistics/wms/inventario" style="color:#43c6b0;">← Inventario</a></p>
    </section>
  `
})
export class WmsConteosComponent implements OnInit {
  private readonly http = inject(HttpClient);
  loading = false; error = ''; rows: any[] = []; cols: string[] = ['id', 'estado', 'fecha', 'planta_id'];
  ngOnInit(): void {
    this.loading = true;
    this.http.get<any>('/api/wms/inventario/conteos').subscribe({
      next: (r) => { const d = Array.isArray(r) ? r : (r?.items || r?.data || r?.results || []); this.rows = Array.isArray(d) ? d : []; if (this.rows.length) this.cols = Object.keys(this.rows[0]).slice(0, 8); this.loading = false; },
      error: (e) => { this.rows = []; this.loading = false; this.error = e?.error?.detail || 'No se pudo cargar conteos (endpoint puede no existir aún).'; }
    });
  }
}
