#!/bin/bash
# ==============================================================================
# Script: exportar_importaciones_2024.sh
# Descripción: Exporta solo los datos de importaciones del año 2024
# Uso: ./exportar_importaciones_2024.sh [nombre_archivo_salida]
# ==============================================================================

set -e

# Configuración
OUTPUT_FILE="${1:-export_importaciones_2024_$(date +%Y%m%d_%H%M%S).sql}"
TEMP_DIR="/tmp/export_2024"
POSTGRES_CONTAINER="postgres_tesys"
DB_NAME="comercio_exterior_argentina"

echo "=================================================================="
echo "  EXPORTANDO IMPORTACIONES 2024"
echo "=================================================================="
echo ""
echo "Archivo de salida: $OUTPUT_FILE"
echo ""

# Crear directorio temporal
mkdir -p "$TEMP_DIR"

# ==============================================================================
# 1. DESPACHOS 2024
# ==============================================================================
echo "1/6 Exportando despachos 2024..."
docker exec $POSTGRES_CONTAINER psql -U postgres -d $DB_NAME <<'EOF' > "$TEMP_DIR/01_despachos.sql"
-- Despachos 2024
COPY (
    SELECT
        despacho_id,
        fecha_oficializacion,
        cuit_importador,
        estado_declaracion,
        condicion_venta,
        fob_divisa,
        flete_divisa,
        seguro_divisa,
        fob_monto,
        flete_monto,
        seguro_monto,
        medio,
        cantidad_bultos,
        peso_bruto,
        matricula,
        titulo_transporte
    FROM importacion_despachos
    WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2024
    ORDER BY fecha_oficializacion, despacho_id
) TO STDOUT WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
EOF

# ==============================================================================
# 2. ITEMS 2024
# ==============================================================================
echo "2/6 Exportando items 2024..."
docker exec $POSTGRES_CONTAINER psql -U postgres -d $DB_NAME <<'EOF' > "$TEMP_DIR/02_items.sql"
-- Items 2024
COPY (
    SELECT
        despacho_id,
        fecha_oficializacion,
        item_id,
        posicion_sim,
        codigo_procedencia,
        codigo_origen,
        codigo_unidad,
        cantidad_unidades,
        kg_netos,
        fob_dolar,
        fob_divisa,
        estado_mercaderia
    FROM importacion_items
    WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2024
    ORDER BY fecha_oficializacion, despacho_id, item_id
) TO STDOUT WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
EOF

# ==============================================================================
# 3. SUBITEMS 2024
# ==============================================================================
echo "3/6 Exportando subitems 2024..."
docker exec $POSTGRES_CONTAINER psql -U postgres -d $DB_NAME <<'EOF' > "$TEMP_DIR/03_subitems.sql"
-- Subitems 2024
COPY (
    SELECT
        despacho_id,
        fecha_oficializacion,
        item_id,
        subitem_id,
        codigo_tipo_destinacion,
        kg_netos
    FROM importacion_subitems
    WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2024
    ORDER BY fecha_oficializacion, despacho_id, item_id, subitem_id
) TO STDOUT WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
EOF

# ==============================================================================
# 4. OBLIGACIONES 2024
# ==============================================================================
echo "4/6 Exportando obligaciones 2024..."
docker exec $POSTGRES_CONTAINER psql -U postgres -d $DB_NAME <<'EOF' > "$TEMP_DIR/04_obligaciones.sql"
-- Obligaciones 2024
COPY (
    SELECT
        despacho_id,
        fecha_oficializacion,
        item_id,
        subitem_id,
        obligacion_id,
        nro_cuota,
        codigo_tributo,
        nro_certificado,
        tipo_comprobante,
        tipo_obligacion,
        importe_obligacion
    FROM importacion_obligaciones
    WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2024
    ORDER BY fecha_oficializacion, despacho_id, item_id, subitem_id, obligacion_id
) TO STDOUT WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
EOF

# ==============================================================================
# 5. VENTAJAS 2024
# ==============================================================================
echo "5/6 Exportando ventajas 2024..."
docker exec $POSTGRES_CONTAINER psql -U postgres -d $DB_NAME <<'EOF' > "$TEMP_DIR/05_ventajas.sql"
-- Ventajas 2024
COPY (
    SELECT
        despacho_id,
        fecha_oficializacion,
        item_id,
        subitem_id,
        ventaja_id,
        codigo_tipo_ventaja,
        nro_certificado,
        importe_ventaja
    FROM importacion_ventajas
    WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2024
    ORDER BY fecha_oficializacion, despacho_id, item_id, subitem_id, ventaja_id
) TO STDOUT WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
EOF

# ==============================================================================
# 6. CUITs AGREGADOS PARA 2024
# ==============================================================================
echo "6/6 Exportando CUITs agregados para 2024..."
docker exec $POSTGRES_CONTAINER psql -U postgres -d $DB_NAME <<'EOF' > "$TEMP_DIR/06_cuits_2024.sql"
-- CUITs que solo aparecen en 2024
SELECT DISTINCT
    p.cuit,
    p.razon_social
FROM padron p
WHERE p.cuit IN (
    SELECT DISTINCT cuit_importador
    FROM importacion_despachos
    WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2024
)
ORDER BY p.cuit;
EOF

# ==============================================================================
# 7. COMBINAR TODO EN UN ARCHIVO
# ==============================================================================
echo ""
echo "Generando archivo SQL completo..."

cat > "$OUTPUT_FILE" <<'HEADER'
-- ==============================================================================
-- EXPORT: Importaciones 2024
-- Fecha de exportación: $(date +"%Y-%m-%d %H:%M:%S")
-- Base de datos: comercio_exterior_argentina
-- ==============================================================================

