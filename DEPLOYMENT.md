# Despliegue: Supabase + Render + Vercel

Arquitectura preparada:

- **Vercel:** Angular estático, raíz `frontend`.
- **Render:** dos servicios FastAPI: Identity (`backend/run.py`) y Finance (`backend/run_finance.py`).
- **Supabase:** PostgreSQL. El proyecto conserva su autenticación propia (JWT de Identity); Supabase Auth está deshabilitado deliberadamente.

> No usar datos reales de producción para la primera prueba. Crea un proyecto Supabase de *staging* y valida ahí migraciones, conexión y login antes de producción.

## 0. Preparar GitHub

El repo Git está en la raíz `erpAethereon` y ya tiene remoto `origin`. Vercel y Render despliegan el contenido de GitHub, no los archivos locales sin commit.

1. Revisa `git status` y confirma cada cambio que quieras incluir; no añadas archivos `.env`, `*.env.local`, volcados de BD, credenciales ni tokens.
2. Ejecuta los builds de frontend y `py_compile` de los servicios.
3. Haz commit y push a la rama que usarás como producción (actualmente `main`).

No publiques ningún secreto en el repositorio.

## 1. Supabase: PostgreSQL y migraciones

1. Crea un proyecto Supabase en la región cercana a Render. Guarda de forma privada la contraseña de base de datos.
2. Usa **Session pooler** o conexión directa PostgreSQL para Render. Construye `DATABASE_URL` con esquema SQLAlchemy, por ejemplo:

   `postgresql+psycopg2://USER:PASSWORD@HOST:PORT/postgres`

   Codifica caracteres especiales de la contraseña como URL-encoding. No uses el Transaction Pooler para la conexión persistente de SQLAlchemy.
3. El repo tiene las migraciones originales en `database/migrations/` y una copia ordenada con timestamps en `supabase/migrations/`. Ambas se conservan; edita la migración original y vuelve a sincronizar su copia si cambias el esquema.
4. Instala la Supabase CLI y Docker Desktop. Desde la raíz del repo:

   ```powershell
   npx supabase start
   npx supabase db reset
   ```

   La segunda orden **borra y recrea la base local de Supabase**; no la apuntes a producción. Este proyecto no tiene `seed.sql` y `seed_enabled=false`.
5. Revisa cualquier fallo de extensiones/permisos. Las migraciones usan `pgcrypto`, `btree_gist`, exclusiones PostgreSQL, `CREATE EXTENSION` y transacciones explícitas. Comprueba la cadena completa en local; no des por hecho que basta con copiar SQL en el editor.
6. Antes de una base remota vacía, configura el proyecto y prueba primero en staging:

   ```powershell
   npx supabase login
   npx supabase link --project-ref <PROJECT_REF>
   npx supabase db push --dry-run --remote
   ```

   Inspecciona el plan. Luego, solo si el proyecto enlazado es el correcto y está vacío/preparado:

   ```powershell
   npx supabase db push --remote
   ```

   En este entorno no pude ejecutar `supabase db reset`: Supabase CLI no está instalado y Docker Desktop no está iniciado. Es obligatorio completar esa prueba en tu equipo antes de `db push` a staging; revisa especialmente transacciones explícitas y permisos para crear `btree_gist`.

   **No ejecutes `supabase db reset --remote` en producción.** No uses `--include-seed` en producción.
7. Security gate obligatorio antes de producción: el esquema actual usa tablas propias (`users`, `memberships`, `roles`) y la API hace autorización en FastAPI; todavía no se ha auditado/configurado RLS para acceso directo vía PostgREST. No expongas la key `service_role` ni permitas acceso directo de navegador a estas tablas. Las APIs deben ser la única ruta de datos.
8. En Supabase Pro configura backups/PITR según RPO/RTO esperado, límites de conexión y alertas. Free puede pausarse por inactividad y no ofrece backups descargables.

## 2. Render: Identity y Finance

