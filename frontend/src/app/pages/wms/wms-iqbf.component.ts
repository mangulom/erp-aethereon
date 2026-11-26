import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-iqbf',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `<section style="padding:24px;color:#e8edf5;"><h2>WMS · IQBF</h2><p style="color:#94a3b8;">Migración desde React (IQBFPage). Pendiente.</p><p><a routerLink="/logistics/wms/matpel" style="color:#43c6b0;">← MATPEL</a></p></section>`
})
export class WmsIqbfComponent {}
