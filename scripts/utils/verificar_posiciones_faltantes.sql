-- Utilidad para identificar posiciones SIM faltantes en nomenclador
-- Requiere que los datos esten en una tabla temporal/staging

-- PASO 1: Crear tabla temporal con los datos del archivo zR5
-- (El script Python debe cargar primero en staging)

DROP TABLE IF EXISTS staging_items;

CREATE TEMPORARY TABLE staging_items (
    despacho_id VARCHAR(16),
    fecha_oficializacion DATE,
    item_id VARCHAR(10),
    posicion_sim VARCHAR(20),
    codigo_procedencia VARCHAR(10),
    codigo_origen VARCHAR(10),
    codigo_unidad VARCHAR(10),
    cantidad_unidades DECIMAL(15,3),
    kg_netos DECIMAL(12,3),
    fob_dolar DECIMAL(15,2),
    fob_divisa DECIMAL(15,2),
    estado_mercaderia VARCHAR(5)
);

-- PASO 2: Cargar datos en staging usando COPY
-- (Ejecutar externamente)

-- PASO 3: Identificar posiciones faltantes
SELECT DISTINCT s.posicion_sim
FROM staging_items s
WHERE s.posicion_sim NOT IN (SELECT posicion_sim FROM nomenclador)
ORDER BY s.posicion_sim;

-- PASO 4: Contar posiciones faltantes
SELECT COUNT(DISTINCT s.posicion_sim) as posiciones_faltantes
FROM staging_items s
WHERE s.posicion_sim NOT IN (SELECT posicion_sim FROM nomenclador);

-- PASO 5: Generar INSERT para posiciones faltantes
SELECT
    'INSERT INTO nomenclador (posicion_sim, descripcion, codigo_unidad) VALUES (''' ||
    s.posicion_sim ||
    ''', ''PARTIDA NUEVA - EN PROCESO DE CLASIFICACION'', NULL) ON CONFLICT DO NOTHING;' as insert_statement
FROM (
    SELECT DISTINCT posicion_sim
    FROM staging_items
    WHERE posicion_sim NOT IN (SELECT posicion_sim FROM nomenclador)
) s
ORDER BY s.posicion_sim;

-- PASO 6: Ver cuantas veces se usa cada posicion faltante
SELECT
    s.posicion_sim,
    COUNT(*) as veces_usada
FROM staging_items s
WHERE s.posicion_sim NOT IN (SELECT posicion_sim FROM nomenclador)
GROUP BY s.posicion_sim
ORDER BY COUNT(*) DESC;
