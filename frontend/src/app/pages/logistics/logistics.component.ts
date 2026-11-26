import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LanguageService } from '../../core/language.service';
import { CompanyService } from '../../core/company.service';

type WmsSection = 'overview' | 'materials' | 'warehouses' | 'stock' | 'movements' | 'adjustments' | 'cycle-counts' | 'valuation' | 'alerts' | 'traceability' | 'lots' | 'receptions' | 'receipt-new' | 'pending-purchase-orders' | 'dispatches' | 'dispatch-new' | 'picking' | 'matpel' | 'iqbf' | 'sap' | 'sap-transactions' | 'ia' | 'predictions' | 'monitoring' | 'reports' | 'users' | 'settings' | 'suppliers' | 'customers' | 'accounting-bridge';

interface WmsNavItem {id:WmsSection;icon:string;es:string;en:string;detailEs:string;detailEn:string;group:string;}

@Component({
  selector: 'app-logistics',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="wms-shell">
      <header class="wms-header">
        <div><span class="wms-kicker">{{ t('OPERACIONES · INVENTARIO','OPERATIONS · INVENTORY') }}</span><h1>{{ t('Gestión logística','Logistics management') }}</h1><p>{{ t('WMS integrado · datos operativos en tiempo real','Integrated WMS · real-time operational data') }}</p></div>
        <div class="wms-header-actions"><span class="wms-status"><i></i>{{ t('WMS integrado','Integrated WMS') }}</span></div>
      </header>
      <nav class="wms-nav" aria-label="WMS modules">
        @for(group of groups;track group){<section class="wms-nav-group"><button type="button" class="wms-nav-group-toggle" [class.active]="isGroupActive(group)" [attr.aria-expanded]="expandedGroups[group]" (click)="toggleGroup(group)"><span>{{group}}</span><span>{{expandedGroups[group]?'⌄':'›'}}</span></button>@if(expandedGroups[group]){<div class="wms-nav-items">@for(item of groupItems(group);track item.id){<button type="button" [class.active]="section===item.id" (click)="open(item.id)"><span>{{item.icon}}</span>{{t(item.es,item.en)}}</button>}</div>}</section>}
      </nav>
      @if (error) { <div class="wms-error" role="alert">{{ error }}</div> }
      @if(section==='accounting-bridge') {
        <div class="wms-panel"><div class="wms-panel-head"><div><span class="wms-kicker">{{t('INTEGRACIÓN ERP · REVISIÓN','ERP BRIDGE · REVIEW')}}</span><h2>{{t('Mapeo contable y eventos WMS','Accounting mapping & WMS events')}}</h2></div><button class="wms-tools-button" type="button" (click)="loadBridge()">{{t('Actualizar','Refresh')}}</button></div>
          <p class="wms-caution">{{t('Los eventos se reciben de forma idempotente y se muestran para revisión. No se crean asientos automáticamente. Primero define cuentas, método de valoración y moneda con el responsable contable.','Events are stored idempotently for review. No journal entries are created automatically. Have accounting approve the accounts, valuation method and currency first.')}}</p>
          <div class="wms-form-grid">
            <label>{{t('Cuenta de inventario (activo)','Inventory account (asset)')}}<select [(ngModel)]="bridgeForm.inventory_account_id"><option value="">{{t('Sin mapear','Unmapped')}}</option>@for(a of accounts;track a.id){<option [value]="a.id">{{a.code}} · {{a.name}}</option>}</select></label>
            <label>{{t('Contrapartida de recepción','Receipt offset account')}}<select [(ngModel)]="bridgeForm.offset_account_id"><option value="">{{t('Sin mapear','Unmapped')}}</option>@for(a of accounts;track a.id){<option [value]="a.id">{{a.code}} · {{a.name}}</option>}</select></label>
            <label>{{t('Cuenta de costo / variación','Cost / variance account')}}<select [(ngModel)]="bridgeForm.expense_account_id"><option value="">{{t('Sin mapear','Unmapped')}}</option>@for(a of accounts;track a.id){<option [value]="a.id">{{a.code}} · {{a.name}}</option>}</select></label>
            <label>{{t('Método de valoración','Valuation method')}}<select [(ngModel)]="bridgeForm.valuation_method"><option value="">{{t('Sin definir','Not defined')}}</option><option value="fifo">FIFO</option><option value="weighted_average">{{t('Promedio ponderado','Weighted average')}}</option><option value="specific">{{t('Identificación específica','Specific identification')}}</option></select></label>
            <label>{{t('Moneda funcional','Functional currency')}}<input maxlength="3" [(ngModel)]="bridgeForm.currency" placeholder="PEN"></label>
            <label class="wms-check"><input type="checkbox" [(ngModel)]="bridgeForm.is_active">{{t('Integración habilitada','Integration enabled')}}</label>
          </div>
          <button class="wms-connect wms-save-map" type="button" [disabled]="bridgeSaving" (click)="saveBridge()">{{bridgeSaving?t('Guardando…','Saving…'):t('Guardar mapeo','Save mapping')}}</button>
        </div>
        <div class="wms-panel"><div class="wms-panel-head"><div><span class="wms-kicker">{{t('BANDEJA DE INTEGRACIÓN','INTEGRATION INBOX')}}</span><h2>{{t('Eventos WMS','WMS events')}}</h2></div><select class="wms-filter" [(ngModel)]="eventStatus" (ngModelChange)="loadBridgeEvents()"><option value="">{{t('Todos los estados','All statuses')}}</option><option value="blocked">{{t('Bloqueados','Blocked')}}</option><option value="preview">{{t('En revisión','In review')}}</option><option value="posted">{{t('Contabilizados','Posted')}}</option><option value="failed">{{t('Fallidos','Failed')}}</option></select></div>
          @if(bridgeEvents.length){<div class="wms-table-wrap"><table><thead><tr><th>{{t('Recibido','Received')}}</th><th>{{t('Evento','Event')}}</th><th>{{t('Documento WMS','WMS document')}}</th><th>{{t('Líneas','Lines')}}</th><th>{{t('Estado','Status')}}</th><th>{{t('Motivo','Reason')}}</th></tr></thead><tbody>@for(e of bridgeEvents;track e.id){<tr><td>{{e.received_at|date:'yyyy-MM-dd HH:mm'}}</td><td>{{e.external_event_type}}</td><td>{{e.external_document_number||e.external_document_id||e.external_event_id}}</td><td>{{e.line_count}}</td><td><span class="wms-event-status" [class.posted]="e.status==='posted'">{{e.status}}</span></td><td>{{e.block_reason||'—'}}</td></tr>}</tbody></table></div>}@else{<div class="wms-empty">{{t('No hay eventos WMS recibidos para esta empresa.','No WMS events received for this company yet.')}}</div>}
        </div>
      } @else if (section==='overview') {
         <div class="wms-kpis"><article><span>{{ t('MATERIALES','MATERIALS') }}</span><b>{{ summary['materiales'] || '—' }}</b></article><article><span>{{ t('ALMACENES','WAREHOUSES') }}</span><b>{{ summary['almacenes'] || '—' }}</b></article><article><span>{{ t('RECEPCIONES','RECEIPTS') }}</span><b>{{ summary['recepciones'] || '—' }}</b></article><article><span>{{ t('DESPACHOS','DISPATCHES') }}</span><b>{{ summary['despachos'] || '—' }}</b></article></div>
        <div class="wms-panel"><h2>{{ t('Áreas de operación','Operations areas') }}</h2><div class="wms-tiles">@for(item of nav.slice(1);track item.id){<button type="button" (click)="open(item.id)"><span>{{ item.icon }}</span><b>{{t(item.es,item.en)}}</b><small>{{t(item.detailEs,item.detailEn)}}</small><i>→</i></button>}</div></div>
      } @else {
        <div class="wms-panel"><div class="wms-panel-head"><div><span class="wms-kicker">{{ t('WMS · DATOS OPERATIVOS','WMS · OPERATIONAL DATA') }}</span><h2>{{ title() }}</h2></div><div class="wms-tools"><input [(ngModel)]="query" [placeholder]="t('Buscar en registros…','Search records…')" (keyup.enter)="loadSection()"><button type="button" (click)="loadSection()" [disabled]="loading">{{loading?t('Cargando…','Loading…'):t('Actualizar','Refresh')}}</button>@if(section==='materials'||section==='receipt-new'||section==='dispatch-new'){<button type="button" (click)="startCreate()">＋ {{t('Nuevo','New')}}</button>}</div></div>
          @if(formOpen){<form class="wms-record-form" (ngSubmit)="saveForm()"><h3>{{formTitle()}}</h3>@if(section==='materials'){
            <div class="wms-form-grid"><label>Código SAP<input name="codigo_sap" [(ngModel)]="form.codigo_sap" required maxlength="20"></label><label>{{t('Nombre','Name')}}<input name="nombre" [(ngModel)]="form.nombre" required maxlength="200"></label><label>{{t('Categoría','Category')}}<input name="categoria" [(ngModel)]="form.categoria" required></label><label>{{t('Unidad de medida','Unit of measure')}}<input name="unidad_medida" [(ngModel)]="form.unidad_medida" required maxlength="10"></label><label>{{t('Stock mínimo','Minimum stock')}}<input name="stock_minimo" type="number" min="0" [(ngModel)]="form.stock_minimo"></label><label>{{t('Stock máximo','Maximum stock')}}<input name="stock_maximo" type="number" min="0" [(ngModel)]="form.stock_maximo"></label><label class="wms-check"><input name="es_peligroso" type="checkbox" [(ngModel)]="form.es_peligroso">{{t('Material peligroso','Hazardous material')}}</label></div>
          } @else if(section==='receipt-new'){
            <div class="wms-form-grid"><label>{{t('Orden de compra','Purchase order')}}<input name="orden_compra" [(ngModel)]="form.orden_compra"></label><label>{{t('ID de proveedor','Supplier ID')}}<input name="proveedor_id" type="number" [(ngModel)]="form.proveedor_id"></label><label>{{t('ID de planta','Plant ID')}}<input name="planta_id" type="number" [(ngModel)]="form.planta_id" required></label><label>{{t('ID de almacén','Warehouse ID')}}<input name="almacen_id" type="number" [(ngModel)]="form.almacen_id"></label><label>{{t('Observaciones','Notes')}}<input name="observaciones" [(ngModel)]="form.observaciones"></label></div>
          } @else {<div class="wms-form-grid"><label>{{t('Pedido SAP','SAP order')}}<input name="pedido_sap" [(ngModel)]="form.pedido_sap"></label><label>{{t('ID cliente','Customer ID')}}<input name="cliente_id" type="number" [(ngModel)]="form.cliente_id"></label><label>{{t('ID de planta','Plant ID')}}<input name="planta_id" type="number" [(ngModel)]="form.planta_id" required></label><label>{{t('ID de almacén','Warehouse ID')}}<input name="almacen_id" type="number" [(ngModel)]="form.almacen_id"></label><label>{{t('Destino','Destination')}}<input name="destino" [(ngModel)]="form.destino"></label></div>}
            <div class="wms-form-actions"><button type="button" (click)="formOpen=false">{{t('Cancelar','Cancel')}}</button><button class="wms-tools-button" type="submit" [disabled]="saving">{{saving?t('Guardando…','Saving…'):t('Guardar','Save')}}</button></div></form>}
          @if (loading) { <div class="wms-empty">{{t('Consultando WMS…','Loading WMS…')}}</div> }
          @else if (!rows.length) { <div class="wms-empty">{{t('No se encontraron registros para mostrar.','No records found.')}}</div> }
          @else { <div class="wms-table-wrap"><table><thead><tr>@for(col of columns;track col){<th>{{label(col)}}</th>}</tr></thead><tbody>@for(row of rows;track row.id ?? row.codigo ?? row.numero ?? $index){<tr>@for(col of columns;track col){<td>{{format(row[col])}}</td>}</tr>}</tbody></table></div> }
        </div>
      }
      <footer class="wms-footnote">{{ t('Inventario, movimientos, recepción y despacho conectados al backend del WMS.','Inventory, movements, receipts and dispatches connected to the WMS backend.') }}</footer>
    </section>
  `,
  styles: [`
    :host{display:block;color:var(--fin-text,#e8edf5)}.wms-shell{--wms-accent:var(--theme-accent, #43c6b0);--wms-surface:rgba(255,255,255,.035);--wms-border:rgba(255,255,255,.09);padding:clamp(16px,2vw,28px);min-height:100%;background:radial-gradient(ellipse at 85% 0%, var(--theme-accent-bg, rgba(67,198,176,.08)), transparent 35%)}
    .wms-header{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:22px}.wms-header-actions{display:flex;align-items:center;gap:8px}.wms-disconnect{border:1px solid var(--wms-border);background:transparent;color:#9fb2c4;border-radius:999px;padding:8px 12px;font-size:11px;cursor:pointer}.wms-kicker{font-size:10px;font-weight:800;letter-spacing:.16em;color:var(--wms-accent)}h1{font-size:clamp(24px,3vw,34px);margin:8px 0 4px;letter-spacing:-.035em}h2{margin:6px 0 0;font-size:18px}.wms-header p{margin:0;color:#94a3b8;font-size:13px}.wms-status{border:1px solid var(--wms-border);border-radius:999px;padding:8px 12px;color:#9fb2c4;font-size:11px;white-space:nowrap}.wms-status i{display:inline-block;width:7px;height:7px;background:#43c6b0;border-radius:50%;margin-right:8px;box-shadow:0 0 10px #43c6b088}
    .wms-nav{display:flex;flex-direction:column;gap:5px;margin-bottom:18px}.wms-nav-group{border:1px solid var(--wms-border);border-radius:10px;overflow:hidden}.wms-nav-group-toggle{width:100%;display:flex;justify-content:space-between;background:rgba(255,255,255,.025);color:#e2e8f0;border:0;padding:10px 13px;font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;cursor:pointer}.wms-nav-items{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:4px;padding:6px}.wms-nav-items button{display:flex;align-items:center;gap:8px;text-align:left;background:transparent;border:1px solid transparent;color:#aebccd;border-radius:7px;padding:8px;font-size:12px;cursor:pointer}.wms-nav-items button:hover,.wms-nav-items button.active{background:color-mix(in srgb,var(--wms-accent) 12%,transparent);border-color:color-mix(in srgb,var(--wms-accent) 40%,transparent);color:#fff}.wms-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}.wms-kpis article,.wms-panel{background:var(--wms-surface);border:1px solid var(--wms-border);border-radius:14px}.wms-kpis article{padding:16px}.wms-kpis span{font-size:10px;letter-spacing:.12em;color:#8fa0b3;font-weight:700}.wms-kpis b{display:block;font-size:28px;margin-top:8px}.wms-panel{padding:18px;margin-bottom:12px}.wms-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-top:14px}.wms-tiles button{text-align:left;position:relative;min-height:110px;padding:14px;border-radius:12px;border:1px solid var(--wms-border);background:rgba(9,17,29,.5);color:inherit;cursor:pointer}.wms-tiles button:hover{border-color:var(--wms-accent);transform:translateY(-1px)}.wms-tiles span{display:block;color:var(--wms-accent);font-size:18px}.wms-tiles b,.wms-tiles small{display:block;margin-top:9px}.wms-tiles small{color:#92a0b1;font-size:11px}.wms-tiles i{position:absolute;right:14px;top:14px;color:var(--wms-accent);font-style:normal}.wms-panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}.wms-tools{display:flex;gap:8px;flex-wrap:wrap}.wms-tools input,.wms-filter{background:#0b1422;border:1px solid var(--wms-border);border-radius:9px;padding:9px 11px;color:#e8edf5;min-width:210px}.wms-table-wrap{overflow:auto;border:1px solid var(--wms-border);border-radius:10px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:11px 12px;border-bottom:1px solid var(--wms-border);white-space:nowrap}th{background:rgba(255,255,255,.035);color:#8fa0b3;font-size:10px;letter-spacing:.08em;text-transform:uppercase}tr:last-child td{border-bottom:0}.wms-empty{padding:26px;text-align:center;color:#91a0b3;font-size:13px}.wms-error{padding:12px 14px;margin-bottom:14px;border:1px solid #f87171;color:#fecaca;background:#7f1d1d33;border-radius:10px}.wms-caution{border:1px solid #fbbf2466;background:#fbbf2410;color:#f6d98b;padding:12px;border-radius:10px;font-size:12px;line-height:1.55}.wms-form-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:14px}.wms-form-grid label{display:grid;gap:6px;font-size:11px;color:#9fb2c4}.wms-form-grid input,.wms-form-grid select{min-height:38px;background:#0b1422;border:1px solid var(--wms-border);border-radius:8px;color:#e8edf5;padding:8px}.wms-form-grid .wms-check{display:flex;align-items:center;gap:8px}.wms-save-map{width:auto;min-width:180px}.wms-event-status{color:#f5ce78}.wms-event-status.posted{color:#43c6b0}.wms-record-form{padding:16px;border:1px solid var(--wms-border);border-radius:12px;margin-bottom:16px;background:#0b142255}.wms-record-form h3{margin:0}.wms-form-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}.wms-form-actions button{border:1px solid var(--wms-border);background:transparent;color:#dbe4ee;border-radius:8px;padding:9px 14px;cursor:pointer}.wms-footnote{padding:8px 2px;color:#76869a;font-size:11px}@media(max-width:760px){.wms-header,.wms-panel-head{align-items:flex-start;flex-direction:column}.wms-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.wms-tools{width:100%}.wms-tools input{min-width:0;flex:1}.wms-form-grid{grid-template-columns:1fr}}
  `],
})
export class LogisticsComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly language = inject(LanguageService);
  private readonly companies = inject(CompanyService);
  section: WmsSection = 'overview';
  rows: any[] = [];
  columns: string[] = [];
  summary: Record<string, number | string> = {};
  loading = false;
  error = '';
  query = '';
  wmsConnected=true;
  accounts:any[]=[]; bridgeEvents:any[]=[]; bridgeSaving=false; eventStatus='';
  formOpen=false;saving=false;form:any={};
  bridgeForm:any={company_id:'',integration_code:'WMS',external_base_url:'',is_active:true,inventory_account_id:'',offset_account_id:'',expense_account_id:'',valuation_method:'',currency:'PEN'};
  private readonly base = '/api/v1/wms';
  readonly nav:WmsNavItem[] = [
    {id:'overview',icon:'◈',es:'Resumen',en:'Overview',detailEs:'Panel general del almacén',detailEn:'Warehouse overview',group:'Principal'},
    {id:'materials',icon:'▦',es:'Insumos / Materiales',en:'Supplies / Materials',detailEs:'Maestro de insumos y códigos SAP',detailEn:'Supply and SAP material master',group:'Tablas'},
    {id:'suppliers',icon:'♙',es:'Proveedores',en:'Suppliers',detailEs:'Directorio de proveedores',detailEn:'Supplier directory',group:'Tablas'},
    {id:'customers',icon:'♧',es:'Clientes',en:'Customers',detailEs:'Directorio de clientes',detailEn:'Customer directory',group:'Tablas'},
    {id:'warehouses',icon:'▤',es:'Almacenes y ubicaciones',en:'Warehouses & locations',detailEs:'Plantas, almacenes y ubicaciones',detailEn:'Plants, warehouses and locations',group:'Tablas'},
    {id:'stock',icon:'▣',es:'Consulta de existencias',en:'Stock inquiry',detailEs:'Disponibilidad por insumo y ubicación',detailEn:'Availability by material and location',group:'Inventario'},
    {id:'movements',icon:'⇄',es:'Movimientos',en:'Movements',detailEs:'Entradas, salidas y transferencias',detailEn:'Receipts, issues and transfers',group:'Inventario'},
    {id:'adjustments',icon:'±',es:'Ajustes',en:'Adjustments',detailEs:'Ajustes sujetos a aprobación',detailEn:'Adjustments subject to approval',group:'Inventario'},
    {id:'cycle-counts',icon:'☷',es:'Conteos cíclicos',en:'Cycle counts',detailEs:'Conteos y diferencias',detailEn:'Counts and variances',group:'Inventario'},
    {id:'valuation',icon:'＄',es:'Valorización',en:'Valuation',detailEs:'Valoración de existencias',detailEn:'Inventory valuation',group:'Inventario'},
    {id:'alerts',icon:'!',es:'Alertas',en:'Alerts',detailEs:'Quiebres y niveles críticos',detailEn:'Stockouts and critical levels',group:'Inventario'},
    {id:'traceability',icon:'⌕',es:'Trazabilidad',en:'Traceability',detailEs:'Trazabilidad extremo a extremo',detailEn:'End-to-end traceability',group:'Inventario'},
    {id:'lots',icon:'◫',es:'Lotes y vencimientos',en:'Lots & expiry',detailEs:'Lotes, FIFO/FEFO y vencimientos',detailEn:'Lots, FIFO/FEFO and expiry',group:'Inventario'},
    {id:'receptions',icon:'↓',es:'Recepciones',en:'Receipts',detailEs:'Recepciones y estado de órdenes',detailEn:'Receipts and order status',group:'Recepción'},
    {id:'receipt-new',icon:'＋',es:'Nueva recepción',en:'New receipt',detailEs:'Registrar recepción y líneas',detailEn:'Create receipt and lines',group:'Recepción'},
    {id:'pending-purchase-orders',icon:'▤',es:'Órdenes pendientes',en:'Pending purchase orders',detailEs:'Órdenes por recibir',detailEn:'Orders pending receipt',group:'Recepción'},
    {id:'dispatches',icon:'↑',es:'Despachos',en:'Dispatches',detailEs:'Pedidos, despacho y estado',detailEn:'Orders, dispatch and status',group:'Despacho'},
    {id:'dispatch-new',icon:'＋',es:'Nuevo despacho',en:'New dispatch',detailEs:'Crear despacho',detailEn:'Create dispatch',group:'Despacho'},
    {id:'picking',icon:'☑',es:'Picking',en:'Picking',detailEs:'Preparación y confirmación de picking',detailEn:'Picking preparation and confirmation',group:'Despacho'},
    {id:'matpel',icon:'⚠',es:'MATPEL',en:'Hazardous materials',detailEs:'Materiales peligrosos y compatibilidad',detailEn:'Hazardous materials and compatibility',group:'Regulatorio'},
    {id:'iqbf',icon:'▧',es:'IQBF SUNAT',en:'IQBF SUNAT',detailEs:'Movimientos y reporte regulatorio',detailEn:'Regulatory movements and reporting',group:'Regulatorio'},
    {id:'sap',icon:'⇄',es:'Integración SAP',en:'SAP integration',detailEs:'Conexión, sincronización y estado',detailEn:'Connection, sync and status',group:'Integraciones'},
    {id:'sap-transactions',icon:'▤',es:'Transacciones SAP',en:'SAP transactions',detailEs:'Pendientes, fallidas y reintentos',detailEn:'Pending, failed and retries',group:'Integraciones'},
    {id:'ia',icon:'✦',es:'Motor IA',en:'AI engine',detailEs:'Insights y anomalías',detailEn:'Insights and anomalies',group:'Inteligencia'},
    {id:'predictions',icon:'⌁',es:'Predicción de demanda',en:'Demand forecasting',detailEs:'Proyección por material y planta',detailEn:'Forecast by material and plant',group:'Inteligencia'},
    {id:'accounting-bridge',icon:'⇆',es:'Integración contable',en:'Accounting bridge',detailEs:'Eventos, trazabilidad y mapeo contable',detailEn:'Events, traceability and accounting mappings',group:'Integraciones'},
    {id:'monitoring',icon:'▥',es:'Monitoreo',en:'Monitoring',detailEs:'Métricas y tableros operativos',detailEn:'Metrics and operational dashboards',group:'Sistema'},
    {id:'reports',icon:'▧',es:'Reportes',en:'Reports',detailEs:'Reportes operativos',detailEn:'Operational reports',group:'Sistema'},
    {id:'users',icon:'♙',es:'Usuarios y permisos',en:'Users & permissions',detailEs:'Administración de usuarios',detailEn:'User administration',group:'Sistema'},
    {id:'settings',icon:'⚙',es:'Configuración',en:'Settings',detailEs:'Parámetros del WMS',detailEn:'WMS settings',group:'Sistema'},
  ];
  readonly groups=[...new Set(this.nav.map(item=>item.group))];
  expandedGroups:Record<string,boolean>={Principal:true,Tablas:true,Inventario:false,Recepción:false,Despacho:false,Regulatorio:false,Integraciones:false,Inteligencia:false,Sistema:false};
  private readonly config: Partial<Record<Exclude<WmsSection, 'overview'|'accounting-bridge'>, {path:string; columns:string[]; queryKey?:string}>> = {
    materials:{path:'/materiales',columns:['codigo_sap','nombre','categoria','unidad_medida','stock_minimo','stock_maximo','stock_actual','activo'],queryKey:'search'},
    suppliers:{path:'/materiales/directory/suppliers',columns:['ruc','razon_social','contacto','telefono','email','activo'],queryKey:'search'},
    customers:{path:'/materiales/directory/customers',columns:['ruc','razon_social','direccion','activo'],queryKey:'search'},
    warehouses:{path:'/inventario/almacenes',columns:['codigo','nombre','tipo','planta_id']},
    stock:{path:'/inventario/stock',columns:['material_id','ubicacion_id','lote_id','cantidad','cantidad_reservada']},
    movements:{path:'/inventario/movimientos',columns:['fecha','tipo','material_id','cantidad','referencia','motivo']},
    adjustments:{path:'/inventario/ajustes',columns:['id','material_id','ubicacion_id','cantidad_sistema','cantidad_real','diferencia','motivo','estado']},
    'cycle-counts':{path:'/inventario/conteos',columns:['id','nombre','planta_id','estado','fecha_inicio','fecha_cierre']},
    valuation:{path:'/inventario/valorizacion',columns:['material_id','codigo_sap','nombre','cantidad','costo_promedio','valor_total']},
    alerts:{path:'/inventario/alertas',columns:['tipo','material_id','codigo_sap','nombre','stock_actual','stock_minimo','mensaje']},
    traceability:{path:'/inventario/trazabilidad',columns:['fecha','tipo','material','lote','cantidad','referencia','usuario']},
    lots:{path:'/lotes',columns:['numero','material_id','fecha_ingreso','fecha_vencimiento','cantidad_inicial','estado']},
    receptions:{path:'/recepciones',columns:['numero','orden_compra','proveedor','planta','estado','fecha','lineas_count']},
    'receipt-new':{path:'/recepciones/ordenes-compra/pendientes',columns:['orden_compra','proveedor','planta','fecha','estado']},
    'pending-purchase-orders':{path:'/recepciones/ordenes-compra/pendientes',columns:['orden_compra','proveedor','planta','fecha','estado']},
    dispatches:{path:'/despachos',columns:['numero','pedido_sap','cliente','planta','estado','fecha_despacho']},
    'dispatch-new':{path:'/despachos',columns:['numero','pedido_sap','cliente','planta','estado','fecha_despacho']},
    picking:{path:'/despachos',columns:['numero','pedido_sap','cliente','estado','fecha_requerida']},
    matpel:{path:'/matpel',columns:['material_id','numero_onu','clase_onu','division','es_iqbf','nombre_tecnico']},
    iqbf:{path:'/matpel/iqbf/registros',columns:['fecha','tipo_operacion','material_id','cantidad','unidad','tercero_ruc','tercero_nombre']},
    sap:{path:'/sap/dashboard',columns:['estado','transacciones_pendientes','transacciones_fallidas','ultima_sincronizacion']},
    'sap-transactions':{path:'/sap/transactions/pending',columns:['id','tipo','referencia_wms','documento_sap','estado','intentos','error_message']},
    ia:{path:'/ia/dashboard',columns:['insights','anomalias','modelo','estado']},
    predictions:{path:'/ia/dashboard',columns:['material_id','fecha_prediccion','cantidad_predicha','limite_inferior','limite_superior','nivel_confianza']},
    monitoring:{path:'/sap/status',columns:['service','status','version','timestamp']},
    reports:{path:'/inventario/stock/resumen',columns:['planta','almacen','materiales','cantidad_total','valor_total']},
    users:{path:'/auth/users',columns:['id','username','nombre','email','rol','activo']},
    settings:{path:'/auth/roles',columns:['rol','descripcion']},
  };
  ngOnInit(): void { this.loadSummary(); }
  t(es:string,en:string):string { return this.language.text(es,en); }
  groupItems(group:string):WmsNavItem[]{return this.nav.filter(item=>item.group===group);}
  isGroupActive(group:string):boolean{return this.nav.some(item=>item.group===group&&item.id===this.section);}
  toggleGroup(group:string):void{this.expandedGroups[group]=!this.expandedGroups[group];}
  startCreate():void{this.formOpen=true;this.form=this.section==='materials'?{codigo_sap:'',nombre:'',categoria:'',unidad_medida:'UN',es_peligroso:false,stock_minimo:null,stock_maximo:null}:this.section==='receipt-new'?{orden_compra:'',proveedor_id:null,planta_id:null,almacen_id:null,tipo:'orden_compra',observaciones:''}:{pedido_sap:'',cliente_id:null,planta_id:null,almacen_id:null,prioridad:'normal',tipo_despacho:'completo',destino:''};}
  formTitle():string{return this.section==='materials'?this.t('Nuevo insumo','New supply'):this.section==='receipt-new'?this.t('Crear recepción','Create receipt'):this.t('Crear despacho','Create dispatch');}
  saveForm():void{const path=this.section==='materials'?'/materiales':this.section==='receipt-new'?'/recepciones':'/despachos';this.saving=true;this.http.post<any>(`${this.base}${path}`,this.form).subscribe({next:()=>{this.saving=false;this.formOpen=false;this.error='';this.loadSection();},error:e=>{this.saving=false;this.error=e?.error?.detail||this.t('No se pudo guardar el registro. Revisa los campos y permisos.','Could not save. Check fields and permissions.');}});}
  title():string { const item=this.nav.find(x=>x.id===this.section); return item?this.t(item.es,item.en):''; }
  open(section:WmsSection):void { this.section=section;this.query='';this.error='';if(section==='accounting-bridge'){this.loadBridge();return;}if(section!=='overview')this.loadSection();else this.loadSummary(); }
  loadBridge():void {
    const companyId=this.companies.selectedCompanyId();if(!companyId){this.error=this.t('Selecciona una empresa activa en el encabezado del ERP.','Select an active company in the ERP header.');return;}
    this.bridgeForm={...this.bridgeForm,company_id:companyId};
    this.http.get<any[]>('/api/v1/finance/accounts',{params:{company_id:companyId}}).subscribe({next:r=>this.accounts=(r||[]).filter((a:any)=>a.allow_posting&&a.is_active&&!a.is_group),error:e=>this.error=e?.error?.detail||'No se pudo cargar el plan contable.'});
    this.http.get<any>('/api/v1/finance/wms/integration',{params:{company_id:companyId}}).subscribe({next:r=>{if(r?.integration)this.bridgeForm={...this.bridgeForm,...r.integration,company_id:companyId,inventory_account_id:r.integration.inventory_account_id||'',offset_account_id:r.integration.offset_account_id||'',expense_account_id:r.integration.expense_account_id||'',valuation_method:r.integration.valuation_method||'',currency:r.integration.currency||'PEN'};this.loadBridgeEvents();},error:e=>this.error=e?.error?.detail||'No se pudo cargar la configuración WMS.'});
  }
  saveBridge():void {const companyId=this.companies.selectedCompanyId();if(!companyId)return;this.bridgeSaving=true;const payload={...this.bridgeForm,company_id:companyId,inventory_account_id:this.bridgeForm.inventory_account_id||null,offset_account_id:this.bridgeForm.offset_account_id||null,expense_account_id:this.bridgeForm.expense_account_id||null,valuation_method:this.bridgeForm.valuation_method||null,currency:this.bridgeForm.currency?.toUpperCase()||null};this.http.put('/api/v1/finance/wms/integration',payload).subscribe({next:()=>{this.bridgeSaving=false;this.error='';this.loadBridge();},error:e=>{this.bridgeSaving=false;this.error=e?.error?.detail||'No se pudo guardar el mapeo.';}});}
  loadBridgeEvents():void {const companyId=this.companies.selectedCompanyId();if(!companyId)return;const params:any={company_id:companyId};if(this.eventStatus)params.status_filter=this.eventStatus;this.http.get<any[]>('/api/v1/finance/wms/events',{params}).subscribe({next:r=>this.bridgeEvents=r||[],error:e=>this.error=e?.error?.detail||'No se pudo cargar la bandeja WMS.'});}
  loadSummary():void {
    if(!this.wmsConnected)return;
    this.http.get<any>(`${this.base}/materiales/dashboard/summary`).subscribe({next:r=>{this.summary=r||{};},error:e=>{this.error=e?.error?.detail||this.t('No se pudo cargar el resumen WMS.','Could not load WMS dashboard.');}});
  }
  loadSection():void {
    if(!this.wmsConnected){this.error=this.t('La sesión de la empresa no está disponible.','The company session is unavailable.');return;}
    if(this.section==='overview'||this.section==='accounting-bridge')return;
    const c=this.config[this.section];if(!c)return;this.loading=true;this.error='';
    const params:any={page:1,per_page:100};if(this.query.trim())params[c.queryKey||'search']=this.query.trim();
    const url=c.path.startsWith('/api/v1/')?c.path:`${this.base}${c.path}`;
    this.http.get<any>(url,{params}).subscribe({next:r=>{
      const data=Array.isArray(r)?r:(r?.items||r?.data||r?.results||[]);this.rows=Array.isArray(data)?data:[];
      this.columns=this.rows.length?c.columns.filter(col=>col in this.rows[0]):c.columns;this.loading=false;
    },error:e=>{this.rows=[];this.columns=c.columns;this.loading=false;this.error=e?.error?.detail||this.t('No se pudo conectar con el API del WMS. Confirma que el servicio esté ejecutándose en el puerto 18005.','Could not connect to WMS API. Ensure the service is running on port 18005.');}});
  }
  label(key:string):string { return key.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase()); }
  format(value:any):string { if(value===null||value===undefined||value==='')return '—';if(typeof value==='boolean')return value?this.t('Sí','Yes'):this.t('No','No');if(typeof value==='object')return JSON.stringify(value);return String(value); }
}
