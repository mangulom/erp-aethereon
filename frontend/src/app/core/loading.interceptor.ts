import { HttpInterceptorFn } from '@angular/common/http';
import { finalize } from 'rxjs';
import { inject } from '@angular/core';
import { LoadingService } from '../shared/loading.service';

export const loadingInterceptor: HttpInterceptorFn = (request, next) => {
  if (!request.url.startsWith('/api/') || request.url.includes('/health/')) return next(request);
  const loading = inject(LoadingService);
  const message = request.url.includes('/auth/login') ? 'VALIDANDO ACCESO' :
    request.url.includes('/documents') && request.method === 'POST' ? 'GUARDANDO COMPROBANTE' :
    request.url.includes('/reports/') ? 'GENERANDO INFORME FINANCIERO' :
    request.method === 'GET' ? 'CARGANDO INFORMACIÓN' : 'GUARDANDO CAMBIOS';
  const id = loading.show(message);
  return next(request).pipe(finalize(() => loading.hide(id)));
};
