-- ============================================================
-- NEON: fijar search_path del role para que persista en el pooler
-- El pooler de Neon resetea SET search_path entre queries, así que
-- configuramos el default a nivel de ROLE (persiste siempre).
-- Conectar como neondb_owner y ejecutar:
-- ============================================================

ALTER ROLE neondb_owner SET search_path = wms, public;

-- Verificación (debe mostrar wms, public)
SHOW search_path;

-- Confirma que los datos están en wms
SELECT 'materiales' AS tabla, COUNT(*) FROM wms.materiales
UNION ALL SELECT 'almacenes', COUNT(*) FROM wms.almacenes
UNION ALL SELECT 'usuarios',  COUNT(*) FROM wms.usuarios;
