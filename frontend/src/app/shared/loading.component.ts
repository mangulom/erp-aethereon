import { Component, inject } from '@angular/core';
import { LoadingService } from './loading.service';

@Component({
  selector:'app-loading',
  standalone:true,
  template:`
    @if(loading.active()){
      <div class="aethereon-loading-backdrop" role="status" aria-live="assertive" aria-atomic="true">
        <section class="aethereon-loading-card">
          <div class="aethereon-loading-orbit" aria-hidden="true">
            <span class="orbit-ring ring-a"></span><span class="orbit-ring ring-b"></span><span class="orbit-ring ring-c"></span>
            <div class="aethereon-loading-core"><svg viewBox="0 0 48 48" fill="none"><path d="M24 3.5 42 14v20L24 44.5 6 34V14L24 3.5Z" stroke="currentColor" stroke-width="2"/><path d="M15 28.5 23 16l5.5 8 4.5-6 4 6.5M15 33h22" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/><circle cx="34" cy="12" r="3" fill="#55d4bd"/></svg></div>
            <i class="orbit-dot dot-a"></i><i class="orbit-dot dot-b"></i><i class="orbit-dot dot-c"></i>
          </div>
          <p class="aethereon-loading-message">{{loading.message()}}</p>
          <div class="aethereon-loading-progress" aria-hidden="true"><span></span></div>
          <span class="aethereon-loading-caption">AETHEREON · ERP</span>
        </section>
      </div>
    }
  `,
})
export class LoadingComponent { readonly loading=inject(LoadingService); }
