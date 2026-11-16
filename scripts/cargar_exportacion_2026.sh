#!/bin/bash
#
# Carga datos de exportación 2026 (Enero–Abril) desde data/TMP/2026/
# Fuente: data/TMP/2026/MMYYYY/{YYYYMM}Expo.zip
#
# Febrero tiene un R9 reenvio ("zR9 reenvio por nuevas marcas.zip")
# que se carga después del original para agregar las marcas nuevas.
# El ON CONFLICT DO NOTHING del script evita duplicados.
#
# Uso: ./scripts/cargar_exportacion_2026.sh [01|02|03|04|all]
# Ejemplo: ./scripts/cargar_exportacion_2026.sh all
#

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }

# --- Configuración ---
CONTAINER=postgres_tesys
DB_USER=postgres
DB_NAME=comercio_exterior_argentina
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_2026="${REPO_ROOT}/data/TMP/2026"
SCRIPTS_DIR="${REPO_ROOT}/scripts/02_importador"
OUTPUT_BASE="${REPO_ROOT}/output/exportacion"
SQL_BASE="${REPO_ROOT}/output/sql/2026"

mkdir -p "${SQL_BASE}"

# Verificar Docker
if ! docker ps | grep -q "$CONTAINER"; then
    log_error "Contenedor '$CONTAINER' no está corriendo. Iniciando..."
    docker start "$CONTAINER"
    sleep 3
fi

# ----------------------------------------------------------------
# procesar_mes YYYY MM CARPETA_ZIP NOMBRE_ZIP [REENVIO_ZIP]
# ----------------------------------------------------------------
procesar_mes() {
    local YEAR=$1
    local MM=$2
    local CARPETA=$3      # ej: 022026
    local ZIP_NOMBRE=$4   # ej: 202602Expo.zip
    local REENVIO_ZIP=$5  # opcional, ej: "zR9 reenvio por nuevas marcas.zip"

    local PERIODO="${YEAR}${MM}"
    local SRC_DIR="${TMP_2026}/${CARPETA}"
    local ZIP_PATH="${SRC_DIR}/${ZIP_NOMBRE}"
    local EXTRACT_DIR="${REPO_ROOT}/data/TMP/_extract_${PERIODO}"
    local OUT_DIR="${OUTPUT_BASE}/${PERIODO}"

    echo ""
    log_step "======================================================"
    log_step "Procesando Exportación ${PERIODO}"
    log_step "======================================================"

    # Extraer zip principal
    log_info "Extrayendo ${ZIP_NOMBRE}..."
    mkdir -p "${EXTRACT_DIR}"
    unzip -o -q "${ZIP_PATH}" -d "${EXTRACT_DIR}"

    # Verificar archivos necesarios
    for f in zR1.txt zR5.txt zR8.txt zR9.txt; do
        if [ ! -f "${EXTRACT_DIR}/${f}" ]; then
            log_error "Falta ${f} en ${EXTRACT_DIR}"
            exit 1
        fi
    done

    mkdir -p "${OUT_DIR}"

    # 1. Despachos (zR1)
    log_info "[1/4] Generando SQL despachos..."
    python3 "${SCRIPTS_DIR}/generar_exportacion_despachos.py" \
        "${EXTRACT_DIR}/zR1.txt" \
        -m "${PERIODO}" \
        -o "${OUT_DIR}/exportacion_despachos_${PERIODO}.sql"
    cp "${OUT_DIR}/exportacion_despachos_${PERIODO}.sql" "${SQL_BASE}/"
    log_info "✓ Despachos OK"

    # 2. Items (zR5)
    log_info "[2/4] Generando SQL items..."
    python3 "${SCRIPTS_DIR}/generar_exportacion_items.py" \
        "${EXTRACT_DIR}/zR5.txt" \
        -m "${PERIODO}" \
        -o "${OUT_DIR}/exportacion_items_${PERIODO}.sql"
    cp "${OUT_DIR}/exportacion_items_${PERIODO}.sql" "${SQL_BASE}/"
    log_info "✓ Items OK"

    # 3. Ventajas (zR8)
    log_info "[3/4] Generando SQL ventajas..."
    python3 "${SCRIPTS_DIR}/generar_exportacion_ventajas.py" \
        "${EXTRACT_DIR}/zR8.txt" \
        -m "${PERIODO}" \
        -o "${OUT_DIR}/exportacion_ventajas_${PERIODO}.sql"
    cp "${OUT_DIR}/exportacion_ventajas_${PERIODO}.sql" "${SQL_BASE}/"
    log_info "✓ Ventajas OK"

    # 4. Subitems (zR9 original)
    log_info "[4/4] Generando SQL subitems (zR9 original)..."
    python3 "${SCRIPTS_DIR}/generar_exportacion_subitems.py" \
        "${EXTRACT_DIR}/zR9.txt" \
        -m "${PERIODO}" \
        -o "${OUT_DIR}/exportacion_subitems_${PERIODO}.sql"
    cp "${OUT_DIR}/exportacion_subitems_${PERIODO}.sql" "${SQL_BASE}/"
    log_info "✓ Subitems OK"

    # 4b. Reenvio R9 (solo Febrero)
    local SUBITEMS_REENVIO_SQL=""
    if [ -n "${REENVIO_ZIP}" ]; then
        log_info "[4b] Procesando R9 reenvío: ${REENVIO_ZIP}..."
        local EXTRACT_REENVIO="${REPO_ROOT}/data/TMP/_extract_${PERIODO}_reenvio"
        mkdir -p "${EXTRACT_REENVIO}"
        unzip -o -q "${SRC_DIR}/${REENVIO_ZIP}" -d "${EXTRACT_REENVIO}"

        if [ ! -f "${EXTRACT_REENVIO}/zR9.txt" ]; then
            log_error "zR9.txt no encontrado en reenvio zip"
            exit 1
        fi

        SUBITEMS_REENVIO_SQL="${OUT_DIR}/exportacion_subitems_${PERIODO}_reenvio.sql"
        python3 "${SCRIPTS_DIR}/generar_exportacion_subitems.py" \
            "${EXTRACT_REENVIO}/zR9.txt" \
            -m "${PERIODO}" \
            -o "${SUBITEMS_REENVIO_SQL}"
        log_info "✓ Subitems reenvío OK"
        rm -rf "${EXTRACT_REENVIO}"
    fi

    # Limpiar archivos extraídos
    rm -rf "${EXTRACT_DIR}"

    # --- Carga en PostgreSQL ---
    echo ""
    log_info "Cargando ${PERIODO} en PostgreSQL (${CONTAINER})..."

    local TABLAS=("despachos" "items" "ventajas" "subitems")
    for t in "${TABLAS[@]}"; do
        local sql_file="${OUT_DIR}/exportacion_${t}_${PERIODO}.sql"
        log_info "  → exportacion_${t}..."
        if ! docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
               --set ON_ERROR_STOP=1 -q < "$sql_file" 2>&1; then
            log_error "Error cargando exportacion_${t} ${PERIODO}"
            log_warn "Para ver el error: docker exec -i ${CONTAINER} psql -U ${DB_USER} -d ${DB_NAME} < ${sql_file}"
            exit 1
        fi
        log_info "  ✓ ${t} cargado"
    done

    # Cargar reenvio si existe
    if [ -n "${SUBITEMS_REENVIO_SQL}" ] && [ -f "${SUBITEMS_REENVIO_SQL}" ]; then
        log_info "  → exportacion_subitems (reenvio marcas nuevas)..."
        if ! docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
               --set ON_ERROR_STOP=1 -q < "${SUBITEMS_REENVIO_SQL}" 2>&1; then
            log_error "Error cargando subitems reenvio ${PERIODO}"
            exit 1
        fi
        log_info "  ✓ subitems reenvio cargado"
    fi

    # Estadísticas del mes
    echo ""
    log_info "Estadísticas ${PERIODO}:"
    docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
  COUNT(DISTINCT d.id_despacho) AS despachos,
  COUNT(i.despacho_id)          AS items,
  ROUND(SUM(i.monto_fob_dolar)::numeric/1e6, 2) AS fob_musd
FROM exportacion_despachos d
JOIN exportacion_items i ON i.despacho_id = d.id_despacho
WHERE d.fecha_oficializacion >= '${YEAR}-${MM}-01'
  AND d.fecha_oficializacion  < '${YEAR}-${MM}-01'::date + interval '1 month';" \
    2>/dev/null || log_warn "No se pudo consultar estadísticas del mes"

    log_info "✓ ${PERIODO} completado"
}

