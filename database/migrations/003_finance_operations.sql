-- Incremental finance operations: explicit account subtypes and source documents.
BEGIN;

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS account_subtype VARCHAR(32);
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS cash_flow_category VARCHAR(16);
DO $$ BEGIN
    ALTER TABLE accounts ADD CONSTRAINT accounts_subtype_check
      CHECK (account_subtype IS NULL OR account_subtype IN ('cash','bank','receivable','payable','inventory','fixed_asset','tax','equity','income','expense'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE accounts ADD CONSTRAINT accounts_cash_flow_category_check
      CHECK (cash_flow_category IS NULL OR cash_flow_category IN ('operating','investing','financing'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS finance_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE RESTRICT,
    fiscal_period_id UUID REFERENCES fiscal_periods(id) ON DELETE SET NULL,
    document_type VARCHAR(24) NOT NULL CHECK (document_type IN ('sales_invoice','purchase_bill','sales_credit_note','purchase_credit_note')),
    document_number VARCHAR(60) NOT NULL,
    party_name VARCHAR(200) NOT NULL,
    party_tax_id VARCHAR(24),
    issue_date DATE NOT NULL,
    due_date DATE,
    currency CHAR(3) NOT NULL DEFAULT 'PEN',
    exchange_rate NUMERIC(18,6) NOT NULL DEFAULT 1 CHECK (exchange_rate > 0),
    subtotal NUMERIC(18,2) NOT NULL DEFAULT 0,
    tax_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    total NUMERIC(18,2) NOT NULL DEFAULT 0,
    status VARCHAR(24) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','posted','void')),
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    control_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    tax_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    notes TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    posted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    posted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT finance_documents_company_number_unique UNIQUE (company_id, document_type, document_number),
    CONSTRAINT finance_documents_due_after_issue CHECK (due_date IS NULL OR due_date >= issue_date),
    CONSTRAINT finance_documents_totals CHECK (subtotal >= 0 AND tax_total >= 0 AND total >= 0 AND abs(total - subtotal - tax_total) < 0.01)
);
CREATE INDEX IF NOT EXISTS ix_finance_documents_company_dates ON finance_documents (company_id, issue_date DESC);
CREATE INDEX IF NOT EXISTS ix_finance_documents_status_due ON finance_documents (company_id, status, due_date);

CREATE TABLE IF NOT EXISTS finance_document_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES finance_documents(id) ON DELETE CASCADE,
    line_number SMALLINT NOT NULL,
    description VARCHAR(300) NOT NULL,
    quantity NUMERIC(18,4) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price NUMERIC(18,4) NOT NULL CHECK (unit_price >= 0),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    tax_rate_id UUID REFERENCES tax_rates(id) ON DELETE RESTRICT,
    tax_rate NUMERIC(7,4) NOT NULL DEFAULT 0 CHECK (tax_rate >= 0),
    net_amount NUMERIC(18,2) NOT NULL CHECK (net_amount >= 0),
    tax_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT finance_document_lines_number_unique UNIQUE (document_id, line_number)
);
CREATE INDEX IF NOT EXISTS ix_finance_document_lines_document ON finance_document_lines (document_id, line_number);

CREATE TABLE IF NOT EXISTS finance_document_settlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES finance_documents(id) ON DELETE RESTRICT,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    settled_at DATE NOT NULL,
    reference VARCHAR(120),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_finance_document_settlements_document ON finance_document_settlements (document_id, settled_at);

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
