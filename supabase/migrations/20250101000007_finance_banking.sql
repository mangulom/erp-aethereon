BEGIN;
CREATE TABLE IF NOT EXISTS finance_bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    bank_name VARCHAR(160) NOT NULL,
    account_name VARCHAR(160) NOT NULL,
    account_number_masked VARCHAR(40),
    currency CHAR(3) NOT NULL DEFAULT 'PEN',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT finance_bank_accounts_company_name_unique UNIQUE (company_id, account_name)
);
CREATE INDEX IF NOT EXISTS ix_finance_bank_accounts_company ON finance_bank_accounts(company_id,is_active);

CREATE TABLE IF NOT EXISTS finance_bank_statement_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_account_id UUID NOT NULL REFERENCES finance_bank_accounts(id) ON DELETE CASCADE,
    transaction_date DATE NOT NULL,
    reference VARCHAR(160),
    description VARCHAR(300) NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'unmatched' CHECK (status IN ('unmatched','matched','ignored')),
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT finance_bank_statement_ref_unique UNIQUE(bank_account_id,transaction_date,reference,amount)
);
CREATE INDEX IF NOT EXISTS ix_finance_bank_statement_reconcile ON finance_bank_statement_lines(bank_account_id,status,transaction_date);
COMMIT;
