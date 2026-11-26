# Integración WMS con Sophia ERP

## Componentes

- Frontend del ERP (Angular): el sidebar de **Operaciones → Logística** abre `/logistics`.
- API WMS (FastAPI): proyecto externo integrado por HTTP local, puerto `18005`.
- Datos WMS: esquema PostgreSQL aislado `wms`, importado desde `database/wms/wms_schema_data.sql`; las tablas financieras siguen en `public` y no se mezclan con el WMS.
- Proxy Angular: `/api/wms/*` se reescribe a `/api/v1/*` y se envía a `127.0.0.1:18005`.
- Autenticación: el WMS conserva sus usuarios, permisos y JWT separados; el interceptor agrega `aethereon.wms_access_token` solo a solicitudes WMS.

## Inicio local

1. Asegurar que PostgreSQL contenga el schema `wms` y su importación. Si se instala desde cero, crear primero el schema y aplicar el dump con una herramienta `psql` que respete los comandos `\restrict` del archivo.
2. Configurar el `.env` privado de WMS con su URL de BD, `DB_SCHEMA=wms`, puerto `18005` y secretos propios. No reutilizar claves de producción ni versionar `.env`.
3. Ejecutar `npm run dev:wms` desde el directorio raíz del ERP. Para iniciar frontend, identidad y WMS juntos se usa `npm run dev`.
4. Iniciar sesión en el ERP y conectar el usuario WMS desde el módulo Logística. La sesión WMS se conserva separada.

## Integración funcional

Finanzas/contabilidad pueden consumir el directorio de clientes/proveedores WMS para crear auxiliares en su propia empresa, conservando el ID WMS como referencia externa. Los movimientos del WMS solo generan impacto financiero al confirmarse y deben publicarse en un flujo de integración idempotente, con cuenta de inventario, costo/variación, centro/almacén y trazabilidad del movimiento. Este asiento debe generarse en Finanzas/Contabilidad (fuente de verdad), no duplicar saldos en el schema WMS.

## Rutas usadas

- `GET /api/v1/materiales/dashboard/summary`
- `GET /api/v1/materiales?search=&page=&per_page=`
- `GET /api/v1/inventario/almacenes`, `/stock`, `/movimientos`
- `GET /api/v1/recepciones`, `/api/v1/despachos`
- Directorios lectura: `GET /api/v1/materiales/directory/suppliers` y `/directory/customers`
- Login: `POST /api/v1/auth/login`
- ERP bridge configuration: `GET/PUT /api/v1/finance/wms/integration`
- ERP bridge inbox: `GET /api/v1/finance/wms/events`
- Idempotent event intake: `POST /api/v1/finance/wms/integration/{integration_id}/events`

## Estado del bridge contable

La migración `022_wms_accounting_bridge.sql` añade un registro de integración por empresa, bandeja inmutable por clave externa y detalle de líneas. El endpoint de eventos valida el hash para evitar reenvíos inconsistentes y solo guarda estado `preview`/`blocked`; nunca crea asientos. El operador ERP puede guardar el mapeo de cuenta de inventario, contrapartida, cuenta de costo, método de valoración y moneda.

La contabilización automática sigue deshabilitada deliberadamente: aún requiere acuerdos funcionales para evento de recepción/despacho que reconoce propiedad del inventario, costo por movimiento, tratamiento de devoluciones y ajustes, apertura de periodo, autorización/aprobación, y política de costos/impuestos. No marcar un evento como contabilizado hasta que estas reglas y pruebas de reversión/reintento estén implementadas.

El API WMS requiere permisos propios por endpoint. No se han importado ni reasignado usuarios, hashes de contraseña, secretos, ni datos operativos al esquema financiero.
