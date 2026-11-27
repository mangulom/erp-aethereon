import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { LanguageService } from '../../core/language.service';

@Component({
  selector: 'app-wms-tabs',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  template: `
    <nav class="fin-tabs wms-nav-tabs" aria-label="Navegación WMS">
      <div class="wms-tabs-cluster">
        <span class="wms-cluster-tag">OPERACIONES</span>
        <a class="fin-tab-btn" routerLink="/logistics/wms/materiales" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
          <span>{{ t('Materiales', 'Materials') }}</span>
        </a>
        <a class="fin-tab-btn" routerLink="/logistics/wms/inventario" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/><line x1="9" y1="9" x2="9" y2="9.01"/><line x1="9" y1="13" x2="9" y2="13.01"/><line x1="9" y1="17" x2="9" y2="17.01"/></svg>
          <span>{{ t('Inventario', 'Inventory') }}</span>
        </a>
        <a class="fin-tab-btn" routerLink="/logistics/wms/lotes" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
          <span>{{ t('Lotes', 'Lots') }}</span>
        </a>
        <a class="fin-tab-btn" routerLink="/logistics/wms/recepciones" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/></svg>
          <span>{{ t('Recepciones', 'Receipts') }}</span>
        </a>
        <a class="fin-tab-btn" routerLink="/logistics/wms/despachos" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/></svg>
          <span>{{ t('Despachos', 'Dispatches') }}</span>
        </a>
      </div>

      <div class="wms-tabs-cluster">
        <span class="wms-cluster-tag">REGULATORIO</span>
        <a class="fin-tab-btn" routerLink="/logistics/wms/matpel" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <span>{{ t('MATPEL', 'HAZMAT') }}</span>
        </a>
        <a class="fin-tab-btn" routerLink="/logistics/wms/matpel/iqbf" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          <span>{{ t('IQBF SUNAT', 'IQBF SUNAT') }}</span>
        </a>
      </div>

      <div class="wms-tabs-cluster">
        <span class="wms-cluster-tag">INTEGRACIÓN</span>
        <a class="fin-tab-btn" routerLink="/logistics/wms/sap" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
          <span>{{ t('SAP Monitor', 'SAP Monitor') }}</span>
        </a>
        <a class="fin-tab-btn" routerLink="/logistics/wms/ia" routerLinkActive="active">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8.01" y2="16"/><line x1="16" y1="16" x2="16.01" y2="16"/></svg>
          <span>{{ t('Motor IA', 'AI Engine') }}</span>
        </a>
      </div>
    </nav>
  `,
  styles: [`
    .wms-nav-tabs {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;
      padding: 6px 12px;
      border: 1px solid #282d42;
      border-radius: 8px;
      background: #101321;
    }
    .wms-tabs-cluster {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 4px;
      padding-right: 10px;
      border-right: 1px solid rgba(255,255,255,0.08);
    }
    .wms-tabs-cluster:last-child {
      border-right: none;
      padding-right: 0;
    }
    .wms-cluster-tag {
      font-size: 8px;
      font-weight: 800;
      letter-spacing: .12em;
      color: #64748b;
      margin-right: 4px;
      user-select: none;
    }
    .fin-tab-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: #9da4bb;
      font-size: 11px;
      font-weight: 600;
      text-decoration: none;
      transition: all .15s ease;
      cursor: pointer;
    }
    .fin-tab-btn:hover {
      background: rgba(255,255,255,0.06);
      color: #f1edff;
    }
    .fin-tab-btn.active {
      border-color: var(--theme-accent, #7058a2);
      background: linear-gradient(110deg, rgba(67, 198, 176, 0.22), rgba(40, 35, 62, 0.6));
      color: #fff;
    }
    .fin-tab-btn.active svg {
      color: var(--theme-accent, #43c6b0);
    }
    @media (max-width: 900px) {
      .wms-tabs-cluster {
        border-right: none;
        padding-right: 0;
        width: 100%;
        margin-bottom: 6px;
      }
    }
  `]
})
export class WmsTabsComponent {
  private readonly lang = inject(LanguageService);
  t(es: string, en: string): string {
    return this.lang.text(es, en);
  }
}
