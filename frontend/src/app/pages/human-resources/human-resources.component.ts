import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-human-resources',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="fin-workspace">
      <header class="fin-header">
        <div>
          <span class="panel-kicker">PERSONAS</span>
          <h1 class="fin-title-main">Recursos Humanos</h1>
          <p class="fin-subtitle-desc">Solicitudes que pueden requerir Certificado de Disponibilidad Presupuestal (CDP) (ej. contrataciones, servicios, capacitaciones) gestionadas en Presupuestos.</p>
        </div>
      </header>
      <div class="fin-panel">
        <h3>Solicitudes de CDP</h3>
        <p class="fin-hint">RR.HH. solicita disponibilidad presupuestal; el área de Presupuesto emite el CDP y se continúa con compromiso y pagos según el flujo.</p>
        <a class="fin-primary fin-link-btn" routerLink="/budgets">Ir a Presupuestos (CDP)</a>
      </div>
    </section>
  `,
})
export class HumanResourcesComponent {}
