-- Registros de ejemplo para flujo Presupuesto (CDP -> Compromiso -> Orden de pago)
-- Requiere: seed_minimo_flujo_presupuesto.sql aplicado y migraciones 017-022.
-- Ejecutar: psql -h localhost -p 15432 -U postgres -d aethereon_erp -f "D:\WorkSpace\ERPAethereon\database\seeds\seed_ejemplo_flujo_presupuesto.sql"

DO $$
DECLARE
  v_company_id UUID;
  v_supplier_id UUID;
  v_bank_account_id UUID;
  v_budget_id UUID;
  v_cdp_id UUID;
  v_commit_id UUID;
BEGIN
  SELECT id INTO v_company_id FROM companies ORDER BY created_at LIMIT 1;
  IF v_company_id IS NULL THEN
    RAISE EXCEPTION 'No hay empresa.';
  END IF;

  SELECT id INTO v_supplier_id FROM finance_auxiliaries WHERE company_id = v_company_id AND code = 'PROV-001' LIMIT 1;
  SELECT id INTO v_bank_account_id FROM finance_bank_accounts WHERE company_id = v_company_id AND account_name = 'Cuenta Operativa BCP' LIMIT 1;
  SELECT id INTO v_budget_id FROM budgets WHERE company_id = v_company_id ORDER BY created_at DESC LIMIT 1;

  IF v_supplier_id IS NULL OR v_bank_account_id IS NULL OR v_budget_id IS NULL THEN
    RAISE EXCEPTION 'Faltan datos base (proveedor PROV-001, cuenta bancaria BCP o presupuesto). Ejecuta seed_minimo_flujo_presupuesto.sql primero.';
  END IF;

  -- CDP ejemplo
  INSERT INTO budget_cdp (company_id, number, cdp_date, line_text, requester_area, amount, status)
  VALUES (v_company_id, 'CDP-2026-001', CURRENT_DATE, '2.3.1.01 Servicios', 'Logística', 1000.00, 'vigente')
  ON CONFLICT DO NOTHING
  RETURNING id INTO v_cdp_id;

  IF v_cdp_id IS NULL THEN
    SELECT id INTO v_cdp_id FROM budget_cdp WHERE company_id = v_company_id AND number = 'CDP-2026-001' LIMIT 1;
  END IF;

  -- Compromiso ejemplo
  INSERT INTO budget_commitments (company_id, number, commitment_date, reference, amount, status, cdp_id, supplier_id)
  VALUES (v_company_id, 'COMP-2026-001', CURRENT_DATE, 'OC-001', 1000.00, 'comprometido', v_cdp_id, v_supplier_id)
  ON CONFLICT DO NOTHING
  RETURNING id INTO v_commit_id;

  IF v_commit_id IS NULL THEN
    SELECT id INTO v_commit_id FROM budget_commitments WHERE company_id = v_company_id AND number = 'COMP-2026-001' LIMIT 1;
  END IF;

  -- Orden de pago ejemplo (emitida)
  INSERT INTO payment_orders (company_id, number, order_date, payee, amount, status, commitment_id, supplier_id, bank_account_id)
  VALUES (v_company_id, 'OP-2026-001', CURRENT_DATE, 'Proveedor Demo SAC', 1000.00, 'emitida', v_commit_id, v_supplier_id, v_bank_account_id)
  ON CONFLICT DO NOTHING;

  RAISE NOTICE 'Seed ejemplo creado: CDP-2026-001, COMP-2026-001, OP-2026-001 (empresa %).', v_company_id;
END $$;
