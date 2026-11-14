import { Component } from '@angular/core';
import { LanguageService } from '../../core/language.service';

@Component({ selector: 'app-settings', template: `
  <div class="dashboard-page"><div class="dashboard-topline"><div><span class="breadcrumb">{{ isSpanish ? 'PLATAFORMA' : 'PLATFORM' }} <span>›</span> {{ isSpanish ? 'CONFIGURACIÓN' : 'SETTINGS' }}</span><h1>{{ isSpanish ? 'Administración' : 'Administration' }}</h1><p class="page-subtitle">{{ isSpanish ? 'Gobierno de la plataforma y base técnica del espacio empresarial.' : 'Platform governance and workspace technical foundations.' }}</p></div></div>
    <div class="settings-grid"><article class="settings-card"><span class="settings-icon">⌘</span><span class="section-kicker">IDENTIDAD</span><h2>Servicio de identidad</h2><p>Autenticación centralizada, JWT, roles y espacios empresariales.</p><div class="settings-status"><i></i> Servicio local · puerto 10001</div></article><article class="settings-card"><span class="settings-icon">▤</span><span class="section-kicker">PERSISTENCIA</span><h2>PostgreSQL</h2><p>Esquema inicial para empresas, usuarios, membresías, permisos y bitácora.</p><div class="settings-status settings-pending"><i></i> Requiere DATABASE_URL local</div></article><article class="settings-card"><span class="settings-icon">▦</span><span class="section-kicker">MICROFRONTENDS</span><h2>Catálogo de módulos</h2><p>Mapa versionado de rutas, puertos de desarrollo y estado de cada dominio.</p><div class="settings-status"><i></i> Catálogo disponible en el shell</div></article><article class="settings-card"><span class="settings-icon">⛨</span><span class="section-kicker">SEGURIDAD</span><h2>Control de acceso</h2><p>Roles y permisos por empresa, acciones protegidas y auditoría.</p><div class="settings-status settings-pending"><i></i> Lista para configurar</div></article></div>
    <div class="notice-card"><b>{{ isSpanish ? 'Credenciales demo temporales' : 'Temporary demo credentials' }}</b><p>{{ isSpanish ? 'La cuenta demo es solo para desarrollo. Rótala y retira las credenciales visibles antes de desplegar en producción.' : 'The demo account is for development only. Rotate it and remove visible credentials before deploying to production.' }}</p></div>
  </div>
` })
export class SettingsComponent {
  constructor(readonly languageService: LanguageService) {}
  get isSpanish(): boolean { return this.languageService.language() === 'es'; }
}
