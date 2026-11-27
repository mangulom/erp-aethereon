import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { WmsTabsComponent } from './wms-tabs.component';

@Component({
  selector: 'app-wms-matpel',
  standalone: true,
  imports: [CommonModule, RouterLink, WmsTabsComponent],
  template: `
    <section class="fin-workspace" style="padding:24px;color:#e8edf5;">
      <header class="fin-header fin-header-advanced" style="margin-bottom:16px;">
        <div class="fin-header-main">
          <span class="panel-kicker">REGULATORIO · WMS</span>
          <h1 class="fin-title-main">MATPEL (Materiales Peligrosos)</h1>
          <p class="fin-subtitle-desc">Control y cumplimiento de almacenamiento de materiales peligrosos y hojas de seguridad.</p>
        </div>
      </header>
      <app-wms-tabs></app-wms-tabs>
      <div class="fin-panel">
        <p style="color:#94a3b8;">Módulo de gestión de materiales peligrosos (MATPEL). Visualización y control regulatorio activo.</p>
      </div>
    </section>
  `
})
export class WmsMatpelComponent {}
