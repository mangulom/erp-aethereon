BEGIN;

CREATE TABLE IF NOT EXISTS invoice_series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_type_code VARCHAR(10) NOT NULL,
    series VARCHAR(10) NOT NULL,
    description VARCHAR(100),
    current_correlative INT NOT NULL DEFAULT 0,
    next_correlative INT NOT NULL DEFAULT 1,
    is_electronic BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT invoice_series_company_type_series_unique UNIQUE(company_id, document_type_code, series)
);
CREATE INDEX IF NOT EXISTS ix_invoice_series_lookup ON invoice_series(company_id, document_type_code, is_active);

COMMIT;
