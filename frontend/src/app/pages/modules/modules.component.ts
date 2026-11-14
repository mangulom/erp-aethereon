import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LanguageService } from '../../core/language.service';

interface ModuleCard { code: string; name: string; group: string; description: string; icon: string; route: string; status: string; }

@Component({
  selector: 'app-modules',
  imports: [RouterLink],
  template: `
    <div class="modules-page"><div class="dashboard-topline"><div><span class="breadcrumb">{{ isSpanish ? 'PLATAFORMA' : 'PLATFORM' }} <span>›</span> {{ isSpanish ? 'MÓDULOS' : 'MODULES' }}</span><h1>{{ isSpanish ? 'Espacio de módulos' : 'Module workspace' }}</h1><p class="page-subtitle">{{ isSpanish ? 'Una plataforma integral, organizada en dominios empresariales.' : 'One integrated platform, organized by business domain.' }}</p></div><a routerLink="/dashboard" class="outline-button">← <span>{{ isSpanish ? 'Volver al inicio' : 'Back to overview' }}</span></a></div>
      <div class="module-intro"><div><span class="welcome-chip"><i></i> {{ isSpanish ? 'ARQUITECTURA MODULAR' : 'MODULAR ARCHITECTURE' }}</span><h2>{{ isSpanish ? 'Tu ERP. A tu ritmo.' : 'Your ERP. At your pace.' }}</h2><p>{{ isSpanish ? 'Explora el mapa funcional de Aethereon. Los módulos se incorporarán por etapas, manteniendo datos y servicios independientes.' : 'Explore the Aethereon functional map. Modules will roll out in phases with independently owned data and services.' }}</p></div><div class="intro-count"><b>22</b><span>{{ isSpanish ? 'dominios planificados' : 'planned domains' }}</span></div></div>
      @for (group of groups; track group.name) {<section class="module-section"><div class="module-section-title"><div><span class="section-kicker">{{ group.kicker }}</span><h2>{{ group.name }}</h2></div><span>{{ group.modules.length }} dominios</span></div><div class="module-cards">@for (module of group.modules; track module.code) {<article class="module-card"><span class="module-card-icon">{{ module.icon }}</span><div class="module-card-copy"><h3>{{ module.name }}</h3><p>{{ module.description }}</p></div><div class="module-card-foot"><code>{{ module.route }}</code><span class="planned-pill"><i></i>{{ module.status }}</span></div></article>}</div></section> }
    </div>
  `,
})
export class ModulesComponent {
  constructor(readonly languageService: LanguageService) {}
  get isSpanish(): boolean { return this.languageService.language() === 'es'; }
  readonly groups = [
    { name: 'Gestión financiera', kicker: 'FINANZAS Y CONTROL', modules: [
      { code: 'finance', name: 'Finanzas y tesorería', group: 'Gestión financiera', description: 'Caja, bancos, liquidez, cuentas por cobrar y pagar.', icon: '◈', route: '/finance', status: 'Planeado' },
      { code: 'accounting', name: 'Contabilidad y tributación', group: 'Gestión financiera', description: 'Contabilidad, cierres, activos y obligaciones tributarias.', icon: '▤', route: '/accounting', status: 'Planeado' },
    ]},
    { name: 'Operaciones', kicker: 'CLIENTES Y CADENA DE SUMINISTRO', modules: [
      { code: 'sales', name: 'Ventas y CRM', group: 'Operaciones', description: 'Clientes, oportunidades, cotizaciones y pedidos.', icon: '↗', route: '/sales', status: 'Planeado' },
      { code: 'procurement', name: 'Compras y proveedores', group: 'Operaciones', description: 'Abastecimiento, compras y gestión de proveedores.', icon: '⇄', route: '/procurement', status: 'Planeado' },
      { code: 'inventory', name: 'Inventarios y almacenes', group: 'Operaciones', description: 'Stock, ubicaciones y trazabilidad.', icon: '▦', route: '/inventory', status: 'Planeado' },
      { code: 'logistics', name: 'Logística y distribución', group: 'Operaciones', description: 'Despachos, rutas, flotas y entregas.', icon: '⌑', route: '/logistics', status: 'Planeado' },
    ]},
    { name: 'Personas y planta', kicker: 'TALENTO Y OPERACIÓN', modules: [
      { code: 'people', name: 'Recursos humanos', group: 'Personas y planta', description: 'Talento, expedientes, asistencia y desarrollo.', icon: '♙', route: '/people', status: 'Planeado' },
      { code: 'payroll', name: 'Nómina peruana', group: 'Personas y planta', description: 'Planilla y normativa laboral peruana.', icon: '≡', route: '/payroll', status: 'Planeado' },
      { code: 'manufacturing', name: 'Producción y MRP', group: 'Personas y planta', description: 'Planificación, órdenes y capacidad de planta.', icon: '⚙', route: '/manufacturing', status: 'Planeado' },
      { code: 'projects', name: 'Proyectos', group: 'Personas y planta', description: 'Portafolios, cronogramas, recursos y costos.', icon: '◫', route: '/projects', status: 'Planeado' },
      { code: 'maintenance', name: 'Mantenimiento y activos', group: 'Personas y planta', description: 'Activos, mantenimiento preventivo y predictivo.', icon: '⌘', route: '/maintenance', status: 'Planeado' },
    ]},
    { name: 'Gobierno y soporte', kicker: 'CONTROL Y SERVICIO', modules: [
      { code: 'quality', name: 'Calidad', group: 'Gobierno y soporte', description: 'Inspecciones, auditorías y mejora continua.', icon: '✓', route: '/quality', status: 'Planeado' },
      { code: 'safety', name: 'Seguridad y riesgos', group: 'Gobierno y soporte', description: 'Seguridad laboral, incidentes y matrices de riesgo.', icon: '⛨', route: '/safety', status: 'Planeado' },
      { code: 'legal', name: 'Legal y cumplimiento', group: 'Gobierno y soporte', description: 'Contratos, obligaciones y cumplimiento.', icon: '§', route: '/legal', status: 'Planeado' },
      { code: 'documents', name: 'Gestión documental', group: 'Gobierno y soporte', description: 'Expedientes, versiones y aprobaciones.', icon: '▤', route: '/documents', status: 'Planeado' },
      { code: 'support', name: 'Atención al cliente', group: 'Gobierno y soporte', description: 'Casos, soporte posventa y acuerdos de servicio.', icon: '☏', route: '/support', status: 'Planeado' },
      { code: 'administration', name: 'Administración', group: 'Gobierno y soporte', description: 'Empresas, usuarios, roles y configuración.', icon: '⚙', route: '/settings', status: 'En desarrollo' },
    ]},
    { name: 'Inteligencia', kicker: 'ANÁLISIS Y AUTOMATIZACIÓN', modules: [
      { code: 'ai-command', name: 'AI Command Center', group: 'Inteligencia', description: 'Agentes con permisos, supervisión y auditoría.', icon: '✳', route: '/ai', status: 'Planeado' },
      { code: 'analytics', name: 'Business Intelligence', group: 'Inteligencia', description: 'Indicadores, analítica y escenarios empresariales.', icon: '▥', route: '/analytics', status: 'Planeado' },
    ]},
    { name: 'Canales digitales', kicker: 'VENTA Y CRECIMIENTO', modules: [
      { code: 'commerce', name: 'Comercio electrónico y POS', group: 'Canales digitales', description: 'Ventas online, catálogo y puntos de venta.', icon: '⌑', route: '/commerce', status: 'Planeado' },
      { code: 'innovation', name: 'Innovación e I+D+i', group: 'Canales digitales', description: 'Ideas, prototipos, iniciativas y conocimiento.', icon: '✧', route: '/innovation', status: 'Planeado' },
    ]},
  ];
}
