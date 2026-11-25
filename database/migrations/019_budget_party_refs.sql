-- Add supplier/beneficiary references to budget tables
ALTER TABLE budget_commitments
  ADD COLUMN IF NOT EXISTS supplier_id UUID REFERENCES finance_auxiliaries(id);

ALTER TABLE payment_orders
  ADD COLUMN IF NOT EXISTS supplier_id UUID REFERENCES finance_auxiliaries(id);

CREATE INDEX IF NOT EXISTS idx_budget_commitments_supplier ON budget_commitments(supplier_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_supplier ON payment_orders(supplier_id);
