-- Initial PostgreSQL schema. Apply explicitly after creating the database.
-- Uses pgcrypto gen_random_uuid(), available in supported PostgreSQL releases.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name VARCHAR(200) NOT NULL,
    trade_name VARCHAR(200),
    tax_id VARCHAR(24),
    country_code CHAR(2) NOT NULL DEFAULT 'PE',
    default_currency CHAR(3) NOT NULL DEFAULT 'PEN',
    timezone VARCHAR(64) NOT NULL DEFAULT 'America/Lima',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT companies_tax_id_country_unique UNIQUE (country_code, tax_id),
    CONSTRAINT companies_tax_id_nonempty CHECK (tax_id IS NULL OR length(trim(tax_id)) > 0)
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    password_hash VARCHAR(512) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE,
    failed_login_attempts SMALLINT NOT NULL DEFAULT 0 CHECK (failed_login_attempts >= 0),
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(80) NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT roles_company_code_unique UNIQUE (company_id, code)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_roles_platform_code ON roles (code) WHERE company_id IS NULL;

CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(160) NOT NULL UNIQUE,
    module_code VARCHAR(80) NOT NULL,
    action VARCHAR(80) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, user_id, role_id)
);
CREATE INDEX IF NOT EXISTS ix_memberships_role_company ON memberships (role_id, company_id);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_type VARCHAR(32) NOT NULL DEFAULT 'user',
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(200),
    request_id VARCHAR(128),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_audit_events_company_occurred ON audit_events (company_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_events_actor_occurred ON audit_events (actor_user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_memberships_user_company ON memberships (user_id, company_id) WHERE is_active;

CREATE TABLE IF NOT EXISTS platform_modules (
    code VARCHAR(80) PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    group_name VARCHAR(80) NOT NULL,
    frontend_route VARCHAR(160) NOT NULL UNIQUE,
    backend_service VARCHAR(80),
    backend_base_url VARCHAR(240),
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    lifecycle_state VARCHAR(24) NOT NULL DEFAULT 'planned'
      CHECK (lifecycle_state IN ('planned', 'development', 'active', 'maintenance')),
    sort_order SMALLINT NOT NULL DEFAULT 100,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO platform_modules (code, name, group_name, frontend_route, backend_service, backend_base_url, is_enabled, lifecycle_state, sort_order) VALUES
('dashboard','Dashboard ejecutivo','General','/dashboard','platform','http://localhost:10002',TRUE,'development',10),
('ai-command','AI Command Center','Inteligencia','/ai','ai-command','http://localhost:10022',FALSE,'planned',20),
('finance','Finanzas y tesorería','Gestión financiera','/finance','finance','http://localhost:10003',FALSE,'planned',30),
('accounting','Contabilidad y tributación','Gestión financiera','/accounting','accounting','http://localhost:10004',FALSE,'planned',40),
('sales','Ventas y CRM','Operaciones','/sales','sales','http://localhost:10005',FALSE,'planned',50),
('procurement','Compras y proveedores','Operaciones','/procurement','procurement','http://localhost:10006',FALSE,'planned',60),
('inventory','Inventarios y almacenes','Operaciones','/inventory','inventory','http://localhost:10007',FALSE,'planned',70),
('logistics','Logística y distribución','Operaciones','/logistics','logistics','http://localhost:10008',FALSE,'planned',80),
('people','Recursos humanos','Personas y planta','/people','people','http://localhost:10009',FALSE,'planned',90),
('payroll','Nómina peruana','Personas y planta','/payroll','payroll','http://localhost:10010',FALSE,'planned',100),
('manufacturing','Producción y MRP','Personas y planta','/manufacturing','manufacturing','http://localhost:10011',FALSE,'planned',110),
('projects','Proyectos','Personas y planta','/projects','projects','http://localhost:10012',FALSE,'planned',120),
('maintenance','Mantenimiento y activos','Personas y planta','/maintenance','maintenance','http://localhost:10013',FALSE,'planned',130),
('quality','Calidad','Gobierno y soporte','/quality','quality','http://localhost:10014',FALSE,'planned',140),
('safety','Seguridad y riesgos','Gobierno y soporte','/safety','safety','http://localhost:10015',FALSE,'planned',150),
('legal','Legal y cumplimiento','Gobierno y soporte','/legal','legal','http://localhost:10016',FALSE,'planned',160),
('documents','Gestión documental','Gobierno y soporte','/documents','documents','http://localhost:10017',FALSE,'planned',170),
('support','Atención al cliente','Gobierno y soporte','/support','support','http://localhost:10018',FALSE,'planned',180),
('analytics','Business Intelligence','Inteligencia','/analytics','analytics','http://localhost:10019',FALSE,'planned',190),
('commerce','Comercio electrónico y POS','Canales digitales','/commerce','commerce','http://localhost:10020',FALSE,'planned',200),
('innovation','Innovación e I+D+i','Canales digitales','/innovation','innovation','http://localhost:10021',FALSE,'planned',210),
('administration','Administración','Gobierno y soporte','/administration','platform','http://localhost:10002',FALSE,'planned',220)
ON CONFLICT (code) DO NOTHING;

COMMIT;
