-- =====================================================
-- SCRIPT DE VALIDACIÓN DE DATOS - EXPORTACIÓN
-- =====================================================
-- Propósito: Verificar calidad e integridad de datos
-- Fecha: 2026-01-14
-- =====================================================

\echo '=========================================='
\echo 'VALIDACIÓN DE DATOS DE EXPORTACIÓN'
\echo '=========================================='
\echo ''

-- =====================================================
-- 1. TOTALES Y COBERTURA
-- =====================================================
\echo '1. TOTALES Y COBERTURA DE DATOS'
\echo '----------------------------------------'

SELECT
    'Despachos únicos' as metrica,
    COUNT(DISTINCT despacho_id) as cantidad,
    TO_CHAR(MIN(fecha_oficializacion), 'YYYY-MM-DD') as fecha_min,
    TO_CHAR(MAX(fecha_oficializacion), 'YYYY-MM-DD') as fecha_max
FROM exportacion_despachos

UNION ALL

SELECT
    'Despachos (versiones)',
    COUNT(*),
    TO_CHAR(MIN(fecha_oficializacion), 'YYYY-MM-DD'),
    TO_CHAR(MAX(fecha_oficializacion), 'YYYY-MM-DD')
FROM exportacion_despachos

UNION ALL

SELECT
    'Items',
    COUNT(*),
    TO_CHAR(MIN(fecha_oficializacion), 'YYYY-MM-DD'),
    TO_CHAR(MAX(fecha_oficializacion), 'YYYY-MM-DD')
FROM exportacion_items

UNION ALL

SELECT
    'Subitems',
    COUNT(*),
    TO_CHAR(MIN(fecha_oficializacion), 'YYYY-MM-DD'),
    TO_CHAR(MAX(fecha_oficializacion), 'YYYY-MM-DD')
FROM exportacion_subitems;

\echo ''
\echo '2. DISTRIBUCIÓN MENSUAL'
\echo '----------------------------------------'

SELECT
    TO_CHAR(fecha_oficializacion, 'YYYY-MM') as mes,
    COUNT(DISTINCT despacho_id) as despachos,
    COUNT(*) as items
FROM exportacion_items
GROUP BY TO_CHAR(fecha_oficializacion, 'YYYY-MM')
ORDER BY mes;

-- =====================================================
-- 2. INTEGRIDAD REFERENCIAL
-- =====================================================
\echo ''
\echo '3. INTEGRIDAD REFERENCIAL'
\echo '----------------------------------------'

-- Items sin despacho
SELECT
    'Items sin despacho' as verificacion,
    COUNT(*) as problemas
FROM exportacion_items i
WHERE NOT EXISTS (
    SELECT 1 FROM exportacion_despachos d
    WHERE i.despacho_id = d.despacho_id
    AND i.fecha_oficializacion = d.fecha_oficializacion
)

UNION ALL

-- Subitems sin item
SELECT
    'Subitems sin item',
    COUNT(*)
FROM exportacion_subitems s
WHERE NOT EXISTS (
    SELECT 1 FROM exportacion_items i
    WHERE s.despacho_id = i.despacho_id
    AND s.fecha_oficializacion = i.fecha_oficializacion
    AND s.item_id = i.item_id
)

UNION ALL

-- Despachos sin items
SELECT
    'Despachos sin items',
    COUNT(DISTINCT d.despacho_id)
FROM exportacion_despachos d
WHERE NOT EXISTS (
    SELECT 1 FROM exportacion_items i
    WHERE i.despacho_id = d.despacho_id
    AND i.fecha_oficializacion = d.fecha_oficializacion
)

UNION ALL

-- Items sin subitems
SELECT
    'Items sin subitems',
    COUNT(*)
FROM exportacion_items i
WHERE NOT EXISTS (
    SELECT 1 FROM exportacion_subitems s
    WHERE s.despacho_id = i.despacho_id
    AND s.fecha_oficializacion = i.fecha_oficializacion
    AND s.item_id = i.item_id
);

-- =====================================================
-- 3. VALIDACIÓN DE CAMPOS OBLIGATORIOS
-- =====================================================
\echo ''
\echo '4. VALIDACIÓN DE CAMPOS OBLIGATORIOS'
\echo '----------------------------------------'

-- Despachos
SELECT
    'Despachos: despacho_id NULL' as validacion,
    COUNT(*) as problemas
FROM exportacion_despachos
WHERE despacho_id IS NULL

UNION ALL

SELECT
    'Despachos: fecha_oficializacion NULL',
    COUNT(*)
