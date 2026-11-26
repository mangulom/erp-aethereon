-- Renombra las 2 plantas reales que existen en tu base (id=1 codigo 8000,
-- id=2 codigo 8101) a los nombres nuevos, e inserta las 2 que faltan para
-- llegar a los 4 almacenes: Central, San Borja, Jesús María, Pueblo Libre.
--
-- Ejecutar con: psql -U postgres -h localhost -p 15432 -d wms -f sql/renombrar_plantas.sql
--
-- Si los acentos salen mal en la consola de psql, es solo un tema de
-- encoding del cliente (corre \encoding utf8 antes, o ignóralo: el dato
-- se guarda bien en la base mientras el server esté en UTF8).

SET search_path TO wms, public;
SET client_encoding TO 'UTF8';

-- Renombra las 2 existentes por id (más seguro que por codigo/nombre,
-- que ya vimos que no coincidían con lo esperado).
UPDATE wms.plantas SET codigo = 'ALM_CENTRAL',   nombre = 'Almacén Central',    direccion = 'Lima, Perú' WHERE id = 1;
UPDATE wms.plantas SET codigo = 'ALM_SAN_BORJA', nombre = 'Almacén San Borja',  direccion = 'San Borja, Lima' WHERE id = 2;

-- Inserta las 2 que faltan (solo si no existen ya por codigo).
INSERT INTO wms.plantas (codigo, nombre, direccion, activa)
SELECT 'ALM_JESUS_MARIA', 'Almacén Jesús María', 'Jesús María, Lima', true
WHERE NOT EXISTS (SELECT 1 FROM wms.plantas WHERE codigo = 'ALM_JESUS_MARIA');

INSERT INTO wms.plantas (codigo, nombre, direccion, activa)
SELECT 'ALM_PUEBLO_LIBRE', 'Almacén Pueblo Libre', 'Pueblo Libre, Lima', true
WHERE NOT EXISTS (SELECT 1 FROM wms.plantas WHERE codigo = 'ALM_PUEBLO_LIBRE');

-- Verifica el resultado:
SELECT id, codigo, nombre, direccion, activa FROM wms.plantas ORDER BY id;
