import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-material-detalle',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="fin-workspace">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">Logística · Ítems</span>
          <h1 class="fin-title-main">{{ item?.nombre || 'Detalle de Material' }}</h1>
          <p class="fin-subtitle-desc">Código: {{ item?.codigo_sap || '—' }}</p>
        </div>
        <div class="fin-header-actions">
          <a class="fin-secondary fin-link-btn" routerLink="/logistics/wms/materiales">← Volver a Ítems</a>
        </div>
      </header>
      @if (loading) { <div class="fin-notice">Cargando…</div> }
      @if (error) { <div class="fin-alert fin-alert-error">{{ error }}</div> }
      @if (item && !loading) {
        <div class="fin-panel">
          <div class="fin-form-grid">
            <div><strong>Código SAP:</strong> {{ item.codigo_sap || '—' }}</div>
            <div><strong>Nombre:</strong> {{ item.nombre || '—' }}</div>
            <div><strong>Categoría:</strong> {{ item.categoria || '—' }}</div>
            <div><strong>Unidad:</strong> {{ item.unidad_medida || '—' }}</div>
            <div><strong>Stock mínimo:</strong> {{ item.stock_minimo ?? '—' }}</div>
            <div><strong>Stock máximo:</strong> {{ item.stock_maximo ?? '—' }}</div>
            <div><strong>Activo:</strong> {{ item.activo === false ? 'No' : 'Sí' }}</div>
            <div><strong>MATPEL:</strong> {{ item.es_peligroso ? 'Sí' : 'No' }}</div>
          </div>
        </div>
        <div class="fin-panel" style="margin-top:12px;">
          <h3 style="margin:0 0 8px;">Subítems / Información relacionada</h3>
          <p style="color:var(--muted);margin:0;">Aquí se pueden mostrar tablas, insumos, lotes asociados y stock por ubicación (según API disponible).</p>
        </div>
      }
    </section>
  `
})
export class WmsMaterialDetalleComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  item: any = null;
  loading = false;
  error = '';
  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) { this.error = 'ID no proporcionado.'; return; }
    this.loading = true;
    const t = localStorage.getItem('aethereon.access_token');
    const headers = t ? new HttpHeaders({ Authorization: `Bearer ${t}` }) : undefined;
    this.http.get<any>(`/api/v1/wms/materiales/${id}`, { headers }).subscribe({
      next: (r) => { this.item = r; this.loading = false; },
      error: (e) => { this.error = e?.error?.detail || 'No se pudo cargar el material.'; this.loading = false; }
    });
  }
}
