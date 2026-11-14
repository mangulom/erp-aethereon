BEGIN;
CREATE TABLE IF NOT EXISTS document_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(80) NOT NULL,
    name VARCHAR(160) NOT NULL,
    category VARCHAR(80) NOT NULL,
    description TEXT,
    prefix VARCHAR(24),
    requires_tax_id BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT document_types_company_code_unique UNIQUE(company_id,code)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_document_types_global_code ON document_types(code) WHERE company_id IS NULL;
CREATE INDEX IF NOT EXISTS ix_document_types_scope_active ON document_types(company_id,is_active,category);
COMMIT;
