import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-sap-transacciones',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `<section style="padding:24px;color:#e8edf5;"><h2>WMS · Transacciones SAP</h2><p style="color:#94a3b8;">Migración desde React (SapTransaccionesPage). Pendiente.</p><p><a routerLink="/logistics/wms/sap" style="color:#43c6b0;">← Integración SAP</a></p></section>`
})
export class WmsSapTransaccionesComponent {}
