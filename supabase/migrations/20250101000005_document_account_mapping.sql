BEGIN;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS control_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS tax_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS related_document_id UUID REFERENCES finance_documents(id) ON DELETE RESTRICT;
COMMIT;
