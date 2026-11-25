-- Budget control: CDP, commitments, payment orders (minimal)
CREATE TABLE IF NOT EXISTS budget_cdp (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    number TEXT NOT NULL,
    cdp_date DATE NOT NULL,
    line_text TEXT,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'vigente',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_budget_cdp_company ON budget_cdp(company_id);

CREATE TABLE IF NOT EXISTS budget_commitments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    number TEXT NOT NULL,
    commitment_date DATE NOT NULL,
    reference TEXT,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'comprometido',
    cdp_id UUID REFERENCES budget_cdp(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_budget_commitments_company ON budget_commitments(company_id);

CREATE TABLE IF NOT EXISTS payment_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    number TEXT NOT NULL,
    order_date DATE NOT NULL,
    payee TEXT,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'emitida',
    commitment_id UUID REFERENCES budget_commitments(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_payment_orders_company ON payment_orders(company_id);
