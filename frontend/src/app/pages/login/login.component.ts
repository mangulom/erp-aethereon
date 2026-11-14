import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  template: `
    <main class="login-page">
      <section class="login-brand-panel">
        <div class="login-grid"></div>
        <div class="brand-top"><div class="brand-mark"><svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><path d="M24 3.5 42 14v20L24 44.5 6 34V14L24 3.5Z" stroke="currentColor" stroke-width="2"/><path d="M15 28.5 23 16l5.5 8 4.5-6 4 6.5M15 33h22" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/><circle cx="34" cy="12" r="3" fill="#4bd3bb"/></svg></div><span class="wordmark">AETHEREON<span>ERP</span></span></div>
        <div class="brand-copy"><span class="eyebrow"><i></i> INTELIGENCIA EMPRESARIAL, EN UN SOLO LUGAR</span><h1 class="login-hero-title">Todo tu negocio.<br/><em>Una visión</em><br/>más inteligente.</h1><p>Conecta procesos, equipos y decisiones en una plataforma empresarial diseñada para crecer contigo.</p>
          <div class="brand-points"><div><span class="point-icon">⌘</span><span><b>Un ecosistema conectado</b><small>Procesos alineados, de punta a punta.</small></span></div><div><span class="point-icon">✳</span><span><b>Inteligencia en cada módulo</b><small>Datos claros para mejores decisiones.</small></span></div></div>
        </div>
        <div class="brand-footer"><span>PERÚ · PLATAFORMA MULTIEMPRESA</span><span>© 2026 Aethereon</span></div>
      </section>
      <section class="login-content">
        <div class="login-card-wrap"><div class="mobile-brand"><div class="brand-mark"><svg viewBox="0 0 48 48" fill="none"><path d="M24 3.5 42 14v20L24 44.5 6 34V14L24 3.5Z" stroke="currentColor" stroke-width="2"/><path d="m15 29 8-13 5.5 8 4.5-6 4 7M15 33h22" stroke="currentColor" stroke-width="2"/></svg></div><span class="wordmark">AETHEREON<span>ERP</span></span></div>
           <div class="welcome-label"><span class="status-pulse"></span> ESPACIO DE TRABAJO EMPRESARIAL</div>
           <h2>Bienvenido de vuelta</h2><p class="login-subtitle">Ingresa tus credenciales para continuar.</p>
           <div class="demo-access" role="note" aria-label="Credenciales demo temporales"><div class="demo-access-heading"><span class="demo-indicator"></span><span>ACCESO DEMO TEMPORAL · DESARROLLO</span><span class="demo-until">SOLO LOCAL</span></div><div class="demo-credentials"><div><span>USUARIO</span><strong>admin&#64;aethereon.pe</strong></div><div><span>CONTRASEÑA</span><strong class="demo-password">admin123!</strong></div></div><p>Retirar esta cuenta antes de publicar en producción.</p></div><form (ngSubmit)="submit()" #form="ngForm" class="login-form">
            <label for="email">Correo electrónico</label><div class="input-shell"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m4 7 8 6 8-6"/></svg><input id="email" name="email" type="email" autocomplete="username" [(ngModel)]="email" placeholder="nombre@empresa.com" required /></div>
            <div class="password-label"><label for="password">Contraseña</label><a href="mailto:soporte&#64;aethereon.pe?subject=Recuperar%20acceso">¿Olvidaste tu contraseña?</a></div><div class="input-shell"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="4" y="10" width="16" height="11" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/></svg><input id="password" name="password" [type]="showPassword() ? 'text' : 'password'" autocomplete="current-password" [(ngModel)]="password" placeholder="Ingresa tu contraseña" required/><button type="button" class="reveal-button" (click)="showPassword.set(!showPassword())" [attr.aria-label]="showPassword() ? 'Ocultar contraseña' : 'Mostrar contraseña'">{{ showPassword() ? 'Ocultar' : 'Mostrar' }}</button></div>
            @if (error()) {<div class="error-message" role="alert">{{ error() }}</div>}
            <button class="login-button" type="submit" [disabled]="loading() || !form.valid"><span>{{ loading() ? 'Verificando acceso…' : 'Iniciar sesión' }}</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></button>
          </form>
          <div class="secure-note"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3 20 6v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-3Z"/><path d="m9 12 2 2 4-4"/></svg><span>Conexión cifrada y acceso protegido</span></div>
        </div><div class="login-bottom"><span>¿Necesitas ayuda? <a href="mailto:soporte&#64;aethereon.pe">Contactar soporte</a></span><span>Privacidad &nbsp;Â·&nbsp; Seguridad</span></div>
      </section>
    </main>
  `,
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  email = '';
  password = '';
  readonly loading = signal(false);
  readonly showPassword = signal(false);
  readonly error = signal<string | null>(null);

  submit(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set(null);
    this.auth.login(this.email.trim(), this.password).subscribe({
      next: () => {
        const redirect = this.route.snapshot.queryParamMap.get('redirect') || '/dashboard';
        void this.router.navigateByUrl(redirect);
      },
      error: (response) => {
        this.loading.set(false);
        this.error.set(response?.error?.detail || 'No se pudo validar el acceso. Comprueba tus datos e intÃ©ntalo de nuevo.');
      },
    });
  }
}
