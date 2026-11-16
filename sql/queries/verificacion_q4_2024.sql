-- ==============================================================================
-- Script: verificacion_q4_2024.sql
-- Descripción: Verificaciones post-importación para Q4 2024
-- Fecha: 2024-11-03
-- Uso: Ejecutar después de importar datos de Q4 2024
-- ==============================================================================

\echo ''
\echo '=================================================================='
\echo '  VERIFICACIÓN DE IMPORTACIÓN Q4 2024'
\echo '  Octubre - Noviembre - Diciembre'
\echo '=================================================================='
\echo ''

-- ==============================================================================
-- 1. RESUMEN DE DESPACHOS POR MES
-- ==============================================================================
\echo '1. DESPACHOS POR MES (Q4 2024)'
\echo '------------------------------------------------------------------'

SELECT
    TO_CHAR(fecha_oficializacion, 'YYYY-MM') AS mes,
    COUNT(*) AS cantidad_despachos,
    TO_CHAR(SUM(fob_monto), 'FM999,999,999,999') AS fob_total_pesos,
    TO_CHAR(AVG(fob_monto), 'FM999,999,999') AS fob_promedio,
    COUNT(DISTINCT cuit_importador) AS importadores_unicos
FROM importacion_despachos
WHERE fecha_oficializacion >= '2024-10-01'
  AND fecha_oficializacion < '2025-01-01'
GROUP BY TO_CHAR(fecha_oficializacion, 'YYYY-MM')
ORDER BY mes;

\echo ''

-- ==============================================================================
-- 2. RESUMEN DE ITEMS POR MES
-- ==============================================================================
\echo '2. ITEMS POR MES (Q4 2024)'
\echo '------------------------------------------------------------------'

SELECT
    TO_CHAR(fecha_oficializacion, 'YYYY-MM') AS mes,
    COUNT(*) AS cantidad_items,
    TO_CHAR(SUM(fob_dolar), 'FM999,999,999,999') AS fob_total_dolares,
    COUNT(DISTINCT despacho_id) AS despachos_relacionados,
    TO_CHAR(AVG(cantidad_unidades), 'FM999,999') AS unidades_promedio
FROM importacion_items
WHERE fecha_oficializacion >= '2024-10-01'
  AND fecha_oficializacion < '2025-01-01'
GROUP BY TO_CHAR(fecha_oficializacion, 'YYYY-MM')
ORDER BY mes;

\echo ''

-- ==============================================================================
-- 3. RESUMEN DE SUBITEMS POR MES
-- ==============================================================================
\echo '3. SUBITEMS POR MES (Q4 2024)'
\echo '------------------------------------------------------------------'

SELECT
    TO_CHAR(fecha_oficializacion, 'YYYY-MM') AS mes,
    COUNT(*) AS cantidad_subitems,
    COUNT(DISTINCT despacho_id) AS despachos_relacionados,
    COUNT(DISTINCT codigo_tipo_destinacion) AS destinaciones_usadas
FROM importacion_subitems
WHERE fecha_oficializacion >= '2024-10-01'
  AND fecha_oficializacion < '2025-01-01'
GROUP BY TO_CHAR(fecha_oficializacion, 'YYYY-MM')
ORDER BY mes;

\echo ''

-- ==============================================================================
-- 4. INTEGRIDAD: ITEMS SIN DESPACHO
-- ==============================================================================
\echo '4. VALIDACIÓN: Items sin despacho (debería ser 0)'
\echo '------------------------------------------------------------------'

SELECT
    COALESCE(COUNT(*), 0) AS items_sin_despacho,
    CASE
        WHEN COUNT(*) = 0 THEN '✓ OK - Todos los items tienen su despacho'
        ELSE '✗ ERROR - Hay items huérfanos'
    END AS estado
FROM importacion_items i
WHERE i.fecha_oficializacion >= '2024-10-01'
  AND i.fecha_oficializacion < '2025-01-01'
  AND NOT EXISTS (
      SELECT 1
      FROM importacion_despachos d
      WHERE d.despacho_id = i.despacho_id
        AND d.fecha_oficializacion = i.fecha_oficializacion
  );

\echo ''

-- ==============================================================================
-- 5. INTEGRIDAD: SUBITEMS SIN ITEM
-- ==============================================================================
\echo '5. VALIDACIÓN: Subitems sin item (debería ser 0)'
\echo '------------------------------------------------------------------'

SELECT
    COALESCE(COUNT(*), 0) AS subitems_sin_item,
    CASE
        WHEN COUNT(*) = 0 THEN '✓ OK - Todos los subitems tienen su item'
        ELSE '✗ ERROR - Hay subitems huérfanos'
    END AS estado
FROM importacion_subitems s
WHERE s.fecha_oficializacion >= '2024-10-01'
  AND s.fecha_oficializacion < '2025-01-01'
  AND NOT EXISTS (
      SELECT 1
      FROM importacion_items i
      WHERE i.despacho_id = s.despacho_id
        AND i.fecha_oficializacion = s.fecha_oficializacion
        AND i.item_id = s.item_id
  );

\echo ''

-- ==============================================================================
-- 6. CUITs TEMPORALES AGREGADOS
-- ==============================================================================
\echo '6. CUITs agregados temporalmente (con razón social "Por determinar")'
\echo '------------------------------------------------------------------'

SELECT
    p.cuit,
    COUNT(d.despacho_id) AS cantidad_despachos
