#!/usr/bin/env bash
# Genera SQL desde los impo_*.lst y los carga en la DB.
# Procesa los 12 meses de 2025 (OneDrive_2_22-7-2026).
#
# Uso:
#   ./cargar_lst_2025.sh             # local (docker)
#   ./cargar_lst_2025.sh prod        # producción via SSH
#
# Los ZIPs se descomprimen on-the-fly; el directorio 202501 ya viene descomprimido.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GENERADOR="$SCRIPT_DIR/generar_importacion_lst.py"
LST_DIR="/home/spawnmc/Code/TesysTMP/OneDrive_2_22-7-2026"
SQL_DIR="$REPO_ROOT/data/mensuales/lst_2025"
TARGET="${1:-local}"

mkdir -p "$SQL_DIR"

if [[ "$TARGET" == "prod" ]]; then
    PSQL="ssh tesys-prod docker exec -i tesys-backend-postgres-1 psql -U postgres -d comercio_exterior_argentina"
else
    PSQL="docker exec -i postgres_tesys psql -U postgres -d comercio_exterior_argentina"
fi

echo "Destino: $TARGET"
echo ""

for MES in 202501 202502 202503 202504 202505 202506 202507 202508 202509 202510 202511 202512; do
    LST_FILE=""
    TMPDIR_USED=""

    # 202501 ya viene descomprimido
    if [[ -f "$LST_DIR/$MES/impo_${MES}.lst" ]]; then
        LST_FILE="$LST_DIR/$MES/impo_${MES}.lst"
    elif [[ -f "$LST_DIR/${MES}.zip" ]]; then
        TMPDIR_USED=$(mktemp -d)
        echo "[$MES] Descomprimiendo..."
        unzip -q "$LST_DIR/${MES}.zip" "impo_${MES}.lst" -d "$TMPDIR_USED"
        LST_FILE="$TMPDIR_USED/impo_${MES}.lst"
    else
        echo "[$MES] SKIP: no se encuentra $LST_DIR/$MES.zip ni $LST_DIR/$MES/impo_${MES}.lst"
        continue
    fi

    SQL_FILE="$SQL_DIR/obl_lst_${MES}.sql"

    echo "[$MES] Generando SQL..."
    python3 "$GENERADOR" -i "$LST_FILE" -o "$SQL_FILE" -m "$MES"

    echo "[$MES] Cargando en DB..."
    $PSQL < "$SQL_FILE"
    echo "[$MES] OK"

    # Limpiar directorio temporal si se descomprimió
    if [[ -n "$TMPDIR_USED" ]]; then
        rm -rf "$TMPDIR_USED"
        # El SQL queda en SQL_DIR para auditoría (son ~200MB por mes; borrar si no se quieren)
    fi

    echo ""
done

echo "=== Resumen por concepto ==="
$PSQL -c "
SELECT concepto, obligacion, COUNT(*), SUM(monto)::numeric(18,2) AS total
FROM importacion_obligaciones
WHERE concepto NOT IN ('010', '056') OR obligacion NOT IN ('P','G','F','X')
GROUP BY concepto, obligacion
ORDER BY concepto, obligacion;
"
