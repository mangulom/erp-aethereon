BEGIN;

CREATE TABLE IF NOT EXISTS finance_auxiliaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(200) NOT NULL,
    auxiliary_type VARCHAR(24) NOT NULL CHECK (auxiliary_type IN ('customer','supplier','employee','user','other')),
    tax_id VARCHAR(24),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    email VARCHAR(320),
    phone VARCHAR(40),
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT finance_auxiliaries_company_code_unique UNIQUE(company_id,code)
);
CREATE INDEX IF NOT EXISTS ix_finance_auxiliaries_company_type ON finance_auxiliaries(company_id,auxiliary_type,is_active);
CREATE INDEX IF NOT EXISTS ix_finance_auxiliaries_tax_id ON finance_auxiliaries(company_id,tax_id);

ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS auxiliary_id UUID REFERENCES finance_auxiliaries(id) ON DELETE RESTRICT;
ALTER TABLE journal_entry_lines ADD COLUMN IF NOT EXISTS auxiliary_id UUID REFERENCES finance_auxiliaries(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS ix_finance_documents_auxiliary ON finance_documents(company_id,auxiliary_id,status);
CREATE INDEX IF NOT EXISTS ix_journal_lines_auxiliary ON journal_entry_lines(auxiliary_id);

COMMIT;
