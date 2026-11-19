BEGIN;

CREATE TABLE IF NOT EXISTS payment_terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(200) NOT NULL,
    days_net INT NOT NULL DEFAULT 0,
    days_discount INT NOT NULL DEFAULT 0,
    discount_rate NUMERIC(5,2) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT payment_terms_company_code_unique UNIQUE(company_id, code)
);
CREATE INDEX IF NOT EXISTS ix_payment_terms_company ON payment_terms(company_id, is_active);

CREATE TABLE IF NOT EXISTS withholding_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(200) NOT NULL,
    rate NUMERIC(5,2) NOT NULL,
    applies_to VARCHAR(20) NOT NULL CHECK (applies_to IN ('purchase', 'sale', 'both')),
    withholding_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT withholding_types_company_code_unique UNIQUE(company_id, code)
);
CREATE INDEX IF NOT EXISTS ix_withholding_types_company ON withholding_types(company_id, is_active);

ALTER TABLE finance_auxiliaries ADD COLUMN IF NOT EXISTS payment_term_id UUID REFERENCES payment_terms(id) ON DELETE SET NULL;
ALTER TABLE finance_auxiliaries ADD COLUMN IF NOT EXISTS credit_limit NUMERIC(14,4) NOT NULL DEFAULT 0;
ALTER TABLE finance_auxiliaries ADD COLUMN IF NOT EXISTS credit_days INT NOT NULL DEFAULT 0;

ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS payment_term_id UUID REFERENCES payment_terms(id) ON DELETE SET NULL;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS withholding_type_id UUID REFERENCES withholding_types(id) ON DELETE SET NULL;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS withholding_amount NUMERIC(14,4) NOT NULL DEFAULT 0;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS detraction_type VARCHAR(50);
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS detraction_rate NUMERIC(5,2) NOT NULL DEFAULT 0;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS detraction_amount NUMERIC(14,4) NOT NULL DEFAULT 0;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS series VARCHAR(10);
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS correlative VARCHAR(20);

CREATE INDEX IF NOT EXISTS ix_finance_docs_series_correlative ON finance_documents(company_id, series, correlative);

COMMIT;
