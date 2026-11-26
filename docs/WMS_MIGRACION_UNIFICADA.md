# WMS integrado a Sophia ERP / Angular 19

## Estado de la integración ejecutable

- UI principal: `frontend/src/app/pages/logistics/logistics.component.ts`, agrupada por Tablas (incluye Insumos/Materiales), Inventario, Recepción, Despacho, Regulatorio, Integraciones, Inteligencia y Sistema.
- Servicio FastAPI original portado dentro del repo: `backend/services/logistics/` (backend WMS/Logística); puerto local `18005`.
- Base unificada: una misma base PostgreSQL `aethereon_erp`; el WMS conserva el schema `wms` para evitar colisiones con Identity/Finance (`users`, `companies`, etc.). El dump con DDL/datos se conserva en `database/wms/wms_schema_data.sql`.
- Login: JWT de Identity de Sophia, issuer `aethereon-identity`, audience `aethereon-erp`; los permisos WMS se derivan de permisos explícitos en memberships. Migración `024_wms_permissions.sql` crea catálogo, sin asignarlo a roles automáticamente.
- `npm run dev` inicia frontend, Identity y WMS; `scripts/start-wms.ps1` obtiene DB/JWT de `.env` privado de Finance, no versionado.
- Proxy Angular: `/api/v1/wms/*` → `localhost:18005/api/v1/*`.

## Rutas portadas disponibles

Resumen; materiales/insumos y directorios cliente/proveedor; almacenes/ubicaciones, stock, movimientos, ajustes, conteos, valorización, alertas, trazabilidad, lotes; recepciones, órdenes pendientes, despachos, picking; MATPEL/IQBF; SAP, transacciones; IA/predicciones; reportes, usuarios/configuración; puente contable.

La navegación ya conserva el mapa de pantallas React. En esta fase, algunas entradas muestran tablas de consulta genéricas; los formularios implementados incluyen alta de material, recepción y despacho. No declarar estas pantallas como paridad funcional completa hasta portar sus formularios, detalle y workflows React (picking, aprobaciones, recepción por líneas, operaciones IQBF, SAP, IA y administración) y agregar pruebas.

## Prueba local realizada

- `GET /health` → healthy en 18005.
- Con token ERP válido, `GET /api/v1/materiales/dashboard/summary` → 46.014 materiales, 8 almacenes, 21 recepciones, 7 despachos.
- Build Angular y syntax checks Python pasaron en la última validación.

## Verificaciones y operación

1. `npm run dev` debe iniciar los cuatro procesos; en particular WMS escucha en `18005`.
2. Dar a los roles solo permisos WMS apropiados (no se otorgan automáticamente). Para módulos se requieren los códigos `wms.*` del catálogo.
3. Probar CRUD/flows, permisos por planta/empresa y escenarios de reintento antes de producción.
4. El schema WMS es independiente dentro de la misma instancia; no mover sus tablas a `public`, donde ya existen nombres compartidos.
