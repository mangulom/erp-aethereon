BEGIN;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS cash_flow_category VARCHAR(16);
DO $$ BEGIN
    ALTER TABLE accounts ADD CONSTRAINT accounts_cash_flow_category_check
      CHECK (cash_flow_category IS NULL OR cash_flow_category IN ('operating','investing','financing'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
COMMIT;
