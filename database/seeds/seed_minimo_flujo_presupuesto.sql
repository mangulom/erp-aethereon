-- Seed mínimo para probar flujo Presupuesto/Contabilidad en Sophia ERP
-- Requiere: empresa creada, migraciones aplicadas (incl. 017-021).
-- Ejecutar: psql -h localhost -p 15432 -U postgres -d aethereon_erp -f "D:\WorkSpace\ERPAethereon\database\seeds\seed_minimo_flujo_presupuesto.sql"

DO $$
DECLARE
  v_company_id UUID;
  v_acc_banco UUID;
  v_bank_id UUID;
  v_supplier_id UUID;
  v_fy_id UUID;
  v_period_id UUID;
  v_year INT := EXTRACT(YEAR FROM CURRENT_DATE)::int;
  v_month INT := EXTRACT(MONTH FROM CURRENT_DATE)::int;
BEGIN
  SELECT id INTO v_company_id FROM companies ORDER BY created_at LIMIT 1;
  IF v_company_id IS NULL THEN
    RAISE EXCEPTION 'No hay empresas en la tabla companies. Crea una empresa primero.';
  END IF;

  RAISE NOTICE 'Usando company_id: %', v_company_id;

  -- 1) Catálogo de bancos
  INSERT INTO finance_banks (company_id, code, name, is_active)
  SELECT v_company_id, 'BCP', 'Banco de Crédito del Perú', true
  WHERE NOT EXISTS (SELECT 1 FROM finance_banks WHERE company_id = v_company_id AND code = 'BCP');

  SELECT id INTO v_bank_id FROM finance_banks WHERE company_id = v_company_id AND code = 'BCP' LIMIT 1;

  -- 2) Cuentas contables mínimas (según esquema real de accounts)
  INSERT INTO accounts (company_id, code, name, account_type, account_subtype, parent_id, currency, allow_posting, is_active)
  SELECT v_company_id, '63', 'Gastos de servicios prestados por terceros', 'expense', 'expense', NULL, 'PEN', false, true
  WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE company_id = v_company_id AND code = '63');

  INSERT INTO accounts (company_id, code, name, account_type, account_subtype, parent_id, currency, allow_posting, is_active)
  SELECT v_company_id, '634', 'Servicios de terceros', 'expense', 'expense', NULL, 'PEN', true, true
  WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE company_id = v_company_id AND code = '634');

  INSERT INTO accounts (company_id, code, name, account_type, account_subtype, parent_id, currency, allow_posting, is_active)
  SELECT v_company_id, '42', 'Cuentas por pagar comerciales', 'liability', 'payable', NULL, 'PEN', false, true
  WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE company_id = v_company_id AND code = '42');

  INSERT INTO accounts (company_id, code, name, account_type, account_subtype, parent_id, currency, allow_posting, is_active)
  SELECT v_company_id, '4212', 'Facturas por pagar', 'liability', 'payable', NULL, 'PEN', true, true
  WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE company_id = v_company_id AND code = '4212');

  INSERT INTO accounts (company_id, code, name, account_type, account_subtype, parent_id, currency, allow_posting, is_active)
  SELECT v_company_id, '104', 'Cuentas corrientes', 'asset', 'bank', NULL, 'PEN', false, true
  WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE company_id = v_company_id AND code = '104');

  INSERT INTO accounts (company_id, code, name, account_type, account_subtype, parent_id, currency, allow_posting, is_active)
  SELECT v_company_id, '1041', 'Cuentas corrientes operativas', 'asset', 'bank', NULL, 'PEN', true, true
  WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE company_id = v_company_id AND code = '1041');

  SELECT id INTO v_acc_banco FROM accounts WHERE company_id = v_company_id AND code = '1041' LIMIT 1;

  -- 3) Cuenta bancaria de tesorería vinculada a 1041
  IF v_acc_banco IS NOT NULL THEN
    INSERT INTO finance_bank_accounts (company_id, account_id, bank_id, bank_name, account_name, account_number_masked, currency, is_active)
    SELECT v_company_id, v_acc_banco, v_bank_id, 'BCP', 'Cuenta Operativa BCP', '****1234', 'PEN', true
    WHERE NOT EXISTS (SELECT 1 FROM finance_bank_accounts WHERE company_id = v_company_id AND account_name = 'Cuenta Operativa BCP');
  END IF;

  -- 4) Auxiliar proveedor de ejemplo
  INSERT INTO finance_auxiliaries (company_id, auxiliary_type, code, name, tax_id, email, is_active)
  SELECT v_company_id, 'supplier', 'PROV-001', 'Proveedor Demo SAC', '20123456789', 'proveedor@demo.com', true
  WHERE NOT EXISTS (SELECT 1 FROM finance_auxiliaries WHERE company_id = v_company_id AND code = 'PROV-001');

  SELECT id INTO v_supplier_id FROM finance_auxiliaries WHERE company_id = v_company_id AND code = 'PROV-001' LIMIT 1;

  -- 5) Ejercicio y periodo fiscal abiertos (año actual)
  INSERT INTO fiscal_years (company_id, name, start_date, end_date, is_closed)
  SELECT v_company_id, 'Ejercicio ' || v_year::text,
         make_date(v_year,1,1), make_date(v_year,12,31), false
  WHERE NOT EXISTS (SELECT 1 FROM fiscal_years WHERE company_id = v_company_id AND start_date = make_date(v_year,1,1));

  SELECT id INTO v_fy_id FROM fiscal_years WHERE company_id = v_company_id AND start_date = make_date(v_year,1,1) LIMIT 1;

  IF v_fy_id IS NOT NULL THEN
    INSERT INTO fiscal_periods (fiscal_year_id, code, name, start_date, end_date, is_closed, sort_order)
    SELECT v_fy_id,
           lpad(v_month::text, 2, '0'),
           to_char(make_date(v_year, v_month, 1), 'TMMonth YYYY'),
           date_trunc('month', make_date(v_year, v_month, 1))::date,
           (date_trunc('month', make_date(v_year, v_month, 1)) + interval '1 month - 1 day')::date,
           false,
           v_month
    WHERE NOT EXISTS (SELECT 1 FROM fiscal_periods WHERE fiscal_year_id = v_fy_id AND sort_order = v_month);
  END IF;

  -- 6) Presupuesto/Apropiación inicial (usa fiscal_year_id)
  IF v_fy_id IS NOT NULL THEN
    INSERT INTO budgets (company_id, fiscal_year_id, name, description, currency, status)
    SELECT v_company_id, v_fy_id, 'Presupuesto ' || v_year::text, 'Presupuesto seed mínimo', 'PEN', 'approved'
    WHERE NOT EXISTS (SELECT 1 FROM budgets WHERE company_id = v_company_id AND fiscal_year_id = v_fy_id);
  END IF;

  RAISE NOTICE 'Seed mínimo completado (cuentas 634,4212,1041, banco tesorería, proveedor PROV-001, FY/periodo y presupuesto).';
END $$;