BEGIN;

-- ==============================================================================
-- 1. DESPACHOS 2024
-- ==============================================================================

CREATE TEMP TABLE temp_despachos (LIKE importacion_despachos INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES);

COPY temp_despachos (
    despacho_id,
    fecha_oficializacion,
    cuit_importador,
    estado_declaracion,
    condicion_venta,
    fob_divisa,
    flete_divisa,
    seguro_divisa,
    fob_monto,
    flete_monto,
    seguro_monto,
    medio,
    cantidad_bultos,
    peso_bruto,
    matricula,
    titulo_transporte
) FROM STDIN WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
HEADER

cat "$TEMP_DIR/01_despachos.sql" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" <<'MID1'
\.

INSERT INTO importacion_despachos (
    despacho_id,
    fecha_oficializacion,
    cuit_importador,
    estado_declaracion,
    condicion_venta,
    fob_divisa,
    flete_divisa,
    seguro_divisa,
    fob_monto,
    flete_monto,
    seguro_monto,
    medio,
    cantidad_bultos,
    peso_bruto,
    matricula,
    titulo_transporte
)
SELECT * FROM temp_despachos
ON CONFLICT (despacho_id, fecha_oficializacion) DO UPDATE SET
    cuit_importador = EXCLUDED.cuit_importador,
    estado_declaracion = EXCLUDED.estado_declaracion,
    condicion_venta = EXCLUDED.condicion_venta,
    fob_divisa = EXCLUDED.fob_divisa,
    flete_divisa = EXCLUDED.flete_divisa,
    seguro_divisa = EXCLUDED.seguro_divisa,
    fob_monto = EXCLUDED.fob_monto,
    flete_monto = EXCLUDED.flete_monto,
    seguro_monto = EXCLUDED.seguro_monto,
    medio = EXCLUDED.medio,
    cantidad_bultos = EXCLUDED.cantidad_bultos,
    peso_bruto = EXCLUDED.peso_bruto,
    matricula = EXCLUDED.matricula,
    titulo_transporte = EXCLUDED.titulo_transporte;

DROP TABLE temp_despachos;

-- ==============================================================================
-- 2. ITEMS 2024
-- ==============================================================================

CREATE TEMP TABLE staging_items (LIKE importacion_items INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES);

COPY staging_items (
    despacho_id,
    fecha_oficializacion,
    item_id,
    posicion_sim,
    codigo_procedencia,
    codigo_origen,
    codigo_unidad,
    cantidad_unidades,
    kg_netos,
    fob_dolar,
    fob_divisa,
    estado_mercaderia
) FROM STDIN WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
MID1

cat "$TEMP_DIR/02_items.sql" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" <<'MID2'
\.

INSERT INTO importacion_items SELECT * FROM staging_items
ON CONFLICT (despacho_id, fecha_oficializacion, item_id) DO UPDATE SET
    posicion_sim = EXCLUDED.posicion_sim,
    codigo_procedencia = EXCLUDED.codigo_procedencia,
    codigo_origen = EXCLUDED.codigo_origen,
    codigo_unidad = EXCLUDED.codigo_unidad,
    cantidad_unidades = EXCLUDED.cantidad_unidades,
    kg_netos = EXCLUDED.kg_netos,
    fob_dolar = EXCLUDED.fob_dolar,
    fob_divisa = EXCLUDED.fob_divisa,
    estado_mercaderia = EXCLUDED.estado_mercaderia;

DROP TABLE staging_items;

-- ==============================================================================
-- 3. SUBITEMS 2024
-- ==============================================================================

COPY importacion_subitems (
    despacho_id,
    fecha_oficializacion,
    item_id,
    subitem_id,
    codigo_tipo_destinacion,
    kg_netos
) FROM STDIN WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
MID2

cat "$TEMP_DIR/03_subitems.sql" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" <<'MID3'
\.

-- ==============================================================================
-- 4. OBLIGACIONES 2024
-- ==============================================================================

COPY importacion_obligaciones (
    despacho_id,
    fecha_oficializacion,
    item_id,
    subitem_id,
    obligacion_id,
    nro_cuota,
    codigo_tributo,
    nro_certificado,
    tipo_comprobante,
    tipo_obligacion,
    importe_obligacion
) FROM STDIN WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
MID3

cat "$TEMP_DIR/04_obligaciones.sql" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" <<'MID4'
\.

-- ==============================================================================
-- 5. VENTAJAS 2024
-- ==============================================================================

COPY importacion_ventajas (
    despacho_id,
    fecha_oficializacion,
    item_id,
    subitem_id,
    ventaja_id,
    codigo_tipo_ventaja,
    nro_certificado,
    importe_ventaja
) FROM STDIN WITH (FORMAT text, DELIMITER E'\t', NULL '\N', ENCODING 'UTF8');
MID4

cat "$TEMP_DIR/05_ventajas.sql" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" <<'FOOTER'
\.

COMMIT;

-- ==============================================================================
-- FIN DEL EXPORT
-- ==============================================================================
FOOTER

# Comprimir
echo ""
echo "Comprimiendo archivo..."
gzip -f "$OUTPUT_FILE"

# Limpiar temporales
rm -rf "$TEMP_DIR"

# Mostrar resultado
echo ""
echo "=================================================================="
echo "✓ Export completado"
echo ""
echo "Archivo generado: ${OUTPUT_FILE}.gz"
echo "Tamaño: $(du -h "${OUTPUT_FILE}.gz" | cut -f1)"
echo ""
echo "Para importar en otra base:"
echo "  gunzip -c ${OUTPUT_FILE}.gz | docker exec -i postgres_tesys psql -U postgres -d comercio_exterior_argentina"
echo "=================================================================="
