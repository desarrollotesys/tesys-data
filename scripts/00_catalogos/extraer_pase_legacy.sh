#!/usr/bin/env bash
# extraer_pase_legacy.sh
# ======================
# Extrae PASEFLETE, PASESEGURO y monedas de las tablas cabi{YY} del sistema
# legacy (MySQL en te-sys.com.ar, usuario read-only) y genera el lookup que
# usa calcular_item_calculos.py.
#
# Credenciales via variables de entorno:
#   TESYS_SSH_HOST       (default: root@te-sys.com.ar)
#   TESYS_MYSQL_USER     (default: tesys_readonly)
#   MYSQL_PWD            (password; sin default — REQUERIDO)
#   TESYS_MYSQL_DB       (default: asisa)
#
# Ejemplo de uso:
#   export MYSQL_PWD=<password>
#   bash scripts/00_catalogos/extraer_pase_legacy.sh            # años 22-26
#   bash scripts/00_catalogos/extraer_pase_legacy.sh 25 26      # solo 2025-2026
#
# Output:
#   data/catalogos/pase_legacy_cabi22_26.tsv.gz
#   Formato TSV sin header:
#     DESTINACION  PASEFLETE  PASESEGURO  MONEDAFOB  MONEDAFLETE  MONEDASEGURO
#   Incluye TODOS los despachos (incluso DOL/DOL) para cubrir el caso
#   FOB=DOL/FLETE=DOL pero SEGURO≠DOL, donde PASESEGURO sí importa.
#
# IMPORTANTE: el archivo resultante NO se commitea al repo (está en .gitignore).
# Regenerar cuando la base legacy avanza o se recalculan los pases.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
OUTPUT="$REPO_DIR/data/catalogos/pase_legacy_cabi22_26.tsv.gz"

SSH_HOST="${TESYS_SSH_HOST:-root@te-sys.com.ar}"
MYSQL_USER="${TESYS_MYSQL_USER:-tesys_readonly}"
MYSQL_DB="${TESYS_MYSQL_DB:-asisa}"

# MYSQL_PWD debe venir del entorno — no tiene default hardcodeado
if [ -z "${MYSQL_PWD:-}" ]; then
    echo "ERROR: MYSQL_PWD no está definida." >&2
    echo "  export MYSQL_PWD=<password> y volvé a ejecutar." >&2
    exit 1
fi

# Años a exportar (default: 22 23 24 25 26)
ANIOS="${*:-22 23 24 25 26}"

mkdir -p "$(dirname "$OUTPUT")"

echo "Extrayendo PASEFLETE/PASESEGURO+monedas de cabi{YY} para años: $ANIOS"
echo "Output: $OUTPUT"

# Construir queries por tabla separadas con ';' para que mysql las ejecute en
# secuencia. Se exportan TODOS los despachos para cubrir el caso en que
# FOB=DOL/FLETE=DOL pero SEGURO≠DOL (PASESEGURO sí necesita lookup).
QUERY=""
for anio in $ANIOS; do
    if [ -n "$QUERY" ]; then
        QUERY="${QUERY};"
    fi
    QUERY="${QUERY}SELECT DESTINACION, ROUND(PASEFLETE,8), ROUND(PASESEGURO,8), MONEDAFOB, MONEDAFLETE, MONEDASEGURO FROM cabi${anio}"
done

echo "Conectando a $SSH_HOST..."
# shellcheck disable=SC2029
ssh -o StrictHostKeyChecking=no "$SSH_HOST" \
    "MYSQL_PWD='${MYSQL_PWD}' mysql -u ${MYSQL_USER} ${MYSQL_DB} --batch --skip-column-names -e \"${QUERY}\"" \
    2>/dev/null \
    | gzip > "$OUTPUT"

LINEAS=$(zcat "$OUTPUT" | wc -l)
SIZE=$(ls -lh "$OUTPUT" | awk '{print $5}')
echo "OK: $LINEAS líneas, $SIZE comprimido"
echo "Archivo listo: $OUTPUT"
