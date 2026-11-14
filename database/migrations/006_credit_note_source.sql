BEGIN;
ALTER TABLE finance_documents ADD COLUMN IF NOT EXISTS related_document_id UUID REFERENCES finance_documents(id) ON DELETE RESTRICT;
COMMIT;
