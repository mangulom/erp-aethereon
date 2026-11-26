import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-predicciones',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `<section style="padding:24px;color:#e8edf5;"><h2>WMS · Predicciones (IA)</h2><p style="color:#94a3b8;">Migración desde React (PrediccionesPage). Pendiente.</p><p><a routerLink="/logistics/wms/ia" style="color:#43c6b0;">← Motor IA</a></p></section>`
})
export class WmsPrediccionesComponent {}
