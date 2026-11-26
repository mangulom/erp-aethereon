import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-monitoreo',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `<section style="padding:24px;color:#e8edf5;"><h2>WMS · Monitoreo</h2><p style="color:#94a3b8;">Migración desde React (MonitoreoPage / Grafana embebido). Pendiente.</p><p><a routerLink="/logistics/wms" style="color:#43c6b0;">← WMS Panel</a></p></section>`
})
export class WmsMonitoreoComponent {}
