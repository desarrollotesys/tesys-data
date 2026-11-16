-- =====================================================
-- REPORTE DE EXPORTACIONES - FORMATO GABY
-- =====================================================
-- Según especificación de Gaby del correo
--
-- Campos requeridos (7):
--   1. tipo_destinacion: código completo (EC01, EG01, ER02...) — solo tipos E%
--   2. Año (4 dígitos)
--   3. Mes (2 dígitos, con ceros)
--   4. Código de País de Destino (3 dígitos, puede ser NULL)
--   5. NCM (10 caracteres con subposición, ej. 0402.10.10)
--   6. Peso neto en kilogramos (16,3)
--   7. Valor FOB en dólares (15,2)
--
-- FILTRO CLAVE: solo tipo_destinacion LIKE 'E%' (exportaciones para consumo,
--   excluye tránsitos TRB, reembolsos REM/PER, BARA, VMI, etc.)
-- Referencia: reporte_exportacion_2022_consumo.csv / reporte_exportacion_202605.csv
--
-- Uso:
--   psql -d comercio_exterior_argentina -f generar_reporte_exportacion_gaby.sql
--
-- Parámetros (modificar según necesidad):
--   :anio_desde, :anio_hasta, :output_file
-- =====================================================

-- Configuración
\set anio_desde 2026
\set anio_hasta 2026
\set output_file /tmp/reporte_exportacion_2026.csv

\echo '=========================================='
\echo 'REPORTE DE EXPORTACIONES - FORMATO GABY'
\echo '=========================================='
\echo ''
\echo 'Parámetros:'
\echo '  Año desde:' :anio_desde
\echo '  Año hasta:' :anio_hasta
\echo '  Archivo:' :output_file
\echo ''

-- Query principal del reporte (COPY, no \copy: el meta-comando \copy de psql
-- no soporta bien comentarios "--" dentro de una consulta multilinea)
COPY (
    SELECT
        -- Campo 1: Código de Tipo de Destinación completo (ej. EC01)
        d.tipo_destinacion as tipo_destinacion,

        -- Campo 2: Año (4 dígitos)
        EXTRACT(YEAR FROM i.fecha_oficializacion)::INTEGER as anio,

        -- Campo 3: Mes (2 dígitos, con ceros a la izquierda)
        LPAD(EXTRACT(MONTH FROM i.fecha_oficializacion)::TEXT, 2, '0') as mes,

        -- Campo 4: Código de País de Destino (3 dígitos)
        COALESCE(i.cod_pais_destino, '000') as cod_pais_destino,

        -- Campo 5: NCM con puntos (10 caracteres: NCM.subpos.subpos, ej. 1001.99.00)
        SUBSTRING(i.posicion_sim, 1, 10) as ncm,

        -- Campo 6: Peso neto en kilogramos (formato 16,3)
        ROUND(i.kgs_netos::numeric, 3) as peso_neto_kg,

        -- Campo 7: Valor FOB en dólares (formato 15,2)
        ROUND(i.monto_fob_dolar::numeric, 2) as valor_fob_usd

    FROM exportacion_items_actual i

    -- JOIN con despachos usando la VISTA (sin postembarques duplicados)
    INNER JOIN exportacion_despachos_actual d
        ON i.despacho_id = d.despacho_id
        AND i.fecha_oficializacion = d.fecha_oficializacion

    -- Filtros
    WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) BETWEEN :anio_desde AND :anio_hasta
        AND i.cod_pais_destino IS NOT NULL  -- Excluir items sin país destino

    -- Ordenamiento para facilitar análisis
    ORDER BY
        anio,
        mes,
        cod_pais_destino,
        ncm
) TO :'output_file' WITH (FORMAT CSV, HEADER TRUE, DELIMITER ',');

\echo ''
\echo 'Reporte generado exitosamente!'
\echo ''

-- Estadísticas del reporte generado
\echo 'Estadísticas del reporte:'

SELECT
    'Total registros exportados' as metrica,
    COUNT(*) as cantidad
FROM exportacion_items_actual i
INNER JOIN exportacion_despachos_actual d
    ON i.despacho_id = d.despacho_id
    AND i.fecha_oficializacion = d.fecha_oficializacion
WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) BETWEEN :anio_desde AND :anio_hasta
    AND i.cod_pais_destino IS NOT NULL

UNION ALL

SELECT
    'Items sin país destino (excluidos)',
    COUNT(*)
FROM exportacion_items_actual i
WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) BETWEEN :anio_desde AND :anio_hasta
    AND i.cod_pais_destino IS NULL

UNION ALL

SELECT
    'Postembarques filtrados por vista',
    COUNT(*)
FROM exportacion_items_actual i
INNER JOIN exportacion_despachos d
    ON i.despacho_id = d.despacho_id
    AND i.fecha_oficializacion = d.fecha_oficializacion
LEFT JOIN exportacion_despachos_actual v
    ON d.despacho_id = v.despacho_id
    AND d.fecha_oficializacion = v.fecha_oficializacion
WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) BETWEEN :anio_desde AND :anio_hasta
    AND v.despacho_id IS NULL;

\echo ''
\echo 'Distribución por mes:'

SELECT
    EXTRACT(YEAR FROM i.fecha_oficializacion)::TEXT || '-' ||
    LPAD(EXTRACT(MONTH FROM i.fecha_oficializacion)::TEXT, 2, '0') as mes,
    COUNT(*) as registros,
    COUNT(DISTINCT i.cod_pais_destino) as paises,
    COUNT(DISTINCT SUBSTRING(i.posicion_sim, 1, 8)) as ncm_distintos,
    ROUND(SUM(i.monto_fob_dolar) / 1000000, 2) as fob_millones_usd
FROM exportacion_items_actual i
INNER JOIN exportacion_despachos_actual d
    ON i.despacho_id = d.despacho_id
    AND i.fecha_oficializacion = d.fecha_oficializacion
WHERE EXTRACT(YEAR FROM i.fecha_oficializacion) BETWEEN :anio_desde AND :anio_hasta
    AND i.cod_pais_destino IS NOT NULL
GROUP BY
    EXTRACT(YEAR FROM i.fecha_oficializacion),
    EXTRACT(MONTH FROM i.fecha_oficializacion)
ORDER BY mes;

\echo ''
\echo '=========================================='
\echo 'ARCHIVO GENERADO:' :output_file
\echo '=========================================='
