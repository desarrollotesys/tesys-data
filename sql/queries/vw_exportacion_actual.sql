-- =====================================================
-- VISTA: vw_exportacion_actual
-- =====================================================
-- Propósito: Filtrar solo la versión MÁS RECIENTE de cada despacho
--            (resolver problema de postembarques)
--
-- Cómo funciona:
--   - Mismo despacho puede tener múltiples registros con diferentes fecha_oficializacion
--   - fecha_carga indica cuándo se insertó cada versión
--   - Esta vista retorna solo el registro con MAX(fecha_carga) por despacho
--
-- Ejemplo de postembarques:
--   despacho_id      | fecha_oficial | fecha_carga         | version
--   -----------------|---------------|---------------------|--------
--   22001EC01009796P | 2022-02-10    | 2026-01-15 04:21    | 3 (vieja)
--   22001EC01009796P | 2022-04-27    | 2026-01-15 04:24    | 2 (vieja)
--   22001EC01009796P | 2022-06-09    | 2026-01-15 04:30    | 1 (ACTUAL) ← Solo este
--
-- Uso en reportes:
--   SELECT * FROM vw_exportacion_actual
--   WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2022
--
-- =====================================================

DROP VIEW IF EXISTS vw_exportacion_actual CASCADE;

CREATE VIEW vw_exportacion_actual AS
WITH ultima_version AS (
    -- Identificar la versión más reciente de cada despacho
    SELECT
        despacho_id,
        fecha_oficializacion,
        ROW_NUMBER() OVER (
            PARTITION BY despacho_id
            ORDER BY fecha_carga DESC
        ) as rn
    FROM exportacion_despachos
)
SELECT
    d.*
FROM exportacion_despachos d
INNER JOIN ultima_version uv
    ON d.despacho_id = uv.despacho_id
    AND d.fecha_oficializacion = uv.fecha_oficializacion
WHERE uv.rn = 1;

-- Comentarios
COMMENT ON VIEW vw_exportacion_actual IS
'Despachos de exportación - solo versión más reciente (resuelve postembarques).
Usar esta vista en lugar de exportacion_despachos para reportes que requieran única versión por despacho.';

-- Verificar creación
\echo 'Vista vw_exportacion_actual creada exitosamente'
\echo ''
\echo 'Comparación antes/después:'

SELECT
    'exportacion_despachos (con postembarques)' as tabla,
    COUNT(*) as total_registros,
    COUNT(DISTINCT despacho_id) as despachos_unicos
FROM exportacion_despachos

UNION ALL

SELECT
    'vw_exportacion_actual (sin postembarques)',
    COUNT(*),
    COUNT(DISTINCT despacho_id)
FROM vw_exportacion_actual;
