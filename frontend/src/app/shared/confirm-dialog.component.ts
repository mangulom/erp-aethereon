import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (open) {
      <div style="position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;" (click)="onCancel()">
        <div style="background:#1a1d2e;border:1px solid #333;border-radius:8px;padding:20px;max-width:400px;width:90%;" (click)="$event.stopPropagation()">
          <h3 style="margin:0 0 12px;color:#fff;font-size:16px;">{{ title }}</h3>
          <p style="margin:0 0 20px;color:#ccc;font-size:14px;">{{ message }}</p>
          <div style="display:flex;gap:8px;justify-content:flex-end;">
            <button type="button" (click)="onCancel()" style="padding:8px 16px;border:1px solid #555;background:transparent;color:#ccc;border-radius:4px;cursor:pointer;">{{ cancelText }}</button>
            <button type="button" (click)="onConfirm()" style="padding:8px 16px;border:none;background:#a78bfa;color:#fff;border-radius:4px;cursor:pointer;">{{ confirmText }}</button>
          </div>
        </div>
      </div>
    }
  `
})
export class ConfirmDialogComponent {
  @Input() open = false;
  @Input() title = 'Confirmar';
  @Input() message = '¿Estás seguro?';
  @Input() confirmText = 'Confirmar';
  @Input() cancelText = 'Cancelar';
  @Output() confirm = new EventEmitter<void>();
  @Output() cancel = new EventEmitter<void>();

  onConfirm() { this.confirm.emit(); }
  onCancel() { this.cancel.emit(); }
}
