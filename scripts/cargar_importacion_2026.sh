#!/bin/bash
# Carga el SQL ya generado por generar_sql_mes.sh para un período de 2026 en
# postgres_tesys, en el orden correcto: despachos -> items -> subitems ->
# obligaciones -> ventajas (por cada quincena), y por último proveedores.
#
# Uso: ./scripts/cargar_importacion_2026.sh PERIODO [PERIODO ...]
# Ejemplo: ./scripts/cargar_importacion_2026.sh 202601 202602 202603 202604 202605
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

CONTAINER=postgres_tesys
DB_USER=postgres
DB_NAME=comercio_exterior_argentina
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

declare -A MESNOM=( [01]=01_enero [02]=02_febrero [03]=03_marzo [04]=04_abril [05]=05_mayo
                     [06]=06_junio [07]=07_julio [08]=08_agosto [09]=09_septiembre
                     [10]=10_octubre [11]=11_noviembre [12]=12_diciembre )

if ! docker ps | grep -q "$CONTAINER"; then
    log_error "Contenedor '$CONTAINER' no está corriendo."
    exit 1
fi

cargar_sql() {
    local archivo=$1
    local etiqueta=$2
    if [ ! -f "$archivo" ]; then
        log_error "No encontrado: $archivo"
        return 1
    fi
    log_info "  -> ${etiqueta}..."
    docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
        --set ON_ERROR_STOP=1 -q < "$archivo"
}

for PERIODO in "$@"; do
    MM=${PERIODO:4:2}
    YEAR=${PERIODO:0:4}
    SQL_DIR="${REPO_ROOT}/data/mensuales/${YEAR}/${MESNOM[$MM]}/sql"

    log_info "=================================================="
    log_info "Cargando importación ${PERIODO}"
    log_info "=================================================="

    for Q in q1 q2; do
        cargar_sql "${SQL_DIR}/importacion_despachos_${PERIODO}_${Q}.sql" "despachos ${Q}"
        cargar_sql "${SQL_DIR}/importacion_items_${PERIODO}_${Q}.sql" "items ${Q}"
        cargar_sql "${SQL_DIR}/importacion_subitems_${PERIODO}_${Q}.sql" "subitems ${Q}"
        cargar_sql "${SQL_DIR}/importacion_obligaciones_${PERIODO}_${Q}.sql" "obligaciones ${Q}"
        cargar_sql "${SQL_DIR}/importacion_ventajas_${PERIODO}_${Q}.sql" "ventajas ${Q}"
    done

    if [ -f "${SQL_DIR}/proveedores_${PERIODO}.sql" ]; then
        cargar_sql "${SQL_DIR}/proveedores_${PERIODO}.sql" "proveedores"
    fi

    log_info "✓ ${PERIODO} cargado"
    echo ""
done

log_info "Estadísticas por mes (importación):"
docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT date_trunc('month', fecha_oficializacion)::date AS mes, COUNT(*) AS despachos
FROM importacion_despachos
WHERE fecha_oficializacion >= '2026-01-01'
GROUP BY 1 ORDER BY 1;"
