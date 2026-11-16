-- =====================================================
-- VALIDACIÓN MANUAL DE REGISTROS DEL CSV
-- =====================================================
-- Propósito: Verificar que los datos del CSV coinciden con la base de datos
--
-- Uso:
--   1. Toma un registro del CSV
--   2. Usa las queries abajo para verificar en la base de datos
--   3. Compara valores campo por campo
-- =====================================================

\echo '=========================================='
\echo 'VALIDACIÓN MANUAL DE REGISTROS CSV'
\echo '=========================================='
\echo ''

-- =====================================================
-- EJEMPLO: Validar el primer registro del CSV
-- =====================================================
-- CSV dice:
--   R,2022,01,127,7326.90.,1260.000,1125.00
--
-- Vamos a buscar este registro en la base de datos

\echo '1. BUSCAR REGISTROS POR CRITERIOS'
\echo '   (Año=2022, Mes=01, País=127, NCM=7326.90.)'
\echo ''

SELECT
    -- Datos calculados (como en el CSV)
    SUBSTRING(d.tipo_destinacion, 1, 1) as tipo_comercio,
    EXTRACT(YEAR FROM i.fecha_oficializacion)::INTEGER as anio,
    LPAD(EXTRACT(MONTH FROM i.fecha_oficializacion)::TEXT, 2, '0') as mes,
    i.cod_pais_destino,
    SUBSTRING(i.posicion_sim, 1, 8) as ncm,
    ROUND(i.kgs_netos::numeric, 3) as peso_neto_kg,
    ROUND(i.monto_fob_dolar::numeric, 2) as valor_fob_usd,

    -- Datos adicionales para identificar el registro
    i.despacho_id,
    i.item_id,
    d.fecha_oficializacion,

    -- Valores originales sin redondear
    i.kgs_netos as peso_original,
    i.monto_fob_dolar as fob_original,
    d.tipo_destinacion as destino_completo

FROM exportacion_items i
INNER JOIN vw_exportacion_actual d
    ON i.despacho_id = d.despacho_id
    AND i.fecha_oficializacion = d.fecha_oficializacion

WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) = 2022
    AND EXTRACT(MONTH FROM i.fecha_oficializacion) = 1
    AND i.cod_pais_destino = '127'
    AND SUBSTRING(i.posicion_sim, 1, 8) = '7326.90.'
    AND ROUND(i.kgs_netos::numeric, 3) = 1260.000
    AND ROUND(i.monto_fob_dolar::numeric, 2) = 1125.00

ORDER BY i.despacho_id, i.item_id
LIMIT 5;

\echo ''
\echo '---'
\echo ''

-- =====================================================
-- BUSCAR POR DESPACHO ESPECÍFICO
-- =====================================================

\echo '2. VALIDAR UN DESPACHO COMPLETO'
\echo '   (Ver todos los items de un despacho)'
\echo ''

-- Primero encuentra un despacho del CSV
WITH primer_despacho AS (
    SELECT i.despacho_id, i.fecha_oficializacion
    FROM exportacion_items i
    INNER JOIN vw_exportacion_actual d
        ON i.despacho_id = d.despacho_id
        AND i.fecha_oficializacion = d.fecha_oficializacion
    WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) = 2022
    LIMIT 5
)
SELECT
    i.despacho_id,
    i.item_id,
    SUBSTRING(d.tipo_destinacion, 1, 1) as tipo_comercio,
    EXTRACT(YEAR FROM i.fecha_oficializacion) as anio,
    EXTRACT(MONTH FROM i.fecha_oficializacion) as mes,
    i.cod_pais_destino,
    SUBSTRING(i.posicion_sim, 1, 8) as ncm,
    ROUND(i.kgs_netos, 3) as peso_kg,
    ROUND(i.monto_fob_dolar, 2) as fob_usd
FROM exportacion_items i
INNER JOIN vw_exportacion_actual d
    ON i.despacho_id = d.despacho_id
    AND i.fecha_oficializacion = d.fecha_oficializacion
WHERE (i.despacho_id, i.fecha_oficializacion) IN (SELECT despacho_id, fecha_oficializacion FROM primer_despacho)
ORDER BY i.item_id;

\echo ''
\echo '---'
\echo ''

-- =====================================================
-- VERIFICAR TOTALES
-- =====================================================

\echo '3. VERIFICAR TOTALES POR MES'
\echo '   (Comparar con resumen del CSV)'
\echo ''

SELECT
    EXTRACT(YEAR FROM i.fecha_oficializacion)::TEXT || '-' ||
    LPAD(EXTRACT(MONTH FROM i.fecha_oficializacion)::TEXT, 2, '0') as mes,
    COUNT(*) as total_registros,
    COUNT(DISTINCT i.despacho_id) as despachos_distintos,
    COUNT(DISTINCT i.cod_pais_destino) as paises_distintos,
    COUNT(DISTINCT SUBSTRING(i.posicion_sim, 1, 8)) as ncm_distintos,
    ROUND(SUM(i.kgs_netos), 3) as total_kg,
    ROUND(SUM(i.monto_fob_dolar), 2) as total_fob_usd
FROM exportacion_items i
INNER JOIN vw_exportacion_actual d
    ON i.despacho_id = d.despacho_id
    AND i.fecha_oficializacion = d.fecha_oficializacion
WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) = 2022
    AND i.cod_pais_destino IS NOT NULL
GROUP BY
    EXTRACT(YEAR FROM i.fecha_oficializacion),
    EXTRACT(MONTH FROM i.fecha_oficializacion)
ORDER BY mes;

\echo ''
\echo '=========================================='
\echo ''

-- =====================================================
-- QUERIES PARAMETRIZADAS PARA USO MANUAL
-- =====================================================

\echo 'QUERIES PARA COPIAR Y MODIFICAR:'
\echo ''
\echo '-- Buscar registro específico del CSV:'
\echo 'SELECT'
\echo '    SUBSTRING(d.tipo_destinacion, 1, 1) as tipo_comercio,'
\echo '    EXTRACT(YEAR FROM i.fecha_oficializacion) as anio,'
\echo '    EXTRACT(MONTH FROM i.fecha_oficializacion) as mes,'
\echo '    i.cod_pais_destino,'
\echo '    SUBSTRING(i.posicion_sim, 1, 8) as ncm,'
\echo '    ROUND(i.kgs_netos, 3) as peso_kg,'
\echo '    ROUND(i.monto_fob_dolar, 2) as fob_usd,'
\echo '    i.despacho_id, i.item_id'
\echo 'FROM exportacion_items i'
\echo 'INNER JOIN vw_exportacion_actual d'
\echo '    ON i.despacho_id = d.despacho_id'
\echo '    AND i.fecha_oficializacion = d.fecha_oficializacion'
\echo 'WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) = 2022  -- Cambiar año'
\echo '    AND EXTRACT(MONTH FROM i.fecha_oficializacion) = 1  -- Cambiar mes'
\echo '    AND i.cod_pais_destino = '\''127'\''                     -- Cambiar país'
\echo '    AND SUBSTRING(i.posicion_sim, 1, 8) = '\''7326.90.'\''   -- Cambiar NCM'
\echo '    AND ROUND(i.kgs_netos, 3) = 1260.000               -- Cambiar peso'
\echo 'ORDER BY i.despacho_id, i.item_id;'
\echo ''
