-- Auditable, idempotent bridge between external WMS events and ERP accounting.
-- This migration does not post any journal entries or assume valuation mappings.
BEGIN;

CREATE TABLE IF NOT EXISTS wms_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    integration_code TEXT NOT NULL DEFAULT 'WMS',
    external_base_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    inventory_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    offset_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    expense_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    valuation_method TEXT CHECK (valuation_method IS NULL OR valuation_method IN ('fifo','weighted_average','specific')),
    currency CHAR(3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(company_id, integration_code)
);

CREATE TABLE IF NOT EXISTS wms_sync_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id UUID NOT NULL REFERENCES wms_integrations(id) ON DELETE RESTRICT,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    external_event_id TEXT NOT NULL,
    external_event_type TEXT NOT NULL,
    external_document_id TEXT,
    external_document_number TEXT,
    occurred_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received' CHECK(status IN ('received','preview','blocked','posted','ignored','failed')),
    block_reason TEXT,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    UNIQUE(integration_id, external_event_id)
);
CREATE INDEX IF NOT EXISTS ix_wms_sync_events_company_status ON wms_sync_events(company_id,status,received_at DESC);
CREATE INDEX IF NOT EXISTS ix_wms_sync_events_journal ON wms_sync_events(journal_entry_id);

CREATE TABLE IF NOT EXISTS wms_sync_event_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES wms_sync_events(id) ON DELETE CASCADE,
    external_line_id TEXT,
    external_material_id TEXT,
    material_code TEXT,
    material_description TEXT,
    quantity NUMERIC(20,6),
    unit_of_measure TEXT,
    unit_cost NUMERIC(20,6),
    currency CHAR(3),
    external_warehouse_id TEXT,
    external_location_id TEXT,
    external_lot_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_wms_sync_event_lines_event ON wms_sync_event_lines(event_id);

COMMIT;
