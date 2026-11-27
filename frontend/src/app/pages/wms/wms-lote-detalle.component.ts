import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-lote-detalle',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="fin-workspace">
      <header class="fin-header fin-header-advanced">
        <div class="fin-header-main">
          <span class="panel-kicker">Logística · Lotes</span>
          <h1 class="fin-title-main">{{ lote?.numero || 'Detalle de Lote' }}</h1>
          <p class="fin-subtitle-desc">Información del lote / subítem.</p>
        </div>
        <div class="fin-header-actions">
          <a class="fin-secondary fin-link-btn" routerLink="/logistics/wms/lotes">← Volver a Lotes</a>
        </div>
      </header>
      @if (loading) { <div class="fin-notice">Cargando…</div> }
      @if (error) { <div class="fin-alert fin-alert-error">{{ error }}</div> }
      @if (lote && !loading) {
        <div class="fin-panel">
          <div class="fin-form-grid">
            <div><strong>Número:</strong> {{ lote.numero || '—' }}</div>
            <div><strong>Material ID:</strong> {{ lote.material_id || '—' }}</div>
            <div><strong>Fecha fabricación:</strong> {{ lote.fecha_fabricacion || '—' }}</div>
            <div><strong>Fecha vencimiento:</strong> {{ lote.fecha_vencimiento || '—' }}</div>
            <div><strong>Cantidad:</strong> {{ lote.cantidad ?? '—' }}</div>
            <div><strong>Estado:</strong> {{ lote.estado || '—' }}</div>
          </div>
        </div>
      }
    </section>
  `
})
export class WmsLoteDetalleComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  lote: any = null;
  loading = false;
  error = '';
  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) { this.error = 'ID no proporcionado.'; return; }
    this.loading = true;
    const t = localStorage.getItem('aethereon.access_token');
    const headers = t ? new HttpHeaders({ Authorization: `Bearer ${t}` }) : undefined;
    this.http.get<any>(`/api/v1/wms/lotes/${id}`, { headers }).subscribe({
      next: (r) => { this.lote = r; this.loading = false; },
      error: (e) => { this.error = e?.error?.detail || 'No se pudo cargar el lote.'; this.loading = false; }
    });
  }
}