FROM exportacion_despachos
WHERE fecha_oficializacion IS NULL

UNION ALL

SELECT
    'Despachos: cuit_exportador NULL',
    COUNT(*)
FROM exportacion_despachos
WHERE cuit_exportador IS NULL

UNION ALL

-- Items
SELECT
    'Items: posicion_sim NULL',
    COUNT(*)
FROM exportacion_items
WHERE posicion_sim IS NULL

UNION ALL

SELECT
    'Items: kgs_netos NULL',
    COUNT(*)
FROM exportacion_items
WHERE kgs_netos IS NULL

UNION ALL

SELECT
    'Items: monto_fob_dolar NULL',
    COUNT(*)
FROM exportacion_items
WHERE monto_fob_dolar IS NULL

UNION ALL

SELECT
    'Items: cod_pais_destino NULL',
    COUNT(*)
FROM exportacion_items
WHERE cod_pais_destino IS NULL;

-- =====================================================
-- 4. VALIDACIÓN DE RANGOS DE VALORES
-- =====================================================
\echo ''
\echo '5. VALIDACIÓN DE RANGOS (valores negativos o fuera de rango)'
\echo '----------------------------------------'

SELECT
    'Items: kgs_netos < 0' as validacion,
    COUNT(*) as problemas
FROM exportacion_items
WHERE kgs_netos < 0

UNION ALL

SELECT
    'Items: kgs_netos = 0',
    COUNT(*)
FROM exportacion_items
WHERE kgs_netos = 0

UNION ALL

SELECT
    'Items: monto_fob_dolar < 0',
    COUNT(*)
FROM exportacion_items
WHERE monto_fob_dolar < 0

UNION ALL

SELECT
    'Items: monto_fob_dolar = 0',
    COUNT(*)
FROM exportacion_items
WHERE monto_fob_dolar = 0

UNION ALL

SELECT
    'Despachos: fob_monto < 0',
    COUNT(*)
FROM exportacion_despachos
WHERE fob_monto < 0;

-- =====================================================
-- 5. CONSISTENCIA DE SUMAS (FOB despacho vs items)
-- =====================================================
\echo ''
\echo '6. CONSISTENCIA DE SUMAS'
\echo '----------------------------------------'
\echo '(Comparando FOB de despacho vs suma de items - diferencias > 1%)'

WITH comparacion AS (
    SELECT
        d.despacho_id,
        d.fecha_oficializacion,
        d.fob_monto as fob_despacho,
        COALESCE(SUM(i.monto_fob_dolar), 0) as fob_items_suma,
        CASE
            WHEN d.fob_monto > 0
            THEN ABS((d.fob_monto - COALESCE(SUM(i.monto_fob_dolar), 0)) / d.fob_monto * 100)
            ELSE 0
        END as diferencia_pct
    FROM exportacion_despachos d
    LEFT JOIN exportacion_items i
        ON d.despacho_id = i.despacho_id
        AND d.fecha_oficializacion = i.fecha_oficializacion
    WHERE d.fob_monto IS NOT NULL AND d.fob_monto > 0
    GROUP BY d.despacho_id, d.fecha_oficializacion, d.fob_monto
)
SELECT
    'Despachos con diferencia > 1%' as validacion,
    COUNT(*) as cantidad,
    ROUND(AVG(diferencia_pct), 2) as "diferencia_promedio_%"
FROM comparacion
WHERE diferencia_pct > 1;

-- =====================================================
-- 6. VALIDACIÓN DE CÓDIGOS DE CATÁLOGO
-- =====================================================
\echo ''
\echo '7. VALIDACIÓN DE CÓDIGOS DE CATÁLOGO'
\echo '----------------------------------------'

SELECT
    'Destinaciones no en catálogo' as validacion,
    COUNT(DISTINCT d.tipo_destinacion) as problemas
FROM exportacion_despachos d
LEFT JOIN destinaciones dest ON d.tipo_destinacion = dest.codigo
WHERE dest.codigo IS NULL

UNION ALL

SELECT
    'Países destino no en catálogo',
    COUNT(DISTINCT i.cod_pais_destino)
FROM exportacion_items i
LEFT JOIN paises p ON i.cod_pais_destino = p.codigo
WHERE p.codigo IS NULL AND i.cod_pais_destino IS NOT NULL

UNION ALL

SELECT
    'NCM no en nomenclador',
    COUNT(DISTINCT i.posicion_sim)
FROM exportacion_items i
LEFT JOIN nomenclador n ON i.posicion_sim = n.posicion_sim
WHERE n.posicion_sim IS NULL

