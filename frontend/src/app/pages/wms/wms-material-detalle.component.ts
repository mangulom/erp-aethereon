import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-material-detalle',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `<section style="padding:24px;color:#e8edf5;"><h2>WMS · Detalle de Material/Ítem</h2><p style="color:#94a3b8;">Pantalla en migración desde React (MaterialDetallePage). Mostrará ficha, stock por ubicación, lotes y subítems (Tablas/Insumos) según modelo wms.*.</p><p><a routerLink="/logistics/wms/materiales" style="color:#43c6b0;">← Volver a Ítems</a></p></section>`
})
export class WmsMaterialDetalleComponent {}
