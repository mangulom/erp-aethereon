BEGIN;

CREATE TABLE IF NOT EXISTS asset_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(200) NOT NULL,
    depreciation_method VARCHAR(30) NOT NULL DEFAULT 'straight_line' CHECK (depreciation_method IN ('straight_line', 'declining_balance', 'units_of_production')),
    useful_life_years INT NOT NULL DEFAULT 5,
    salvage_rate NUMERIC(5,2) NOT NULL DEFAULT 0,
    asset_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    accumulated_depreciation_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    depreciation_expense_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT asset_categories_company_code_unique UNIQUE(company_id, code)
);
CREATE INDEX IF NOT EXISTS ix_asset_categories_company ON asset_categories(company_id, is_active);

CREATE TABLE IF NOT EXISTS fixed_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category_id UUID REFERENCES asset_categories(id) ON DELETE RESTRICT,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    serial_number VARCHAR(100),
    location VARCHAR(150),
    acquisition_date DATE NOT NULL,
    start_depreciation_date DATE NOT NULL,
    acquisition_cost NUMERIC(14,4) NOT NULL,
    salvage_value NUMERIC(14,4) NOT NULL DEFAULT 0,
    useful_life_months INT NOT NULL DEFAULT 60,
    current_book_value NUMERIC(14,4) NOT NULL,
    accumulated_depreciation NUMERIC(14,4) NOT NULL DEFAULT 0,
    status VARCHAR(24) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'fully_depreciated', 'disposed', 'under_maintenance')),
    disposal_date DATE,
    disposal_reason TEXT,
    cost_center_id UUID REFERENCES cost_centers(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fixed_assets_company_code_unique UNIQUE(company_id, code)
);
CREATE INDEX IF NOT EXISTS ix_fixed_assets_company_status ON fixed_assets(company_id, status);
CREATE INDEX IF NOT EXISTS ix_fixed_assets_category ON fixed_assets(category_id);

CREATE TABLE IF NOT EXISTS asset_depreciation_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES fixed_assets(id) ON DELETE CASCADE,
    fiscal_period_id UUID REFERENCES fiscal_periods(id) ON DELETE RESTRICT,
    period_date DATE NOT NULL,
    depreciation_amount NUMERIC(14,4) NOT NULL,
    accumulated_before NUMERIC(14,4) NOT NULL,
    accumulated_after NUMERIC(14,4) NOT NULL,
    book_value_after NUMERIC(14,4) NOT NULL,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_asset_depr_asset ON asset_depreciation_lines(asset_id, period_date);
CREATE INDEX IF NOT EXISTS ix_asset_depr_period ON asset_depreciation_lines(fiscal_period_id);

COMMIT;
