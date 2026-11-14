import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  if (inject(AuthService).isAuthenticated) return true;
  return inject(Router).createUrlTree(['/login'], { queryParams: { redirect: state.url } });
};

export const platformAdminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  if (auth.isAuthenticated && auth.user()?.is_platform_admin === true) return true;
  return inject(Router).createUrlTree(['/dashboard']);
};