UNION ALL

SELECT
    'Unidades no en catálogo',
    COUNT(DISTINCT i.codigo_unidad)
FROM exportacion_items i
LEFT JOIN unidades u ON i.codigo_unidad = u.codigo
WHERE u.codigo IS NULL

UNION ALL

SELECT
    'Estados mercadería no en catálogo',
    COUNT(DISTINCT i.estado_mercaderia)
FROM exportacion_items i
LEFT JOIN estados e ON i.estado_mercaderia = e.codigo
WHERE e.codigo IS NULL

UNION ALL

SELECT
    'CUIT exportadores no en padrón',
    COUNT(DISTINCT d.cuit_exportador)
FROM exportacion_despachos d
LEFT JOIN padron p ON d.cuit_exportador = p.cuit
WHERE p.cuit IS NULL;

-- =====================================================
-- 7. POSTEMBARQUES
-- =====================================================
\echo ''
\echo '8. ANÁLISIS DE POSTEMBARQUES'
\echo '----------------------------------------'

SELECT
    'Despachos con postembarques' as metrica,
    COUNT(*) as cantidad
FROM (
    SELECT despacho_id
    FROM exportacion_despachos
    GROUP BY despacho_id
    HAVING COUNT(*) > 1
) subq

UNION ALL

SELECT
    'Total de versiones de postembarques',
    COUNT(*) - COUNT(DISTINCT despacho_id)
FROM exportacion_despachos;

\echo ''
\echo 'Muestra de despachos con más versiones:'
SELECT
    despacho_id,
    COUNT(*) as versiones,
    MIN(fecha_oficializacion) as primera_fecha,
    MAX(fecha_oficializacion) as ultima_fecha,
    MAX(fecha_carga) as ultima_carga
FROM exportacion_despachos
GROUP BY despacho_id
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 10;

-- =====================================================
-- 8. SUFIJOS EN SUBITEMS
-- =====================================================
\echo ''
\echo '9. VALIDACIÓN DE SUFIJOS (JSONB)'
\echo '----------------------------------------'

SELECT
    'Subitems con sufijos_completos NULL' as validacion,
    COUNT(*) as problemas
FROM exportacion_subitems
WHERE sufijos_completos IS NULL

UNION ALL

SELECT
    'Subitems con sufijos vacíos {}',
    COUNT(*)
FROM exportacion_subitems
WHERE sufijos_completos = '{}'::jsonb

UNION ALL

SELECT
    'Subitems con detalle_completo vacío',
    COUNT(*)
FROM exportacion_subitems
WHERE detalle_completo = '' OR detalle_completo IS NULL;

\echo ''
\echo 'Sufijos más comunes encontrados:'
SELECT
    key as sufijo_codigo,
    COUNT(*) as cantidad_registros
FROM exportacion_subitems,
    jsonb_each_text(sufijos_completos)
GROUP BY key
ORDER BY COUNT(*) DESC
LIMIT 20;

-- =====================================================
-- 9. ESTADÍSTICAS GENERALES
-- =====================================================
\echo ''
\echo '10. ESTADÍSTICAS GENERALES'
\echo '----------------------------------------'

SELECT
    'FOB promedio por despacho (USD)' as estadistica,
    ROUND(AVG(fob_monto), 2) as valor
FROM exportacion_despachos
WHERE fob_monto IS NOT NULL

UNION ALL

SELECT
    'FOB promedio por item (USD)',
    ROUND(AVG(monto_fob_dolar), 2)
FROM exportacion_items

UNION ALL

SELECT
    'Kg netos promedio por item',
    ROUND(AVG(kgs_netos), 2)
FROM exportacion_items

UNION ALL

SELECT
    'Items promedio por despacho',
    ROUND(AVG(items_count), 2)
FROM (
    SELECT despacho_id, fecha_oficializacion, COUNT(*) as items_count
    FROM exportacion_items
    GROUP BY despacho_id, fecha_oficializacion
) subq

UNION ALL

SELECT
    'Subitems promedio por item',
    ROUND(AVG(subitems_count), 2)
FROM (
    SELECT despacho_id, fecha_oficializacion, item_id, COUNT(*) as subitems_count
    FROM exportacion_subitems
    GROUP BY despacho_id, fecha_oficializacion, item_id
) subq;

\echo ''
\echo '=========================================='
\echo 'VALIDACIÓN COMPLETADA'
\echo '=========================================='
\echo ''
\echo 'Revisar los resultados arriba.'
\echo 'Problemas = 0 indica que la validación pasó exitosamente.'
\echo ''
