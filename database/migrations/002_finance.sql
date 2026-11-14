-- Finance module schema. Apply after 001_identity.sql.
-- Uses pgcrypto gen_random_uuid(), available in supported PostgreSQL releases.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Fiscal years
CREATE TABLE IF NOT EXISTS fiscal_years (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fiscal_years_company_name_unique UNIQUE (company_id, name),
    CONSTRAINT fiscal_years_dates_order CHECK (end_date >= start_date),
    EXCLUDE USING gist (
        company_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    )
);
CREATE INDEX IF NOT EXISTS ix_fiscal_years_company_dates ON fiscal_years (company_id, start_date);

-- Fiscal periods (months/quarters within a fiscal year)
CREATE TABLE IF NOT EXISTS fiscal_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE CASCADE,
    code VARCHAR(16) NOT NULL,
    name VARCHAR(80) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    closed_at TIMESTAMPTZ,
    sort_order SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fiscal_periods_year_code_unique UNIQUE (fiscal_year_id, code),
    CONSTRAINT fiscal_periods_dates_order CHECK (end_date >= start_date)
);
CREATE INDEX IF NOT EXISTS ix_fiscal_periods_year_order ON fiscal_periods (fiscal_year_id, sort_order);

-- Chart of accounts (multi-company, hierarchical)
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(32) NOT NULL,
    name VARCHAR(200) NOT NULL,
    account_type VARCHAR(32) NOT NULL CHECK (account_type IN ('asset','liability','equity','revenue','expense')),
    parent_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    currency CHAR(3) NOT NULL DEFAULT 'PEN',
    allow_posting BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT accounts_company_code_unique UNIQUE (company_id, code)
);
CREATE INDEX IF NOT EXISTS ix_accounts_company_parent ON accounts (company_id, parent_id);
CREATE INDEX IF NOT EXISTS ix_accounts_company_type ON accounts (company_id, account_type);
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS account_subtype VARCHAR(32);
DO $$ BEGIN
    ALTER TABLE accounts ADD CONSTRAINT accounts_subtype_check
      CHECK (account_subtype IS NULL OR account_subtype IN ('cash','bank','receivable','payable','inventory','fixed_asset','tax','equity','income','expense'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Journal entries (asientos contables)
CREATE TABLE IF NOT EXISTS journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE RESTRICT,
    fiscal_period_id UUID REFERENCES fiscal_periods(id) ON DELETE SET NULL,
    entry_number VARCHAR(40) NOT NULL,
    entry_date DATE NOT NULL,
    reference VARCHAR(200),
    description TEXT,
    status VARCHAR(24) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','posted','reversed')),
    currency CHAR(3) NOT NULL DEFAULT 'PEN',
    exchange_rate NUMERIC(18,6) NOT NULL DEFAULT 1.000000,
    total_debit NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_credit NUMERIC(18,2) NOT NULL DEFAULT 0,
    posted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    posted_at TIMESTAMPTZ,
    reversed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reversed_at TIMESTAMPTZ,
    reversal_reason TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT journal_entries_company_number_unique UNIQUE (company_id, entry_number),
    CONSTRAINT journal_entries_balanced CHECK (abs(total_debit - total_credit) < 0.01)
);
CREATE INDEX IF NOT EXISTS ix_journal_entries_company_date ON journal_entries (company_id, entry_date);
CREATE INDEX IF NOT EXISTS ix_journal_entries_company_period ON journal_entries (company_id, fiscal_period_id);
CREATE INDEX IF NOT EXISTS ix_journal_entries_status ON journal_entries (company_id, status);

-- Journal entry lines (líneas de asiento)
CREATE TABLE IF NOT EXISTS journal_entry_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    line_number SMALLINT NOT NULL,
    description TEXT,
    debit_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    currency_amount NUMERIC(18,2),
    currency_code CHAR(3),
    analytical_dimension_1 VARCHAR(80),
    analytical_dimension_2 VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT journal_entry_lines_entry_line_unique UNIQUE (journal_entry_id, line_number),
    CONSTRAINT journal_entry_lines_amounts_check CHECK (
        (debit_amount > 0 AND credit_amount = 0) OR
        (debit_amount = 0 AND credit_amount > 0) OR
        (debit_amount = 0 AND credit_amount = 0)
    )
);
CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_entry ON journal_entry_lines (journal_entry_id);
CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_account ON journal_entry_lines (account_id);

-- Budgets (presupuestos)
CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    status VARCHAR(24) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','active','closed')),
    currency CHAR(3) NOT NULL DEFAULT 'PEN',
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT budgets_company_year_name_unique UNIQUE (company_id, fiscal_year_id, name)
);
CREATE INDEX IF NOT EXISTS ix_budgets_company_year ON budgets (company_id, fiscal_year_id);

-- Budget lines (líneas de presupuesto)
CREATE TABLE IF NOT EXISTS budget_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    period_id UUID REFERENCES fiscal_periods(id) ON DELETE SET NULL,
    planned_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT budget_lines_budget_account_period_unique UNIQUE (budget_id, account_id, period_id)
);
CREATE INDEX IF NOT EXISTS ix_budget_lines_budget ON budget_lines (budget_id);
CREATE INDEX IF NOT EXISTS ix_budget_lines_account ON budget_lines (account_id);

-- Tax rates (tasas de impuesto)
CREATE TABLE IF NOT EXISTS tax_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(120) NOT NULL,
    rate NUMERIC(7,4) NOT NULL CHECK (rate >= 0),
    tax_type VARCHAR(32) NOT NULL CHECK (tax_type IN ('vat','withholding','excise','other')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    valid_from DATE NOT NULL,
    valid_until DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tax_rates_company_code_unique UNIQUE (company_id, code)
);
CREATE INDEX IF NOT EXISTS ix_tax_rates_company_active ON tax_rates (company_id, is_active);

-- Currency exchange rates
CREATE TABLE IF NOT EXISTS exchange_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    from_currency CHAR(3) NOT NULL,
    to_currency CHAR(3) NOT NULL,
    rate_date DATE NOT NULL,
    rate NUMERIC(18,6) NOT NULL CHECK (rate > 0),
    source VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT exchange_rates_company_pair_date_unique UNIQUE (company_id, from_currency, to_currency, rate_date)
);
CREATE INDEX IF NOT EXISTS ix_exchange_rates_company_date ON exchange_rates (company_id, rate_date);

-- Finance operational documents (customer invoices, supplier bills, credit notes).
-- Draft documents are editable; posted documents retain an immutable audit trail.
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

-- Update platform_modules for finance and accounting with correct ports
UPDATE platform_modules SET
    backend_base_url = 'http://localhost:18003',
    lifecycle_state = 'development',
    is_enabled = TRUE
WHERE code = 'finance';

UPDATE platform_modules SET
    backend_base_url = 'http://localhost:18004',
    lifecycle_state = 'planned',
    is_enabled = FALSE
WHERE code = 'accounting';

COMMIT;
