-- =====================================================
-- REFACTORIZACION: Importacion Subitems - Solo JSONB
-- =====================================================
-- Este script elimina las columnas individuales de sufijos
-- y deja solo el campo sufijos_completos (JSONB) para mayor flexibilidad
--
-- RAZON DEL CAMBIO:
-- Las columnas individuales (marca, modelo, version, presentacion, etc)
-- tenian limitaciones de longitud impredecibles y duplicaban informacion
-- que ya esta en detalle_completo.
--
-- Con JSONB:
-- - Soporte para TODOS los sufijos, no solo 7 predefinidos
-- - Sin limites de longitud (JSONB maneja strings largos)
-- - Mas flexible para futuros sufijos
-- - Un solo indice GIN vs multiples columnas
--
-- CONSULTAS EQUIVALENTES:
-- Antes: WHERE marca = 'VW'
-- Ahora: WHERE sufijos_completos->>'AA' = 'VW'
--
-- Antes: WHERE modelo LIKE '%2H6853294A%'
-- Ahora: WHERE sufijos_completos->>'AB' LIKE '%2H6853294A%'
--
-- Ver: docs/NOTAS_TECNICAS.md para mas ejemplos y lista completa de sufijos
-- =====================================================

-- Verificar que el indice GIN existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'importacion_subitems'
          AND indexname = 'idx_subitems_sufijos_gin'
    ) THEN
        RAISE NOTICE 'Creando indice GIN para sufijos_completos...';
        CREATE INDEX idx_subitems_sufijos_gin ON importacion_subitems USING gin (sufijos_completos);
    ELSE
        RAISE NOTICE 'Indice GIN ya existe';
    END IF;
END $$;

-- Eliminar columnas individuales de sufijos
-- NOTA: Al eliminar columnas de la tabla padre, se eliminan automaticamente de las particiones
ALTER TABLE importacion_subitems DROP COLUMN IF EXISTS marca CASCADE;
ALTER TABLE importacion_subitems DROP COLUMN IF EXISTS modelo CASCADE;
ALTER TABLE importacion_subitems DROP COLUMN IF EXISTS codigo CASCADE;
ALTER TABLE importacion_subitems DROP COLUMN IF EXISTS version CASCADE;
ALTER TABLE importacion_subitems DROP COLUMN IF EXISTS especialidad CASCADE;
ALTER TABLE importacion_subitems DROP COLUMN IF EXISTS presentacion CASCADE;
ALTER TABLE importacion_subitems DROP COLUMN IF EXISTS vencimiento_original CASCADE;

-- Verificar estructura final
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_generated
FROM information_schema.columns
WHERE table_name = 'importacion_subitems'
ORDER BY ordinal_position;

-- Mostrar mensaje de finalizacion
DO $$
BEGIN
    RAISE NOTICE '
================================================================================
MIGRACION COMPLETADA
================================================================================

Estructura simplificada:
- detalle_completo: TEXT (campo original completo)
- sufijos_completos: JSONB (todos los sufijos parseados)

Ejemplos de consulta:

1. Buscar por marca (AA):
   SELECT * FROM importacion_subitems
   WHERE sufijos_completos->>''AA'' = ''VW'';

2. Buscar por modelo (AB) con LIKE:
   SELECT * FROM importacion_subitems
   WHERE sufijos_completos->>''AB'' LIKE ''%%%%2H6853294A%%%%'';

3. Buscar multiples sufijos:
   SELECT * FROM importacion_subitems
   WHERE sufijos_completos->>''AA'' = ''VW''
     AND sufijos_completos->>''AB'' LIKE ''%%%%Golf%%%%'';

4. Verificar si sufijo existe:
   SELECT * FROM importacion_subitems
   WHERE sufijos_completos ? ''AR'';  -- Tiene vencimiento

5. Extraer valor de sufijo:
   SELECT despacho_id,
          sufijos_completos->>''AA'' as marca,
          sufijos_completos->>''AB'' as modelo
   FROM importacion_subitems
   LIMIT 10;

Operadores JSONB utiles:
- ->>  : Extraer como texto
- ->   : Extraer como JSONB
- ?    : Verificar si clave existe
- @>   : Contiene
- #>>  : Extraer en path anidado

Ver: https://www.postgresql.org/docs/current/functions-json.html
Ver: docs/NOTAS_TECNICAS.md para mas ejemplos
================================================================================
';
END $$;
