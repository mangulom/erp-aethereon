-- WMS module permission catalog. Permissions are intentionally NOT assigned to roles.
BEGIN;
INSERT INTO permissions(code,module_code,action,description) VALUES
('wms.materiales.ver','wms.materiales','ver','Consultar insumos/materiales WMS'),
('wms.materiales.crear','wms.materiales','crear','Crear insumos/materiales WMS'),
('wms.materiales.editar','wms.materiales','editar','Editar insumos/materiales WMS'),
('wms.materiales.eliminar','wms.materiales','eliminar','Desactivar insumos/materiales WMS'),
('wms.inventario.ver','wms.inventario','ver','Consultar existencias, movimientos y almacenes'),
('wms.inventario.operar','wms.inventario','operar','Registrar movimientos de inventario'),
('wms.inventario.aprobar','wms.inventario','aprobar','Aprobar ajustes y conteos'),
('wms.lotes.ver','wms.lotes','ver','Consultar lotes y vencimientos'),
('wms.lotes.operar','wms.lotes','operar','Crear/actualizar lotes'),
('wms.recepciones.ver','wms.recepciones','ver','Consultar recepciones'),
('wms.recepciones.operar','wms.recepciones','operar','Crear y procesar recepciones'),
('wms.despachos.ver','wms.despachos','ver','Consultar despachos'),
('wms.despachos.operar','wms.despachos','operar','Crear y procesar despachos/picking'),
('wms.matpel.ver','wms.matpel','ver','Consultar MATPEL/IQBF'),
('wms.matpel.operar','wms.matpel','operar','Registrar operaciones MATPEL/IQBF'),
('wms.integraciones.ver','wms.integraciones','ver','Consultar estado de integraciones'),
('wms.integraciones.operar','wms.integraciones','operar','Ejecutar sincronizaciones/reintentos'),
('wms.reportes.ver','wms.reportes','ver','Consultar reportes WMS'),
('wms.usuarios.administrar','wms.usuarios','administrar','Administrar usuarios y permisos WMS'),
('wms.configuracion.administrar','wms.configuracion','administrar','Administrar configuración WMS')
ON CONFLICT(code) DO NOTHING;
COMMIT;
