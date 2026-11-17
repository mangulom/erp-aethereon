BEGIN;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS is_group BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE accounts parent SET is_group=TRUE WHERE EXISTS(SELECT 1 FROM accounts child WHERE child.parent_id=parent.id);
COMMIT;
