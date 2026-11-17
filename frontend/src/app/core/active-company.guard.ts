import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { CompanyService } from './company.service';

export const activeCompanyGuard: CanActivateFn = (_route, state) => {
  const companies = inject(CompanyService);
  companies.loadCompanies();
  if (companies.hasActiveCompany) return true;
  return inject(Router).createUrlTree(['/dashboard'], { queryParams: { returnUrl: state.url, reason: 'no-company' } });
};
