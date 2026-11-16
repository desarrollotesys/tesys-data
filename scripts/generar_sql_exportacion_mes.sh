#!/bin/bash
#
# Script para generar archivos SQL de exportación para un mes específico
# Uso: ./generar_sql_exportacion_mes.sh YYYY MM
# Ejemplo: ./generar_sql_exportacion_mes.sh 2025 01
#

set -e  # Salir si hay error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para mostrar mensajes
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validar argumentos
if [ $# -ne 2 ]; then
    echo "Uso: $0 YYYY MM"
    echo "Ejemplo: $0 2025 01"
    exit 1
fi

YEAR=$1
MONTH=$2

# Validar formato de año y mes
if ! [[ "$YEAR" =~ ^[0-9]{4}$ ]]; then
    log_error "Año inválido. Debe ser formato YYYY (ej: 2025)"
    exit 1
fi

if ! [[ "$MONTH" =~ ^[0-9]{2}$ ]]; then
    log_error "Mes inválido. Debe ser formato MM (ej: 01, 12)"
    exit 1
fi

# Determinar nombre del mes
declare -A MESES=(
    ["01"]="01_enero"
    ["02"]="02_febrero"
    ["03"]="03_marzo"
    ["04"]="04_abril"
    ["05"]="05_mayo"
    ["06"]="06_junio"
    ["07"]="07_julio"
    ["08"]="08_agosto"
    ["09"]="09_septiembre"
    ["10"]="10_octubre"
    ["11"]="11_noviembre"
    ["12"]="12_diciembre"
)

MES_NOMBRE=${MESES[$MONTH]}
if [ -z "$MES_NOMBRE" ]; then
    log_error "Mes inválido: $MONTH. Debe estar entre 01 y 12"
    exit 1
fi

# Construir rutas
PERIODO="${YEAR}${MONTH}"
DATA_DIR="data/mensuales/${YEAR}/${MES_NOMBRE}/raw/exportacion/${PERIODO}Expo"
OUTPUT_DIR="output/exportacion/${PERIODO}"
SCRIPTS_DIR="scripts/02_importador"

# Verificar que exista el directorio de datos
if [ ! -d "$DATA_DIR" ]; then
    log_error "Directorio de datos no encontrado: $DATA_DIR"
    exit 1
fi

# Verificar que existan los archivos necesarios
ARCHIVOS=("zR1.txt" "zR5.txt" "zR8.txt" "zR9.txt")
for archivo in "${ARCHIVOS[@]}"; do
    if [ ! -f "${DATA_DIR}/${archivo}" ]; then
        log_error "Archivo no encontrado: ${DATA_DIR}/${archivo}"
        exit 1
    fi
done

# Crear directorio de salida
log_info "Creando directorio de salida: $OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo ""
log_info "=============================================="
log_info "Generando SQL para Exportación"
log_info "Periodo: ${MES_NOMBRE} ${YEAR}"
log_info "=============================================="
echo ""

# 1. Generar SQL para despachos (zR1)
log_info "[1/4] Procesando despachos (zR1.txt)..."
python3 "${SCRIPTS_DIR}/generar_exportacion_despachos.py" \
    "${DATA_DIR}/zR1.txt" \
    -m "${PERIODO}" \
    -o "${OUTPUT_DIR}/exportacion_despachos_${PERIODO}.sql"

if [ $? -eq 0 ]; then
    log_info "✓ Despachos procesados exitosamente"
else
    log_error "✗ Error procesando despachos"
    exit 1
fi

echo ""

# 2. Generar SQL para items (zR5)
log_info "[2/4] Procesando items (zR5.txt)..."
python3 "${SCRIPTS_DIR}/generar_exportacion_items.py" \
    "${DATA_DIR}/zR5.txt" \
    -m "${PERIODO}" \
    -o "${OUTPUT_DIR}/exportacion_items_${PERIODO}.sql"

if [ $? -eq 0 ]; then
    log_info "✓ Items procesados exitosamente"
else
    log_error "✗ Error procesando items"
    exit 1
fi

echo ""

# 3. Generar SQL para ventajas (zR8)
log_info "[3/4] Procesando ventajas (zR8.txt)..."
python3 "${SCRIPTS_DIR}/generar_exportacion_ventajas.py" \
    "${DATA_DIR}/zR8.txt" \
    -m "${PERIODO}" \
    -o "${OUTPUT_DIR}/exportacion_ventajas_${PERIODO}.sql"

if [ $? -eq 0 ]; then
    log_info "✓ Ventajas procesadas exitosamente"
else
    log_error "✗ Error procesando ventajas"
    exit 1
fi

echo ""

# 4. Generar SQL para subitems (zR9)
log_info "[4/4] Procesando subitems (zR9.txt)..."
python3 "${SCRIPTS_DIR}/generar_exportacion_subitems.py" \
    "${DATA_DIR}/zR9.txt" \
    -m "${PERIODO}" \
    -o "${OUTPUT_DIR}/exportacion_subitems_${PERIODO}.sql"

if [ $? -eq 0 ]; then
    log_info "✓ Subitems procesados exitosamente"
else
    log_error "✗ Error procesando subitems"
    exit 1
fi

echo ""
log_info "=============================================="
log_info "Proceso completado exitosamente"
log_info "=============================================="
echo ""

# Mostrar archivos generados
log_info "Archivos SQL generados en: $OUTPUT_DIR"
ls -lh "${OUTPUT_DIR}"/*.sql

echo ""
log_info "Para cargar en PostgreSQL, ejecutar en este orden:"
echo ""
echo "psql -d comercio_exterior_argentina -f ${OUTPUT_DIR}/exportacion_despachos_${PERIODO}.sql"
echo "psql -d comercio_exterior_argentina -f ${OUTPUT_DIR}/exportacion_items_${PERIODO}.sql"
echo "psql -d comercio_exterior_argentina -f ${OUTPUT_DIR}/exportacion_ventajas_${PERIODO}.sql"
echo "psql -d comercio_exterior_argentina -f ${OUTPUT_DIR}/exportacion_subitems_${PERIODO}.sql"
echo ""

exit 0
