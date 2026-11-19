BEGIN;

CREATE TABLE IF NOT EXISTS accounting_book_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    book_code VARCHAR(10) NOT NULL,
    book_name VARCHAR(150) NOT NULL,
    ple_code VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT accounting_book_company_code_unique UNIQUE(company_id, book_code)
);

CREATE TABLE IF NOT EXISTS purchase_register_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_period_id UUID REFERENCES fiscal_periods(id) ON DELETE RESTRICT,
    document_id UUID REFERENCES finance_documents(id) ON DELETE SET NULL,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    cuo VARCHAR(40) NOT NULL,
    issue_date DATE NOT NULL,
    due_date DATE,
    voucher_type VARCHAR(10) NOT NULL DEFAULT '01',
    series VARCHAR(20) NOT NULL,
    voucher_number VARCHAR(30) NOT NULL,
    supplier_id_type VARCHAR(10) NOT NULL DEFAULT '6',
    supplier_tax_id VARCHAR(24) NOT NULL,
    supplier_name VARCHAR(200) NOT NULL,
    taxable_base NUMERIC(14,4) NOT NULL DEFAULT 0,
    igv_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    exempt_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    unaffected_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    isc_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    icbper_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    other_taxes NUMERIC(14,4) NOT NULL DEFAULT 0,
    total_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'PEN',
    exchange_rate NUMERIC(10,4) NOT NULL DEFAULT 1.0,
    detraction_date DATE,
    detraction_constancy VARCHAR(40),
    retention_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    operation_status VARCHAR(10) NOT NULL DEFAULT '1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_purchase_reg_company_period ON purchase_register_entries(company_id, fiscal_period_id);
CREATE INDEX IF NOT EXISTS ix_purchase_reg_voucher ON purchase_register_entries(company_id, voucher_type, series, voucher_number);

CREATE TABLE IF NOT EXISTS sales_register_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_period_id UUID REFERENCES fiscal_periods(id) ON DELETE RESTRICT,
    document_id UUID REFERENCES finance_documents(id) ON DELETE SET NULL,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    cuo VARCHAR(40) NOT NULL,
    issue_date DATE NOT NULL,
    due_date DATE,
    voucher_type VARCHAR(10) NOT NULL DEFAULT '01',
    series VARCHAR(20) NOT NULL,
    voucher_number VARCHAR(30) NOT NULL,
    customer_id_type VARCHAR(10) NOT NULL DEFAULT '6',
    customer_tax_id VARCHAR(24) NOT NULL,
    customer_name VARCHAR(200) NOT NULL,
    export_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    taxable_base NUMERIC(14,4) NOT NULL DEFAULT 0,
    discount_base NUMERIC(14,4) NOT NULL DEFAULT 0,
    igv_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    discount_igv NUMERIC(14,4) NOT NULL DEFAULT 0,
    exempt_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    unaffected_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    isc_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    icbper_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    other_taxes NUMERIC(14,4) NOT NULL DEFAULT 0,
    total_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'PEN',
    exchange_rate NUMERIC(10,4) NOT NULL DEFAULT 1.0,
    operation_status VARCHAR(10) NOT NULL DEFAULT '1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sales_reg_company_period ON sales_register_entries(company_id, fiscal_period_id);
CREATE INDEX IF NOT EXISTS ix_sales_reg_voucher ON sales_register_entries(company_id, voucher_type, series, voucher_number);

CREATE TABLE IF NOT EXISTS closing_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE CASCADE,
    step_number INT NOT NULL,
    step_name VARCHAR(150) NOT NULL,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_closing_entries_fy ON closing_entries(company_id, fiscal_year_id);

CREATE TABLE IF NOT EXISTS opening_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    auxiliary_id UUID REFERENCES finance_auxiliaries(id) ON DELETE SET NULL,
    debit NUMERIC(14,4) NOT NULL DEFAULT 0,
    credit NUMERIC(14,4) NOT NULL DEFAULT 0,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_opening_balances_fy_acc ON opening_balances(company_id, fiscal_year_id, account_id);

COMMIT;
