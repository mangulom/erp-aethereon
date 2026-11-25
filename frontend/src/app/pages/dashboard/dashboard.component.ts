import { Component, inject, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { LanguageService } from '../../core/language.service';

interface IdentityHealth { status: string; service: string; version: string; }

interface MetricCard {
  label: string;
  labelEs: string;
  value: string;
  note: string;
  noteEs: string;
  icon: string;
  tone: 'violet' | 'blue' | 'teal' | 'amber';
  bars: number[];
}

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  template: `
    <section class="command-dashboard">
      <header class="command-heading">
        <div><div class="command-eyebrow"><span class="command-pulse"></span>{{ isSpanish ? 'INTELIGENCIA EMPRESARIAL · CENTRO DE CONTROL' : 'ENTERPRISE INTELLIGENCE · CONTROL ROOM' }}</div><h1>{{ isSpanish ? 'Resumen ejecutivo' : 'Executive overview' }}</h1><p>{{ isSpanish ? 'Visibilidad unificada de operaciones, finanzas y módulos de tu ERP.' : 'Unified visibility across operations, finance, and your modular ERP.' }}</p></div>
        <div class="command-heading-actions"><span class="command-range"><span>◷</span> {{ isSpanish ? 'Vista general' : 'Workspace overview' }} <b>⌄</b></span><a class="console-button" routerLink="/modules">{{ isSpanish ? 'Explorar módulos' : 'Explore modules' }} <span>↗</span></a></div>
      </header>

      <div class="executive-kpis">
        @for (metric of metrics; track metric.label) {
          <article class="executive-kpi" [class]="'executive-kpi tone-' + metric.tone">
            <div class="metric-top"><span>{{ isSpanish ? metric.labelEs : metric.label }}</span><span class="metric-icon">{{ metric.icon }}</span></div>
            <div class="metric-value">{{ metric.value }}</div>
            <div class="metric-foot"><span>{{ isSpanish ? metric.noteEs : metric.note }}</span><span class="metric-spark" aria-hidden="true">@for (height of metric.bars; track $index) { <i [style.height.%]="height"></i> }</span></div>
          </article>
        }
      </div>

      <div class="command-grid-main">
        <article class="console-panel routing-panel">
          <div class="console-panel-heading"><div><span class="panel-kicker">{{ isSpanish ? 'ORQUESTACIÓN INTELIGENTE' : 'INTELLIGENCE ROUTING' }}</span><h2>{{ isSpanish ? 'Centro de control de procesos' : 'Workflow command center' }}</h2><p>{{ isSpanish ? 'Estado de los servicios y preparación de los dominios' : 'AI orchestration status and domain readiness' }}</p></div><span class="mode-badge"><i></i> {{ isSpanish ? 'FUNDACIÓN' : 'FOUNDATIONS' }}</span></div>
          <div class="workflow-canvas">
            <div class="workflow-legend"><span><i class="legend-violet"></i> {{ isSpanish ? 'Operaciones' : 'Operations' }}</span><span><i class="legend-blue"></i> {{ isSpanish ? 'Finanzas y datos' : 'Finance & data' }}</span><span><i class="legend-teal"></i> {{ isSpanish ? 'Capa inteligente' : 'Intelligence layer' }}</span></div>
            <div class="workflow-stages">
              @for (stage of workflowStages; track stage.name; let index = $index) {
                <div class="workflow-stage"><span class="stage-index">0{{ index + 1 }}</span><span class="stage-orbit"><span class="stage-icon">{{ stage.icon }}</span><span class="orbit-dot"></span></span><b>{{ stage.name }}</b><small>{{ stage.detail }}</small><span class="stage-caption">{{ stage.state }}</span></div>
                @if (index < workflowStages.length - 1) { <span class="workflow-connector"><i></i><i></i><i></i></span> }
              }
            </div>
            <div class="workflow-readiness"><div><span class="readiness-icon">✳</span><div><b>{{ isSpanish ? 'Base de la plataforma' : 'ERP foundation' }}</b><small>{{ isSpanish ? 'Identidad activa · PostgreSQL conectado · sin datos empresariales de muestra' : 'Identity online · PostgreSQL connected · no business data seeded' }}</small></div></div><span class="readiness-value">{{ isSpanish ? 'LISTO' : 'READY' }}</span></div>
          </div>
          <footer class="routing-footer"><span><i class="legend-violet"></i> {{ isSpanish ? 'MÓDULOS' : 'DOMAIN MODULES' }} <b>22</b></span><span><i class="legend-blue"></i> {{ isSpanish ? 'SERVICIOS ACTIVOS' : 'ACTIVE SERVICES' }} <b>1 / 22</b></span><span><i class="legend-teal"></i> {{ isSpanish ? 'DATOS DE MUESTRA' : 'SAMPLE DATA' }} <b>{{ isSpanish ? 'DESACTIVADOS' : 'DISABLED' }}</b></span><a routerLink="/modules">{{ isSpanish ? 'Ver módulos' : 'View module map' }} ↗</a></footer>
        </article>

        <article class="console-panel approval-panel">
          <div class="console-panel-heading compact"><div><span class="panel-kicker">{{ isSpanish ? 'GOBERNANZA' : 'GOVERNANCE' }}</span><h2>{{ isSpanish ? 'Cola de aprobaciones' : 'Approval queue' }}</h2><p>{{ isSpanish ? 'Controles con revisión humana' : 'Human-in-the-loop controls' }}</p></div><span class="queue-count">0 <small>{{ isSpanish ? 'pendientes' : 'pending' }}</small></span></div>
          <div class="approval-empty"><span class="empty-orb">✓</span><b>{{ isSpanish ? 'No hay aprobaciones pendientes' : 'No approvals to review' }}</b><p>{{ isSpanish ? 'Las acciones sensibles aparecerán aquí y requerirán revisión autorizada.' : 'Sensitive ERP actions will appear here and require authorized review.' }}</p></div>
          <a class="panel-footer-link" routerLink="/modules">{{ isSpanish ? 'Explorar procesos' : 'Explore workflows' }} <span>→</span></a>
        </article>
      </div>

      <div class="command-grid-bottom">
        <article class="console-panel health-panel"><div class="console-panel-heading compact"><div><span class="panel-kicker">{{ isSpanish ? 'SALUD DE LA PLATAFORMA' : 'PLATFORM HEALTH' }}</span><h2>{{ isSpanish ? 'Estado del sistema' : 'System status' }}</h2><p>{{ isSpanish ? 'Servicios locales en vivo' : 'Live local services' }}</p></div><span class="health-live"><i></i> {{ isSpanish ? 'EN VIVO' : 'LIVE' }}</span></div>
          <div class="health-rows"><div class="health-row"><span class="health-mark mark-shell">⌂</span><div><b>ERP shell</b><small>{{ isSpanish ? 'Frontend Angular' : 'Angular frontend' }} · :4200</small></div><span class="healthy-state"><i></i> {{ isSpanish ? 'EN LÍNEA' : 'ONLINE' }}</span></div><div class="health-row"><span class="health-mark mark-api">⌘</span><div><b>{{ isSpanish ? 'Servicio de identidad' : 'Identity service' }}</b><small>FastAPI · :{{ identityPort }}</small></div>@if (identityStatus === 'online') { <span class="healthy-state"><i></i> {{ isSpanish ? 'EN LÍNEA' : 'ONLINE' }}</span> } @else { <span class="waiting-state"><i></i> {{ isSpanish ? 'REVISAR' : 'CHECK' }}</span> }</div><div class="health-row"><span class="health-mark mark-db">▤</span><div><b>PostgreSQL</b><small>{{ isSpanish ? 'Base multiempresa' : 'Multi-company foundation' }} · :15432</small></div><span class="healthy-state"><i></i> {{ isSpanish ? 'LISTO' : 'READY' }}</span></div></div>
        </article>
        <article class="console-panel finance-panel"><div class="console-panel-heading compact"><div><span class="panel-kicker">{{ isSpanish ? 'FINANZAS Y OPERACIONES' : 'FINANCE & OPERATIONS' }}</span><h2>{{ isSpanish ? 'Indicadores ejecutivos' : 'Executive KPIs' }}</h2><p>{{ isSpanish ? 'Los datos reales aparecerán al activar los módulos' : 'Real data will populate after module activation' }}</p></div><span class="cycle-tag">{{ isSpanish ? 'CONFIGURACIÓN INICIAL' : 'INITIAL SETUP' }}</span></div><div class="finance-empty"><div class="finance-chart-placeholder"><div class="chart-axis"><span>100%</span><span>75%</span><span>50%</span><span>25%</span></div><div class="chart-grid-lines"><i></i><i></i><i></i><i></i><div class="chart-wave-placeholder"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div></div><div class="chart-months"><span>{{ isSpanish ? 'S1' : 'W1' }}</span><span>{{ isSpanish ? 'S2' : 'W2' }}</span><span>{{ isSpanish ? 'S3' : 'W3' }}</span><span>{{ isSpanish ? 'S4' : 'W4' }}</span><span>{{ isSpanish ? 'S5' : 'W5' }}</span><span>{{ isSpanish ? 'S6' : 'W6' }}</span><span>{{ isSpanish ? 'S7' : 'W7' }}</span><span>{{ isSpanish ? 'S8' : 'W8' }}</span></div></div><div class="finance-summary"><span>{{ isSpanish ? 'INGRESOS' : 'REVENUE' }}</span><b>—</b><small>{{ isSpanish ? 'Activa Ventas para comenzar' : 'Connect Sales to begin' }}</small><span>{{ isSpanish ? 'MARGEN NETO' : 'NET MARGIN' }}</span><b>—</b><small>{{ isSpanish ? 'Requiere datos financieros' : 'Requires finance data' }}</small></div></div><div class="finance-footnote"><span class="safe-note">◉ {{ isSpanish ? 'Sin indicadores sintéticos' : 'No synthetic KPIs' }}</span><span>{{ isSpanish ? 'Fuente: registros reales del negocio' : 'Source: live business records only' }}</span></div></article>
        <article class="console-panel activity-console"><div class="console-panel-heading compact"><div><span class="panel-kicker">{{ isSpanish ? 'MONITOR DE EVENTOS' : 'EVENT MONITOR' }}</span><h2>{{ isSpanish ? 'Actividad y alertas' : 'Activity & alerts' }}</h2><p>{{ isSpanish ? 'Eventos confiables y auditables' : 'Trusted, audited system events' }}</p></div><span class="activity-dot">●</span></div><div class="activity-empty"><div class="activity-symbol">◎</div><b>{{ isSpanish ? 'Todo tranquilo por ahora' : 'All quiet for now' }}</b><p>{{ isSpanish ? 'Todavía no hay eventos de procesos ni alertas operativas.' : 'There are no workflow events or operational alerts yet.' }}</p></div><a class="panel-footer-link" routerLink="/settings">{{ isSpanish ? 'Abrir configuración de gobierno' : 'Open governance settings' }} <span>→</span></a></article>
      </div>

      <footer class="command-bottomline"><span>SOPHIA <b>ERP</b> <i>·</i> {{ isSpanish ? 'CENTRO DE CONTROL' : 'COMMAND CENTER' }}</span><span>{{ isSpanish ? 'DESARROLLO LOCAL' : 'LOCAL DEVELOPMENT' }} <i>·</i> POSTGRESQL <i>·</i> {{ isSpanish ? 'DATOS DEMO DESACTIVADOS' : 'DEMO RECORDS DISABLED' }}</span></footer>
    </section>
  `,
})
export class DashboardComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly languageService = inject(LanguageService);
  identityStatus: 'online' | 'checking' = 'checking';
  readonly identityPort = '18001';
  readonly metrics: MetricCard[] = [
    { label: 'MODULES PLANNED', labelEs: 'MÓDULOS PLANIFICADOS', value: '22', note: 'Across 6 business domains', noteEs: 'En 6 dominios empresariales', icon: '▧', tone: 'violet', bars: [38, 56, 44, 70, 62, 88, 75, 100] },
    { label: 'API SERVICES ONLINE', labelEs: 'SERVICIOS API EN LÍNEA', value: '1 / 22', note: 'Identity · development ready', noteEs: 'Identidad · lista en desarrollo', icon: '⌘', tone: 'blue', bars: [45, 42, 56, 50, 69, 66, 81, 100] },
    { label: 'BUSINESS ENTITIES', labelEs: 'EMPRESAS REGISTRADAS', value: '—', note: 'Awaiting first company setup', noteEs: 'Pendiente de configurar la primera empresa', icon: '⌂', tone: 'teal', bars: [30, 45, 36, 59, 52, 74, 68, 90] },
    { label: 'WORKFLOW APPROVALS', labelEs: 'APROBACIONES PENDIENTES', value: '0', note: 'Human approval controls enabled', noteEs: 'Controles de revisión humana activos', icon: '✓', tone: 'amber', bars: [54, 39, 61, 47, 74, 56, 84, 68] },
  ];
  readonly workflowStages = [
    { name: 'Capture', detail: 'Enterprise events', state: 'DOMAIN READY', icon: '⌕' },
    { name: 'Orchestrate', detail: 'Service contracts', state: 'API FIRST', icon: '⌘' },
    { name: 'Authorize', detail: 'Review controls', state: 'GUARDED', icon: '⛨' },
    { name: 'Execute', detail: 'Business modules', state: 'PHASED ROLLOUT', icon: '✳' },
  ];

  get isSpanish(): boolean { return this.languageService.language() === 'es'; }

  ngOnInit(): void {
    this.http.get<IdentityHealth>('/health/live').subscribe({
      next: (health) => {
        this.identityStatus = health.status === 'ok' ? 'online' : 'checking';
      },
      error: () => { this.identityStatus = 'checking'; },
    });
  }

}
