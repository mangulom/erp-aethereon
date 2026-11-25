-- Seed: Proveedores y Clientes (finance_auxiliaries)
-- Reemplaza el company_id si es necesario. Ejemplo usa el company_id visto en logs.
-- Ejecutar contra tu BD local (ej: aethereon_erp)

DO $$
DECLARE
  v_company_id UUID := '383c423b-0618-49f5-98f3-e1b0d828681d';
BEGIN
  -- Clientes
  INSERT INTO finance_auxiliaries (company_id, code, name, auxiliary_type, tax_id, email, phone, address, is_active)
  VALUES
    (v_company_id, 'CLI-001', 'Cliente Demo SAC', 'customer', '20123456789', 'contacto@clientedemo.pe', '01-5550001', 'Av. Demo 123, Lima', true),
    (v_company_id, 'CLI-002', 'Cliente General EIRL', 'customer', '20987654321', 'ventas@clientegral.pe', '01-5550002', 'Jr. General 456, Lima', true)
  ON CONFLICT (company_id, code) DO NOTHING;

  -- Proveedores
  INSERT INTO finance_auxiliaries (company_id, code, name, auxiliary_type, tax_id, email, phone, address, is_active)
  VALUES
    (v_company_id, 'PROV-001', 'Proveedor ABC S.A.C.', 'supplier', '20111111111', 'compras@proveedorabc.pe', '01-4440001', 'Av. Industrial 100, Lima', true),
    (v_company_id, 'PROV-002', 'Servicios Logísticos XYZ', 'supplier', '20222222222', 'contacto@logxyz.pe', '01-4440002', 'Calle Logística 200, Callao', true),
    (v_company_id, 'PROV-003', 'RRHH Servicios Integrales', 'supplier', '20333333333', 'rrhh@servint.pe', '01-4440003', 'Av. Personas 300, Lima', true)
  ON CONFLICT (company_id, code) DO NOTHING;
END $$;
