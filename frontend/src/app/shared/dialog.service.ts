import { Injectable } from '@angular/core';
import Swal, { SweetAlertIcon, SweetAlertOptions } from 'sweetalert2';

export interface DialogOptions {
  title?: string;
  text?: string;
  confirmText?: string;
  cancelText?: string;
  icon?: SweetAlertIcon;
  danger?: boolean;
}

@Injectable({ providedIn: 'root' })
export class DialogService {
  private readonly base: SweetAlertOptions = {
    buttonsStyling: false,
    customClass: {
      popup: 'aethereon-dialog',
      title: 'aethereon-dialog-title',
      htmlContainer: 'aethereon-dialog-body',
      confirmButton: 'aethereon-dialog-confirm',
      cancelButton: 'aethereon-dialog-cancel',
      actions: 'aethereon-dialog-actions',
    },
    confirmButtonText: 'Aceptar',
    cancelButtonText: 'Cancelar',
    heightAuto: false,
    reverseButtons: true,
    focusCancel: true,
    showCloseButton: true,
    backdrop: 'rgba(4, 7, 18, .76)',
  };

  private readonly toastPopup = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3600,
    timerProgressBar: true,
    buttonsStyling: false,
    customClass: { popup: 'aethereon-toast' },
  });

  async confirm(options: DialogOptions): Promise<boolean> {
    const result = await Swal.fire({
      ...this.base,
      title: options.title ?? '¿Confirmas esta acción?',
      text: options.text,
      icon: options.icon ?? 'question',
      showCancelButton: true,
      confirmButtonText: options.confirmText ?? 'Confirmar',
      cancelButtonText: options.cancelText ?? 'Cancelar',
      customClass: {
        ...this.base.customClass,
        confirmButton: options.danger ? 'aethereon-dialog-confirm aethereon-dialog-danger' : 'aethereon-dialog-confirm',
      },
    });
    return result.isConfirmed;
  }

  async success(options: DialogOptions): Promise<void> { await this.message({...options, icon:options.icon??'success'}); }
  async error(options: DialogOptions): Promise<void> { await this.message({...options, icon:options.icon??'error'}); }
  async warning(options: DialogOptions): Promise<void> { await this.message({...options, icon:options.icon??'warning'}); }
  async info(options: DialogOptions): Promise<void> { await this.message({...options, icon:options.icon??'info'}); }

  toast(options: DialogOptions): void {
    void this.toastPopup.fire({title:options.title??options.text,icon:options.icon??'info'});
  }

  async apiError(error: unknown, fallback='Ocurrió un error inesperado.'): Promise<void> {
    const err=error as {error?:{detail?:unknown;message?:unknown};message?:unknown};
    const detail=err?.error?.detail??err?.error?.message??err?.message;
    await this.error({title:'No se pudo completar',text:this.stringifyError(detail)||fallback});
  }

  private async message(options:DialogOptions):Promise<void>{
    await Swal.fire({...this.base,title:options.title,text:options.text,icon:options.icon,confirmButtonText:options.confirmText??'Entendido',showCancelButton:false,focusConfirm:true});
  }

  private stringifyError(value:unknown):string{
    if(typeof value==='string')return value;
    if(Array.isArray(value))return value.map(item=>typeof item==='string'?item:`${Array.isArray(item?.loc)?item.loc.join(' → ')+': ':''}${item?.msg??item?.message??JSON.stringify(item)}`).join('\n');
    if(value&&typeof value==='object'){const record=value as {msg?:unknown;message?:unknown;detail?:unknown};return this.stringifyError(record.detail??record.msg??record.message??JSON.stringify(value));}
    return '';
  }
}
