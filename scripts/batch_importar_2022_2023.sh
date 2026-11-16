#!/bin/bash
# ==============================================================================
# Script: batch_importar_2022_2023.sh
# Descripción: Extrae, genera SQL e importa datos de importación
#              para 2022 completo y 2023 Ene-Ago
# Uso: ./batch_importar_2022_2023.sh
# ==============================================================================

set -e

BASE_DIR="${TESYS_DATA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TMP_DIR="/home/spawnmc/Code/TesysTMP"
SCRIPTS_DIR="$BASE_DIR/scripts"
LOG_FILE="$BASE_DIR/output/batch_importar_2022_2023.log"

mkdir -p "$BASE_DIR/output"

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

mes_nombre() {
    case $1 in
        01) echo "enero" ;;    02) echo "febrero" ;;
        03) echo "marzo" ;;    04) echo "abril" ;;
        05) echo "mayo" ;;     06) echo "junio" ;;
        07) echo "julio" ;;    08) echo "agosto" ;;
        09) echo "septiembre" ;; 10) echo "octubre" ;;
        11) echo "noviembre" ;; 12) echo "diciembre" ;;
    esac
}

extraer_archivo() {
    local archivo=$1
    local destino=$2
    mkdir -p "$destino"
    if [[ "$archivo" == *.rar ]]; then
        unrar x -y "$archivo" "$destino/" > /dev/null 2>&1 || true
    else
        unzip -o -q "$archivo" -d "$destino"
    fi
}

procesar_mes() {
    local periodo=$1   # ej: 202201
    local anio=${periodo:0:4}
    local mes=${periodo:4:2}
    local nombre=$(mes_nombre $mes)
    local mes_dir="$BASE_DIR/data/mensuales/$anio/${mes}_${nombre}"
    local raw_dir="$mes_dir/raw/importacion"

    log "══════════════════════════════════════"
    log "Procesando $nombre $anio ($periodo)"
    log "══════════════════════════════════════"

    mkdir -p "$raw_dir"

    # --- Extraer quincenas ---
    local q1_zip q2_zip

    if [ "$anio" = "2022" ]; then
        q1_zip="$TMP_DIR/2022/${periodo}ImpoQ1.zip"
        q2_zip=$(ls "$TMP_DIR/2022/${periodo}ImpoQ2".{zip,rar} 2>/dev/null | head -1)
    else
        # 2023: archivos en subcarpeta 0MMYYYY
        local sub_dir="$TMP_DIR/2023/0${mes}2023"
        q1_zip=$(ls "$sub_dir/${periodo}ImpoQ1".{zip,rar} 2>/dev/null | head -1)
        q2_zip=$(ls "$sub_dir/${periodo}ImpoQ2".{zip,rar} 2>/dev/null | head -1)
    fi

    if [ -n "$q1_zip" ] && [ -f "$q1_zip" ]; then
        log "  Extrayendo Q1: $(basename $q1_zip)"
        extraer_archivo "$q1_zip" "$raw_dir/${periodo}ImpoQ1"
    else
        log "  ⚠ Q1 no encontrado para $periodo"
    fi

    if [ -n "$q2_zip" ] && [ -f "$q2_zip" ]; then
        log "  Extrayendo Q2: $(basename $q2_zip)"
        extraer_archivo "$q2_zip" "$raw_dir/${periodo}ImpoQ2"
    else
        log "  ⚠ Q2 no encontrado para $periodo"
    fi

    # --- Generar SQL ---
    log "  Generando SQL..."
    if bash "$SCRIPTS_DIR/generar_sql_mes.sh" "$periodo" >> "$LOG_FILE" 2>&1; then
        log "  ✓ SQL generado"
    else
        log "  ✗ Error generando SQL para $periodo"
        return 1
    fi

    # --- Importar a BD ---
    log "  Importando a la base de datos..."
    if bash "$SCRIPTS_DIR/importar_sql_mes.sh" "$periodo" >> "$LOG_FILE" 2>&1; then
        log "  ✓ Importado correctamente"
    else
        log "  ⚠ Importación con errores en $periodo (posiblemente solo despachos por FK)"
    fi

    log "  ✓ $nombre $anio completado"
}

# ==============================================================================
log "Iniciando importación batch 2022 + 2023 Ene-Ago"
log "Log: $LOG_FILE"

# Deshabilitar FK en importacion_despachos (hay CUITs históricos no en padrón actual)
log "Deshabilitando triggers en importacion_despachos..."
docker exec postgres_tesys psql -U postgres -d comercio_exterior_argentina -c \
    "ALTER TABLE importacion_despachos DISABLE TRIGGER ALL;" > /dev/null

ERRORES=0

# 2022: todos los meses
for mes in 01 02 03 04 05 06 07 08 09 10 11 12; do
    procesar_mes "2022${mes}" || ERRORES=$((ERRORES+1))
done

# 2023: enero a agosto
for mes in 01 02 03 04 05 06 07 08; do
    procesar_mes "2023${mes}" || ERRORES=$((ERRORES+1))
done

# Reactivar FK
log "Reactivando triggers en importacion_despachos..."
docker exec postgres_tesys psql -U postgres -d comercio_exterior_argentina -c \
    "ALTER TABLE importacion_despachos ENABLE TRIGGER ALL;" > /dev/null

log "══════════════════════════════════════"
log "Batch finalizado. Errores: $ERRORES"
log "══════════════════════════════════════"

if [ "$ERRORES" -gt 0 ]; then
    exit 1
fi
