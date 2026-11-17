import { Injectable, computed, signal } from '@angular/core';

interface LoadingTask { id:number; message:string; }

@Injectable({providedIn:'root'})
export class LoadingService {
  private nextId=1;
  private readonly tasks=signal<LoadingTask[]>([]);
  readonly active=computed(()=>this.tasks().length>0);
  readonly message=computed(()=>this.tasks().at(-1)?.message??'CARGANDO');
  show(message='CARGANDO'):number{const id=this.nextId++;this.tasks.update(items=>[...items,{id,message:this.normalize(message)}]);return id;}
  hide(id?:number):void{this.tasks.update(items=>id===undefined?items.slice(0,-1):items.filter(item=>item.id!==id));}
  clear():void{this.tasks.set([]);}
  async track<T>(message:string,operation:Promise<T>):Promise<T>{const id=this.show(message);try{return await operation;}finally{this.hide(id);}}
  private normalize(message:string):string{return message.trim().toLocaleUpperCase('es')||'CARGANDO';}
}
