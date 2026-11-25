-- Master table for bank entities
CREATE TABLE IF NOT EXISTS finance_banks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(30),
    name VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_finance_banks_company ON finance_banks(company_id, is_active);

ALTER TABLE finance_bank_accounts
  ADD COLUMN IF NOT EXISTS bank_id UUID REFERENCES finance_banks(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_finance_bank_accounts_bank ON finance_bank_accounts(bank_id);
