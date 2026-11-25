-- Add origin/requester area to budgets (Apropiación inicial)
ALTER TABLE budgets
  ADD COLUMN IF NOT EXISTS origin_area TEXT;

COMMENT ON COLUMN budgets.origin_area IS 'Area origen: finanzas, contabilidad, logistica, rrhh, general';
