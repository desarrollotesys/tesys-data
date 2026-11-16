#!/usr/bin/env bash
# Validación y recarga de exportacion_subitems para un mes específico.
# Uso: ./validar_recarga_subitems.sh YYYYMM /ruta/a/zR9.txt [--staging|--prod]
#
# Pasos:
#   1. Genera SQL con el ETL corregido (sin [:100])
#   2. Muestra estadísticas: total / con detalle>100 chars / sufijos AM encontrados
#   3. Con --staging: aplica en DB de staging y verifica resultado
#   4. NO ejecuta en producción sin flag --prod explícito
#
set -euo pipefail

MES="${1:-}"
ZR9="${2:-}"
ENV="${3:---staging}"

if [[ -z "$MES" || -z "$ZR9" ]]; then
    echo "Uso: $0 YYYYMM /ruta/zR9.txt [--staging|--prod]"
    exit 1
fi

if [[ "$ENV" != "--staging" && "$ENV" != "--prod" ]]; then
    echo "Error: tercer argumento debe ser --staging o --prod"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="/tmp/subitems_recarga_${MES}"
mkdir -p "$OUTPUT_DIR"

echo "=== Validación previa: analizar $ZR9 ==="
python3 - <<PYEOF
import csv, re
RE = re.compile(r'([A-Z]{2})(?:\([^)]*\)|\d{2})-')
total = truncated = with_am = 0
with open('$ZR9', encoding='utf-8', errors='replace') as f:
    for row in csv.reader(f, delimiter='|'):
        if len(row) < 4:
            continue
        d = row[3].strip().strip('"')
        total += 1
        if len(d) > 100:
            truncated += 1
        if 'AM(' in d or '-AM(' in d:
            # AM aparece en el source
            pass
        codes = [m.group(1) for m in RE.finditer(d)]
        if 'AM' in codes:
            with_am += 1
print(f"Total subitems:          {total:,}")
print(f"Con detalle > 100 chars: {truncated:,} ({truncated/total*100:.1f}%)")
print(f"Con sufijo AM en source: {with_am:,}")
PYEOF

echo ""
echo "=== Generando SQL corregido ==="
python3 "$SCRIPT_DIR/generar_exportacion_subitems.py" \
    "$ZR9" \
    -m "$MES" \
    -o "$OUTPUT_DIR/subitems_${MES}.sql" \
    || { echo "Error generando SQL"; exit 1; }

echo "SQL generado en: $OUTPUT_DIR/subitems_${MES}.sql"

# Verificar sufijos AM en SQL generado (COPY text format, sin comillas en campos)
AM_COUNT=$(grep -c 'AM(' "$OUTPUT_DIR/subitems_${MES}.sql" 2>/dev/null || echo 0)
echo "Registros con AM en SQL generado: $AM_COUNT"

if [[ "$ENV" == "--staging" ]]; then
    echo ""
    echo "=== Carga en STAGING (requiere STAGING_DB env) ==="
    DB="${STAGING_DB:-tesys_staging}"
    echo "DB target: $DB"
    echo "Para aplicar en staging:"
    echo "  psql -d $DB -f $OUTPUT_DIR/subitems_${MES}.sql"
    echo ""
    echo "Verificación post-carga sugerida:"
    echo "  SELECT COUNT(*) FROM exportacion_subitems"
    echo "    WHERE DATE_TRUNC('month', fecha_oficializacion) = '$MES-01'::date"
    echo "    AND LENGTH(detalle_completo) > 100;"
elif [[ "$ENV" == "--prod" ]]; then
    echo ""
    echo "=== ADVERTENCIA: Carga en PRODUCCIÓN ==="
    read -rp "¿Confirmar recarga producción para mes $MES? [yes/N]: " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Cancelado."
        exit 0
    fi
    echo "Aplicar manualmente en el servidor:"
    echo "  scp $OUTPUT_DIR/subitems_${MES}.sql tesys-prod:/tmp/"
    echo "  ssh tesys-prod 'docker exec tesys-db psql -U tesys -d tesys -f /tmp/subitems_${MES}.sql'"
fi
