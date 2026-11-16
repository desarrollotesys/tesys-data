#!/bin/bash
# ==============================================================================
# Script: importar_sql_mes.sh
# Descripción: Importa scripts SQL de un mes a la base de datos
# Uso: ./importar_sql_mes.sh YYYYMM
# Ejemplo: ./importar_sql_mes.sh 202502
# ==============================================================================

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 PERIODO"
    echo "Ejemplo: $0 202502 (para Febrero 2025)"
    exit 1
fi

PERIODO=$1
ANIO=${PERIODO:0:4}
MES=${PERIODO:4:2}

# Mapear número de mes a nombre
case $MES in
    01) MES_NOMBRE="enero" ;;
    02) MES_NOMBRE="febrero" ;;
    03) MES_NOMBRE="marzo" ;;
    04) MES_NOMBRE="abril" ;;
    05) MES_NOMBRE="mayo" ;;
    06) MES_NOMBRE="junio" ;;
    07) MES_NOMBRE="julio" ;;
    08) MES_NOMBRE="agosto" ;;
    09) MES_NOMBRE="septiembre" ;;
    10) MES_NOMBRE="octubre" ;;
    11) MES_NOMBRE="noviembre" ;;
    12) MES_NOMBRE="diciembre" ;;
    *) echo "Error: Mes inválido"; exit 1 ;;
esac

BASE_DIR="${TESYS_DATA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SQL_DIR="${BASE_DIR}/data/mensuales/${ANIO}/${MES}_${MES_NOMBRE}/sql"

echo "=================================================================="
echo "  Importando SQL a Base de Datos"
echo "  Mes: ${MES_NOMBRE^^} ${ANIO} (Período: $PERIODO)"
echo "=================================================================="
echo ""

# Verificar que existe el directorio
if [ ! -d "$SQL_DIR" ]; then
    echo "Error: No existe $SQL_DIR"
    exit 1
fi

# Contar archivos
TOTAL_FILES=$(ls -1 "$SQL_DIR"/*.sql 2>/dev/null | wc -l)
if [ "$TOTAL_FILES" -eq 0 ]; then
    echo "Error: No hay archivos SQL en $SQL_DIR"
    exit 1
fi

echo "Archivos encontrados: $TOTAL_FILES"
echo ""

IMPORTADOS=0
ERRORES=0

# Función para importar un archivo
# IMPORTANTE: -v ON_ERROR_STOP=1 es obligatorio. Sin esto, psql por defecto
# sigue ejecutando después de un ERROR de SQL y termina con exit code 0 --
# el script marcaba "✓" (éxito) aunque un INSERT masivo hubiera fallado
# completo (ej. mayo 2025: un despacho_id malformado con un espacio
# embebido en el zR1 de origen violaba la FK y abortaba TODO el INSERT de
# items de esa quincena -- 324.787 filas perdidas en silencio, "✓" en
# pantalla). El validador de completitud (paso final) sí lo detectaba,
# pero este paso mentía. Con ON_ERROR_STOP=1, psql corta y devuelve exit
# code distinto de 0 apenas hay un ERROR real, y el log queda guardado
# (no se descarta con /dev/null) para poder diagnosticar qué pasó.
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
for archivo in "$SQL_DIR"/importacion_despachos_${PERIODO}_q*.sql; do
    [ -f "$archivo" ] && importar_archivo "$archivo"
done
echo ""

echo "=== 2. ITEMS ==="
for archivo in "$SQL_DIR"/importacion_items_${PERIODO}_q*.sql; do
    [ -f "$archivo" ] && importar_archivo "$archivo"
done
echo ""

echo "=== 3. SUBITEMS ==="
for archivo in "$SQL_DIR"/importacion_subitems_${PERIODO}_q*.sql; do
    [ -f "$archivo" ] && importar_archivo "$archivo"
done
echo ""

echo "=== 4. OBLIGACIONES ==="
for archivo in "$SQL_DIR"/importacion_obligaciones_${PERIODO}_q*.sql; do
    [ -f "$archivo" ] && importar_archivo "$archivo"
done
echo ""

echo "=== 5. VENTAJAS ==="
for archivo in "$SQL_DIR"/importacion_ventajas_${PERIODO}_q*.sql; do
    [ -f "$archivo" ] && importar_archivo "$archivo"
done
echo ""

echo "=== 6. PROVEEDORES ==="
for archivo in "$SQL_DIR"/proveedores_${PERIODO}.sql; do
    [ -f "$archivo" ] && importar_archivo "$archivo"
done
echo ""

echo "=================================================================="
echo "✓ Importación completada para $MES_NOMBRE $ANIO"
echo ""
echo "Resultados:"
echo "  Archivos importados: $IMPORTADOS"
echo "  Errores:             $ERRORES"
echo ""

if [ "$ERRORES" -gt 0 ]; then
    echo "⚠ Hubo errores durante la importación"
    echo "  Revisa los logs de PostgreSQL para más detalles"
    exit 1
fi

echo "✓ Todos los archivos importados exitosamente (archivos SQL ejecutados sin error)"
echo ""

# ==============================================================================
# VALIDACIÓN OBLIGATORIA (no omitir): confirma que lo que se ejecutó sin error
# arriba realmente insertó TODAS las claves de los archivos fuente. Origen:
# Fase 5 (202608) descubrió que este mismo script podía imprimir "exitosamente"
# arriba aunque faltaran archivos enteros de una categoría (el glob
# "$SQL_DIR"/importacion_subitems_${PERIODO}_q*.sql no matcheaba nada y el
# for-loop simplemente no iteraba, sin error) — agosto 2026 quedó con
# subitems/obligaciones/ventajas vacíos sin que nada lo marcara como
# incompleto. Este paso cierra ese hueco: SIEMPRE corre, y si detecta
# claves faltantes, el script termina con exit 1 (no "éxito").
# ==============================================================================
echo "=== 7. VALIDACIÓN DE COMPLETITUD (obligatoria) ==="
RAW_DIR="${BASE_DIR}/data/mensuales/${ANIO}/${MES}_${MES_NOMBRE}/raw/importacion"
LST_FILE="${BASE_DIR}/data/mensuales/${ANIO}/${MES}_${MES_NOMBRE}/raw/proveedores/impo_${PERIODO}.lst"
LST_ARG=()
[ -f "$LST_FILE" ] && LST_ARG=(--lst-file "$LST_FILE")

if [ ! -d "$RAW_DIR" ]; then
    echo "⚠ No existe $RAW_DIR — no se puede validar completitud automáticamente."
    echo "  Esto NO significa que la carga esté completa. Validar manualmente antes de dar el mes por cerrado."
    exit 1
fi

python3 "${BASE_DIR}/scripts/04_validacion/validar_mes_completo_importacion.py" \
    --periodo "$PERIODO" \
    --raw-dir "$RAW_DIR" \
    --docker-container postgres_tesys \
    --docker-db comercio_exterior_argentina \
    "${LST_ARG[@]}"
VALIDACION_EXIT=$?

echo ""
if [ "$VALIDACION_EXIT" -ne 0 ]; then
    echo "✗ VALIDACIÓN FALLÓ — el mes $MES_NOMBRE $ANIO NO está completo (ver detalle arriba)."
    echo "  No dar este mes por cargado hasta resolver las claves faltantes."
    exit 1
fi

echo "✓ Validación de completitud OK — $MES_NOMBRE $ANIO confirmado completo (subitems/ventajas/obligaciones)"
echo ""