# ----------------------------------------------------------------
# Selección de meses a procesar
# ----------------------------------------------------------------
MESES_ARG=${1:-all}

run_01() { procesar_mes 2026 01 012026 202601Expo.zip; }
run_02() { procesar_mes 2026 02 022026 202602Expo.zip "zR9 reenvio por nuevas marcas.zip"; }
run_03() { procesar_mes 2026 03 032026 202603Expo.zip; }
run_04() { procesar_mes 2026 04 042026 202604Expo.zip; }
run_05() { procesar_mes 2026 05 052026 202605Expo.zip; }

case "$MESES_ARG" in
    01)  run_01 ;;
    02)  run_02 ;;
    03)  run_03 ;;
    04)  run_04 ;;
    05)  run_05 ;;
    all)
        run_01
        run_02
        run_03
        run_04
        run_05
        ;;
    *)
        echo "Uso: $0 [01|02|03|04|05|all]"
        exit 1
        ;;
esac

# --- Resumen final ---
echo ""
log_step "======================================================"
log_step "RESUMEN 2026 en base de datos"
log_step "======================================================"
docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
  EXTRACT(MONTH FROM fecha_oficializacion)::int AS mes,
  COUNT(DISTINCT despacho_id) AS despachos,
  COUNT(*) AS items,
  ROUND(SUM(monto_fob_dolar)::numeric/1e6, 2) AS fob_musd
FROM exportacion_items_actual
WHERE EXTRACT(YEAR FROM fecha_oficializacion) = 2026
GROUP BY 1 ORDER BY 1;" 2>/dev/null

log_info "Proceso completado."
exit 0
