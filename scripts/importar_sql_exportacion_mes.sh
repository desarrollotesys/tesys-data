#!/bin/bash
# ==============================================================================
# Script: importar_sql_exportacion_mes.sh
# Descripción: Importa los SQL de EXPORTACIÓN de un mes a la base de datos
#              (generados antes con generar_sql_exportacion_mes.sh), y
#              valida que la carga haya quedado completa.
# Uso: ./importar_sql_exportacion_mes.sh YYYYMM
# Ejemplo: ./importar_sql_exportacion_mes.sh 202609
#
# Hermano de importar_sql_mes.sh (importación) — mismo motivo de existir:
# Fase 5 (agosto 202608) mostró que una carga podía declararse "exitosa"
# aunque faltara una categoría entera, sin que nada lo marcara. Este script
# SIEMPRE corre la validación de completitud al final (paso 5), y termina
# con exit 1 (no "éxito") si detecta claves faltantes.
#
# Apunta por defecto al contenedor local postgres_tesys. Para producción,
# usar el mismo patrón manual de los reportes en docs/ (backup + SHA256 +
# transacción + aserciones) en vez de este script — este es para carga
# local/desarrollo, donde un fallo se puede reintentar sin riesgo.
# ==============================================================================

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 PERIODO"
    echo "Ejemplo: $0 202609 (para Septiembre 2026)"
    exit 1
fi

PERIODO=$1
ANIO=${PERIODO:0:4}
MES=${PERIODO:4:2}

BASE_DIR="${TESYS_DATA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SQL_DIR="${BASE_DIR}/output/exportacion/${PERIODO}"
RAW_DIR_PATTERN="${BASE_DIR}/data/mensuales/${ANIO}"

echo "=================================================================="
echo "  Importando SQL de EXPORTACIÓN a Base de Datos"
echo "  Período: $PERIODO"
echo "=================================================================="
echo ""

if [ ! -d "$SQL_DIR" ]; then
    echo "Error: No existe $SQL_DIR"
    echo "  Generarlo primero con: ./scripts/generar_sql_exportacion_mes.sh $ANIO $MES"
    exit 1
fi

IMPORTADOS=0
ERRORES=0

importar_archivo() {
    local archivo=$1
    local nombre=$(basename "$archivo")
    local log="/tmp/importar_$(basename "$archivo" .sql).log"

    echo -n "  Importando $nombre... "

    if docker exec -i postgres_tesys psql -U postgres -d comercio_exterior_argentina -v ON_ERROR_STOP=1 < "$archivo" > "$log" 2>&1; then
        echo "✓"
        ((IMPORTADOS++))
        return 0
    else
        echo "✗ (ver $log)"
        tail -5 "$log" | sed 's/^/      /'
        ((ERRORES++))
        return 1
    fi
}

# ORDEN CRÍTICO: Respetar foreign keys
echo "=== 1. DESPACHOS ==="
[ -f "$SQL_DIR/exportacion_despachos_${PERIODO}.sql" ] && importar_archivo "$SQL_DIR/exportacion_despachos_${PERIODO}.sql"
echo ""

echo "=== 2. ITEMS ==="
[ -f "$SQL_DIR/exportacion_items_${PERIODO}.sql" ] && importar_archivo "$SQL_DIR/exportacion_items_${PERIODO}.sql"
echo ""

echo "=== 3. VENTAJAS ==="
[ -f "$SQL_DIR/exportacion_ventajas_${PERIODO}.sql" ] && importar_archivo "$SQL_DIR/exportacion_ventajas_${PERIODO}.sql"
echo ""

echo "=== 4. SUBITEMS ==="
[ -f "$SQL_DIR/exportacion_subitems_${PERIODO}.sql" ] && importar_archivo "$SQL_DIR/exportacion_subitems_${PERIODO}.sql"
echo ""

echo "=================================================================="
echo "Resultados:"
echo "  Archivos importados: $IMPORTADOS"
echo "  Errores:             $ERRORES"
echo ""

if [ "$ERRORES" -gt 0 ]; then
    echo "⚠ Hubo errores durante la importación"
    exit 1
fi

echo "✓ Todos los archivos importados exitosamente (archivos SQL ejecutados sin error)"
echo ""

# ==============================================================================
# VALIDACIÓN OBLIGATORIA (no omitir)
# ==============================================================================
echo "=== 5. VALIDACIÓN DE COMPLETITUD (obligatoria) ==="

# Buscar el directorio raw de exportación de ese período (ej. .../raw/exportacion/202609Expo)
RAW_DIR=$(find "$RAW_DIR_PATTERN" -maxdepth 4 -type d -name "${PERIODO}Expo" 2>/dev/null | head -1)

if [ -z "$RAW_DIR" ] || [ ! -d "$RAW_DIR" ]; then
    echo "⚠ No se encontró el directorio raw de exportación para $PERIODO — no se puede validar completitud automáticamente."
    echo "  Esto NO significa que la carga esté completa. Validar manualmente antes de dar el mes por cerrado."
    exit 1
fi

python3 "${BASE_DIR}/scripts/04_validacion/validar_mes_completo_exportacion.py" \
    --periodo "$PERIODO" \
    --raw-dir "$RAW_DIR" \
    --docker-container postgres_tesys \
    --docker-db comercio_exterior_argentina
VALIDACION_EXIT=$?

echo ""
if [ "$VALIDACION_EXIT" -ne 0 ]; then
    echo "✗ VALIDACIÓN FALLÓ — exportación $PERIODO NO está completa (ver detalle arriba)."
    echo "  No dar este mes por cargado hasta resolver las claves faltantes."
    exit 1
fi

echo "✓ Validación de completitud OK — exportación $PERIODO confirmada completa (subitems/ventajas)"
echo ""
