import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-wms-recepciones-flujo',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `<section style="padding:24px;color:#e8edf5;"><h2>WMS · Recepciones (flujo)</h2><p style="color:#94a3b8;">Migración desde React (RecepcionFlujoPage, wizard 6 pasos). Pendiente de portar lógica completa.</p><p><a routerLink="/logistics/wms/recepciones" style="color:#43c6b0;">← Recepciones</a></p></section>`
})
export class WmsRecepcionesFlujoComponent {}
