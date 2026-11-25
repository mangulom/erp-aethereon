import { Routes } from '@angular/router';
import { authGuard, platformAdminGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./pages/login/login.component').then((module) => module.LoginComponent) },
  {
    path: '', canActivate: [authGuard], children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      { path: 'dashboard', loadComponent: () => import('./pages/dashboard/dashboard.component').then((module) => module.DashboardComponent) },
      { path: 'inteligencia-ia', pathMatch: 'full', loadComponent: () => import('./pages/finance-ai/finance-ai.component').then((module) => module.FinanceAiComponent) },
      { path: 'finance', pathMatch: 'full', loadComponent: () => import('./pages/finance/finance.component').then((module) => module.FinanceComponent) },
      { path: 'accounting', pathMatch: 'full', loadComponent: () => import('./pages/accounting/accounting.component').then((module) => module.AccountingComponent) },
      { path: 'budgets', pathMatch: 'full', loadComponent: () => import('./pages/budgets/budgets.component').then((module) => module.BudgetsComponent) },
      { path: 'logistics', pathMatch: 'full', loadComponent: () => import('./pages/logistics/logistics.component').then((module) => module.LogisticsComponent) },
      { path: 'human-resources', pathMatch: 'full', loadComponent: () => import('./pages/human-resources/human-resources.component').then((module) => module.HumanResourcesComponent) },
      { path: 'administration', loadComponent: () => import('./pages/administration/administration.component').then((module) => module.AdministrationComponent) },
      { path: 'maintenance', pathMatch: 'full', redirectTo: 'maintenance/companies' },
      { path: 'maintenance/:section', canActivate: [platformAdminGuard], loadComponent: () => import('./pages/maintenance/maintenance.component').then((module) => module.MaintenanceComponent) },
      { path: 'modules', loadComponent: () => import('./pages/modules/modules.component').then((module) => module.ModulesComponent) },
      { path: 'settings', loadComponent: () => import('./pages/settings/settings.component').then((module) => module.SettingsComponent) },
      { path: '**', redirectTo: 'dashboard' },
    ],
  },
];
