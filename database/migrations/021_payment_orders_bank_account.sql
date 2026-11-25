-- Link payment order to treasury bank account for automatic posting
ALTER TABLE payment_orders
  ADD COLUMN IF NOT EXISTS bank_account_id UUID REFERENCES finance_bank_accounts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_payment_orders_bank_account ON payment_orders(bank_account_id);