1. Importa el repo de GitHub en Render como **Blueprint** y selecciona la raíz del repositorio (`render.yaml`). Revisa el plan y los costos antes de aplicar.
2. Se crearán dos Web Services Python. Render inyecta `PORT`; los entrypoints ya usan `PORT` y en Render escuchan en `0.0.0.0`. Los health checks son `/health/ready`.
3. En **ambos** servicios configura `DATABASE_URL` con el mismo proyecto Supabase y `JWT_SECRET_KEY` con el mismo secreto aleatorio de al menos 32 bytes. Genera uno fuera del repo (por ejemplo `python -c "import secrets; print(secrets.token_hex(48))"`) y copia el mismo valor a ambos servicios.
4. Mantén:
   - Identity: `JWT_ALGORITHM=HS256`, `JWT_EXPIRE_MINUTES=60`, `CORS_ORIGINS=https://<dominio-vercel>`.
   - Finance: `JWT_ALGORITHM=HS256`, `JWT_ISSUER=aethereon-identity`, `JWT_AUDIENCE=aethereon-erp`, misma `CORS_ORIGINS`.
   - `IDENTITY_RELOAD=false`, `FINANCE_RELOAD=false`, `IDENTITY_UPDATE_FRONTEND_PROXY=false`.
5. Despliega primero Identity y Finance. Copia sus hostnames HTTPS reales de Render.
6. Comprueba ambos health checks `/health/ready` y revisa logs. La base se administra con migraciones Supabase, no con `docker-compose.yml` de desarrollo.

## 3. Vercel: Angular

1. En Vercel → **New Project**, importa el repositorio GitHub `mangulom/erp-aethereon`.
2. Configura **Root Directory = `frontend`** y permite instalar dependencias desde esa carpeta.
3. Vercel detecta Angular. El build verificado genera `frontend/dist/frontend/browser`. Con `frontend` como root, el output relativo suele ser `dist/frontend/browser`; si el preset Angular detecta automáticamente el output, deja el valor detectado. Build command verificado:

   `npm run build -- --configuration production`

4. En `frontend/vercel.json`, reemplaza los dos textos `REPLACE_WITH_...` por los hostnames reales de Render, sin `https://` duplicado. El orden es intencional: `/api/v1/finance/*` va a Finance antes del rewrite general `/api/*` hacia Identity. Se agrega fallback SPA a `index.html`.
5. Revisa la lista de dominios de Vercel y copia el dominio definitivo (por ejemplo `https://<proyecto>.vercel.app`). En los dos servicios Render, `CORS_ORIGINS` debe ser ese origen exacto, sin barra final. Si usas dominio propio, agrega ambos orígenes separados por coma.
6. Haz Deploy. Cuando quede listo, usa recarga forzada del navegador y valida rutas profundas (`/finance`, `/finance/ai`) y `/api`.

## 4. Validación de extremo a extremo

1. `https://<identity-host>/health/ready` y `https://<finance-host>/health/ready` devuelven `200`.
2. Entra por Vercel. Login funciona y el selector de empresa lista los nombres actuales.
3. Selecciona empresa; verifica que las peticiones a `/api/v1/finance/...` llegan a Finance y las `/api/v1/auth/...` a Identity.
4. Crea un ejercicio de prueba; confirma que persiste tras recargar. Luego crea periodos dentro del rango del ejercicio.
5. Importa/aplica un plan de cuentas de prueba y confirma jerarquía. No borres planes que tengan movimientos, comprobantes, presupuestos o bancos.
6. Inteligencia IA: la demo sintética es solo de interfaz y está rotulada; los endpoints reales deben indicar `has_data=false` mientras no haya registros contabilizados.
7. Revisa CORS, logs, backups y reglas de acceso. No actives Supabase Auth como reemplazo parcial del JWT actual sin migración diseñada.

## Configuración preparada en el repo

- `frontend/vercel.json`: rewrites, fallback SPA y headers. Reemplaza los hostnames `REPLACE_WITH_...` antes de desplegar.
- `render.yaml`: blueprint de ambos servicios; requiere completar secretos en el dashboard.
- `supabase/config.toml` y `supabase/migrations/`: CLI y copias versionadas de migraciones.

Este repo no ha sido desplegado desde aquí: requiere que tú conectes GitHub en los dashboards, crees los recursos y completes secretos en sus campos seguros.
