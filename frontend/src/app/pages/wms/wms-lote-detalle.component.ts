import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-lote-detalle',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `<section style="padding:24px;color:#e8edf5;"><h2>WMS · Detalle de Lote</h2><p style="color:#94a3b8;">Migración desde React (LoteDetallePage).</p><p><a routerLink="/logistics/wms/lotes" style="color:#43c6b0;">← Volver a Lotes</a></p></section>`
})
export class WmsLoteDetalleComponent {}
