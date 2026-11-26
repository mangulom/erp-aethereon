-- Diagnóstico: ¿en qué schema vive la tabla plantas (si es que existe)?
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name = 'plantas';

-- Lista todos los schemas disponibles en esta base:
SELECT schema_name FROM information_schema.schemata;

-- search_path actual de esta sesión:
SHOW search_path;
