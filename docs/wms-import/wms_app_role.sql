-- ============================================================
-- WMS REPSOL - ROLE DE APLICACIÓN CON PERMISOS LIMITADOS
-- Ejecutar como superusuario (postgres) en Postgres LOCAL.
--
-- Objetivo: que la app (FastAPI) NO se conecte como superusuario.
-- Este role solo puede CRUD sobre el schema wms, sin DDL ni acceso
-- a otros schemas ni a roles de sistema.
--
-- Uso:
--   1) Ajustar la contraseña al final.
--   2) psql -U postgres -d wms_repsol -f wms_app_role.sql
--   3) En .env del backend:
--        DATABASE_URL=postgresql://wms_app:<pwd>@localhost:5432/wms_repsol
--        DB_SCHEMA=wms
-- ============================================================

\set ON_ERROR_STOP on

-- === 1. Role de aplicación (login role) =====================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
    CREATE ROLE wms_app LOGIN
      PASSWORD '3mlx440*'
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
      INHERIT CONNECTION LIMIT 50;
  END IF;
END
$$;

-- Privilegios a nivel de BD
REVOKE ALL ON DATABASE wms_repsol FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE wms_repsol TO wms_app;

-- === 2. Permisos sobre el schema wms ========================
-- Quita wildcard de PUBLIC en el schema y da solo lo necesario a wms_app.
REVOKE ALL ON SCHEMA wms FROM PUBLIC;
GRANT USAGE ON SCHEMA wms TO wms_app;

-- DML sobre tablas existentes
GRANT SELECT, INSERT, UPDATE, DELETE
  ON ALL TABLES IN SCHEMA wms TO wms_app;

-- Secuencias (para SERIAL / IDENTITY)
GRANT USAGE, SELECT, UPDATE
  ON ALL SEQUENCES IN SCHEMA wms TO wms_app;

-- Funciones (ej. triggers, helpers propios del schema)
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA wms TO wms_app;

-- === 3. Privilegios por defecto para objetos FUTUROS ========
-- Lo que se cree después también hereda los permisos correctos.
ALTER DEFAULT PRIVILEGES IN SCHEMA wms
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wms_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA wms
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO wms_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA wms
  GRANT EXECUTE ON FUNCTIONS TO wms_app;

-- === 4. Denegaciones explícitas =============================
-- wms_app NO debe poder tocar schemas administrativos ni crear objetos.
REVOKE CREATE ON SCHEMA wms FROM wms_app;
REVOKE CREATE ON SCHEMA public FROM wms_app;

-- === 5. search_path persistente =============================
ALTER ROLE wms_app SET search_path = wms, public;

-- === 6. Tabla de auditoría opcional =========================
-- Si usas audit.log (middleware/backend_services.py), dale sólo INSERT.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'audit') THEN
    GRANT USAGE ON SCHEMA audit TO wms_app;
    GRANT INSERT ON ALL TABLES IN SCHEMA audit TO wms_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA audit
      GRANT INSERT ON TABLES TO wms_app;
  END IF;
END
$$;

-- === 7. Verificación ========================================
-- Lista los privilegios efectivos de wms_app sobre el schema wms.
SELECT grantee, privilege_type, table_name
  FROM information_schema.role_table_grants
 WHERE grantee = 'wms_app' AND table_schema = 'wms'
 ORDER BY table_name, privilege_type;
