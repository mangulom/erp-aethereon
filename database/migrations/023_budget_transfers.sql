-- Traslados de presupuesto entre áreas (conserva referencia al CDP original)
CREATE TABLE IF NOT EXISTS budget_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    original_cdp_id UUID,
    original_cdp_number TEXT NOT NULL,
    from_area TEXT,
    to_area TEXT NOT NULL,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    new_partida TEXT,
    new_account_code TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_budget_transfers_company ON budget_transfers(company_id);
CREATE INDEX IF NOT EXISTS idx_budget_transfers_original_cdp ON budget_transfers(original_cdp_id);
