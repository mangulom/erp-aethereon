-- Incremental accounting books: diario, mayor, compras, ventas, caja, conciliación.
BEGIN;

-- 1️⃣ Tabla de movimientos diarios del libro diario
CREATE TABLE IF NOT EXISTS accounting_daily_journal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE RESTRICT,
    journal_date DATE NOT NULL,
    auxiliary_id UUID REFERENCES finance_auxiliaries(id) ON DELETE SET NULL,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    debit_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_adj_company_date ON accounting_daily_journal(company_id, journal_date);
CREATE INDEX IF NOT EXISTS ix_adj_auxiliary ON accounting_daily_journal(auxiliary_id);
CREATE INDEX IF NOT EXISTS ix_adj_account ON accounting_daily_journal(account_id);

-- 2️⃣ Tabla del libro mayor (general ledger)
CREATE TABLE IF NOT EXISTS accounting_general_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE RESTRICT,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    journal_date DATE NOT NULL,
    auxiliary_id UUID REFERENCES finance_auxiliaries(id) ON DELETE SET NULL,
    debit_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_adj_gl_company_account ON accounting_general_ledger(company_id, account_id);
CREATE INDEX IF NOT EXISTS ix_adj_gl_date ON accounting_general_ledger(company_id, journal_date);
CREATE INDEX IF NOT EXISTS ix_adj_gl_aux ON accounting_general_ledger(auxiliary_id);

-- 3️⃣ Tabla del registro de compras
CREATE TABLE IF NOT EXISTS accounting_purchase_journal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE RESTRICT,
    journal_date DATE NOT NULL,
    auxiliary_id UUID REFERENCES finance_auxiliaries(id) ON DELETE SET NULL,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    debit_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_adj_purchase_company_date ON accounting_purchase_journal(company_id, journal_date);
CREATE INDEX IF NOT EXISTS ix_adj_purchase_aux ON accounting_purchase_journal(auxiliary_id);

-- 4️⃣ Tabla del registro de ventas
CREATE TABLE IF NOT EXISTS accounting_sales_journal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE RESTRICT,
    journal_date DATE NOT NULL,
    auxiliary_id UUID REFERENCES finance_auxiliaries(id) ON DELETE SET NULL,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    debit_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_adj_sales_company_date ON accounting_sales_journal(company_id, journal_date);
CREATE INDEX IF NOT EXISTS ix_adj_sales_aux ON accounting_sales_journal(auxiliary_id);

-- 5️⃣ Tabla del libro de caja (efectivo y banco)
CREATE TABLE IF NOT EXISTS accounting_cash_book (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE RESTRICT,
    journal_date DATE NOT NULL,
    auxiliary_id UUID REFERENCES finance_auxiliaries(id) ON DELETE SET NULL,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    direction VARCHAR(8) NOT NULL CHECK (direction IN ('debit','credit')),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_adj_cash_company_date ON accounting_cash_book(company_id, journal_date);
CREATE INDEX IF NOT EXISTS ix_adj_cash_aux ON accounting_cash_book(auxiliary_id);

-- 6️⃣ Tabla de conciliación bancaria
CREATE TABLE IF NOT EXISTS accounting_bank_reconciliation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    bank_statement_id UUID REFERENCES finance_bank_statement_lines(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE RESTRICT,
    journal_date DATE NOT NULL,
    matched BOOLEAN NOT NULL DEFAULT FALSE,
    adjustment_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_adj_bank_stmt ON accounting_bank_reconciliation(company_id, bank_statement_id);
CREATE INDEX IF NOT EXISTS ix_adj_bank_date ON accounting_bank_reconciliation(company_id, journal_date);

COMMIT;
