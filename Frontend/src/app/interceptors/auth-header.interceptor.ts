import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';

export const authHeaderInterceptor: HttpInterceptorFn = (req, next) => {
  const user = inject(AuthService).getUser();
  if (user) {
    req = req.clone({
      setHeaders: {
        'X-User-Name':  user.name,
        'X-User-Email': user.email,
      },
    });
  }
  return next(req);
};
