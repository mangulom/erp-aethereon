BEGIN;

CREATE TABLE IF NOT EXISTS cost_centers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(200) NOT NULL,
    parent_id UUID REFERENCES cost_centers(id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cost_centers_company_code_unique UNIQUE(company_id, code)
);
CREATE INDEX IF NOT EXISTS ix_cost_centers_company_active ON cost_centers(company_id, is_active);
CREATE INDEX IF NOT EXISTS ix_cost_centers_parent ON cost_centers(parent_id);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(40) NOT NULL,
    name VARCHAR(200) NOT NULL,
    start_date DATE,
    end_date DATE,
    budget_amount NUMERIC(14,4) NOT NULL DEFAULT 0,
    status VARCHAR(24) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'suspended', 'cancelled')),
    manager_name VARCHAR(150),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT projects_company_code_unique UNIQUE(company_id, code)
);
CREATE INDEX IF NOT EXISTS ix_projects_company_status ON projects(company_id, status);

ALTER TABLE journal_entry_lines ADD COLUMN IF NOT EXISTS cost_center_id UUID REFERENCES cost_centers(id) ON DELETE RESTRICT;
ALTER TABLE journal_entry_lines ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS ix_journal_lines_cost_center ON journal_entry_lines(cost_center_id);
CREATE INDEX IF NOT EXISTS ix_journal_lines_project ON journal_entry_lines(project_id);

ALTER TABLE finance_document_lines ADD COLUMN IF NOT EXISTS cost_center_id UUID REFERENCES cost_centers(id) ON DELETE RESTRICT;
ALTER TABLE finance_document_lines ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS ix_doc_lines_cost_center ON finance_document_lines(cost_center_id);
CREATE INDEX IF NOT EXISTS ix_doc_lines_project ON finance_document_lines(project_id);

COMMIT;
