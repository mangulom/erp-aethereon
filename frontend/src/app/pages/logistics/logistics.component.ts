import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-logistics',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="fin-workspace">
      <header class="fin-header">
        <div>
          <span class="panel-kicker">OPERACIONES</span>
          <h1 class="fin-title-main">Logística</h1>
          <p class="fin-subtitle-desc">Solicitudes de compra/servicio (bienes, suministros, contratos) que generan requerimientos de Certificado de Disponibilidad Presupuestal (CDP) en Presupuestos.</p>
        </div>
      </header>
      <div class="fin-panel">
        <h3>Solicitudes de CDP</h3>
        <p class="fin-hint">Desde Logística se registran necesidades; Presupuesto emite el CDP y luego se genera el Compromiso al aprobar la Orden de Compra/Servicio.</p>
        <a class="fin-primary fin-link-btn" routerLink="/budgets">Ir a Presupuestos (CDP)</a>
      </div>
    </section>
  `,
})
export class LogisticsComponent {}