FROM padron p
LEFT JOIN importacion_despachos d
    ON p.cuit = d.cuit_importador
    AND d.fecha_oficializacion >= '2024-10-01'
    AND d.fecha_oficializacion < '2025-01-01'
WHERE p.razon_social = 'Por determinar'
GROUP BY p.cuit
ORDER BY cantidad_despachos DESC;

\echo ''

-- ==============================================================================
-- 7. TOP 10 IMPORTADORES Q4 2024
-- ==============================================================================
\echo '7. Top 10 Importadores por FOB (Q4 2024)'
\echo '------------------------------------------------------------------'

SELECT
    d.cuit_importador,
    COALESCE(p.razon_social, 'Sin datos') AS razon_social,
    COUNT(*) AS cantidad_despachos,
    TO_CHAR(SUM(d.fob_monto), 'FM999,999,999,999') AS fob_total_pesos
FROM importacion_despachos d
LEFT JOIN padron p ON d.cuit_importador = p.cuit
WHERE d.fecha_oficializacion >= '2024-10-01'
  AND d.fecha_oficializacion < '2025-01-01'
GROUP BY d.cuit_importador, p.razon_social
ORDER BY SUM(d.fob_monto) DESC
LIMIT 10;

\echo ''

-- ==============================================================================
-- 8. PAÍSES DE ORIGEN MÁS FRECUENTES
-- ==============================================================================
\echo '8. Top 10 Países de origen (Q4 2024)'
\echo '------------------------------------------------------------------'

SELECT
    COALESCE(pa.nombre, i.codigo_origen) AS pais,
    COUNT(*) AS cantidad_items,
    TO_CHAR(SUM(i.fob_dolar), 'FM999,999,999,999') AS fob_total_usd
FROM importacion_items i
LEFT JOIN paises pa ON i.codigo_origen = pa.codigo
WHERE i.fecha_oficializacion >= '2024-10-01'
  AND i.fecha_oficializacion < '2025-01-01'
GROUP BY pa.nombre, i.codigo_origen
ORDER BY SUM(i.fob_dolar) DESC
LIMIT 10;

\echo ''

-- ==============================================================================
-- 9. DISTRIBUCIÓN POR ADUANA
-- ==============================================================================
\echo '9. Despachos por Aduana (Q4 2024)'
\echo '------------------------------------------------------------------'

SELECT
    SUBSTRING(s.despacho_id, 6, 3) AS codigo_aduana,
    COALESCE(a.nombre, 'Desconocida') AS nombre_aduana,
    COUNT(DISTINCT s.despacho_id) AS cantidad_despachos
FROM importacion_subitems s
LEFT JOIN aduanas a ON SUBSTRING(s.despacho_id, 6, 3) = a.codigo
WHERE s.fecha_oficializacion >= '2024-10-01'
  AND s.fecha_oficializacion < '2025-01-01'
GROUP BY SUBSTRING(s.despacho_id, 6, 3), a.nombre
ORDER BY COUNT(DISTINCT s.despacho_id) DESC
LIMIT 10;

\echo ''

-- ==============================================================================
-- 10. RANGOS DE FECHAS Y TOTALES GENERALES
-- ==============================================================================
\echo '10. RESUMEN GENERAL Q4 2024'
\echo '------------------------------------------------------------------'

WITH stats AS (
    SELECT
        MIN(fecha_oficializacion) AS fecha_minima,
        MAX(fecha_oficializacion) AS fecha_maxima,
        COUNT(*) AS total_despachos,
        COUNT(DISTINCT cuit_importador) AS total_importadores,
        SUM(fob_monto) AS fob_total
    FROM importacion_despachos
    WHERE fecha_oficializacion >= '2024-10-01'
      AND fecha_oficializacion < '2025-01-01'
)
SELECT
    fecha_minima,
    fecha_maxima,
    (fecha_maxima - fecha_minima) AS dias_cubiertos,
    TO_CHAR(total_despachos, 'FM999,999,999') AS total_despachos,
    TO_CHAR(total_importadores, 'FM999,999') AS total_importadores,
    TO_CHAR(fob_total, 'FM999,999,999,999,999') AS fob_total_pesos
FROM stats;

\echo ''

-- ==============================================================================
-- 11. COMPARACIÓN CON MESES ANTERIORES (SI EXISTEN)
-- ==============================================================================
\echo '11. Comparación con trimestres anteriores 2024'
\echo '------------------------------------------------------------------'

SELECT
    CONCAT('Q', EXTRACT(QUARTER FROM fecha_oficializacion)) AS trimestre,
    COUNT(*) AS cantidad_despachos,
    TO_CHAR(SUM(fob_monto), 'FM999,999,999,999') AS fob_total_pesos,
    COUNT(DISTINCT cuit_importador) AS importadores_unicos
FROM importacion_despachos
WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2024
GROUP BY EXTRACT(QUARTER FROM fecha_oficializacion)
ORDER BY trimestre;

\echo ''
\echo '=================================================================='
\echo '  FIN DE VERIFICACIÓN'
\echo '=================================================================='
\echo ''

-- ==============================================================================
-- NOTAS:
-- ==============================================================================
--
-- ✓ Si "Items sin despacho" = 0 y "Subitems sin item" = 0, la integridad es correcta
-- ⚠ Si hay CUITs con "Por determinar", consultar con AFIP para actualizar
-- ℹ Los totales de FOB pueden variar según el tipo de cambio y la fecha
--
-- ==============================================================================
