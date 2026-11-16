-- Modificación de importacion_subitems para ampliar columnas de sufijos
-- Ejecutar después de crear las tablas con tesys-infra/db/schema/04_tables_importation.sql

-- Ampliar columnas que pueden exceder 50 caracteres
-- Ejemplos de valores largos encontrados:
--   marca (AA): "GUANG DONG XINBAO ELECTRICAL APPLIANCES HOLDINGS CO., LTD." - 58 caracteres
--   modelo (AB): "PN:2375101 R//TDI PN:140577 REV C1/SPS5692/GE PN:23751010 REV6 // SN:TDC1533 AC13638." - 85 caracteres
--   version (AI): "PN: D3145T//MX165CT INSERT//46 309300G3//SOLARIX 350 BRIGHTSPEED//2199077 7//SN:199630BI5//230394BC9." - 101 caracteres
--   presentacion (AJ): "4 BOTELLAS X 450 ML DE SOLUCION DE LAVADO Y 4 JUEGOS DE INTERVENCION DEL USUARIO D 1A 2 ML X 4 D1B 50MG X 4 C 2ML X 4 HCT 2ML X 4" - 129 caracteres
--   vencimiento_original (AR): "06/09/2029  14/08/2029  07/09/2029  02/10/2029" - 46 caracteres

ALTER TABLE importacion_subitems ALTER COLUMN marca TYPE VARCHAR(150);
ALTER TABLE importacion_subitems ALTER COLUMN modelo TYPE VARCHAR(150);
ALTER TABLE importacion_subitems ALTER COLUMN version TYPE VARCHAR(150);
ALTER TABLE importacion_subitems ALTER COLUMN presentacion TYPE VARCHAR(150);
ALTER TABLE importacion_subitems ALTER COLUMN vencimiento_original TYPE VARCHAR(100);

COMMENT ON COLUMN importacion_subitems.vencimiento_original IS
'Sufijo AR (texto original - puede contener rangos o multiples fechas de vencimiento para diferentes lotes)';

-- Verificar el cambio
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'importacion_subitems'
  AND column_name = 'vencimiento_original';
