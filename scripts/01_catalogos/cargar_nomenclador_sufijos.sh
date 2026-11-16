#!/usr/bin/env bash
# Carga la tabla nomenclador_sufijos desde el archivo AFIP (ISO-8859-1).
# Uso:
#   ./cargar_nomenclador_sufijos.sh [local|prod] [truncate|upsert]
#
#   truncate (default): TRUNCATE + INSERT — refleja exactamente el archivo AFIP
#   upsert:             INSERT ON CONFLICT — acumula históricos, no borra claves viejas
#
# Ejemplos:
#   ./cargar_nomenclador_sufijos.sh                    # local, truncate
#   ./cargar_nomenclador_sufijos.sh prod truncate      # prod, truncate
#   ./cargar_nomenclador_sufijos.sh local upsert       # local, upsert

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ARCHIVO="$REPO_ROOT/data/catalogos/sufijos_03082026.txt"

TARGET="${1:-local}"
MODE="${2:-truncate}"

if [[ "$TARGET" == "prod" ]]; then
    PSQL_CMD="ssh tesys-prod docker exec -i tesys-backend-postgres-1 psql -U postgres -d comercio_exterior_argentina"
else
    PSQL_CMD="docker exec -i postgres_tesys psql -U postgres -d comercio_exterior_argentina"
fi

echo "Destino : $TARGET"
echo "Archivo : $ARCHIVO"
echo "Modo    : $MODE"

if [[ ! -f "$ARCHIVO" ]]; then
    echo "ERROR: no se encuentra $ARCHIVO" >&2
    exit 1
fi

# Crear tabla e índice si no existen
$PSQL_CMD <<'EOSQL'
CREATE TABLE IF NOT EXISTS nomenclador_sufijos (
    tipo          smallint NOT NULL,
    posicion      text     NOT NULL,
    codigo_sufijo text     NOT NULL,
    regla         text,
    descripcion   text,
    PRIMARY KEY (tipo, posicion, codigo_sufijo)
);
CREATE INDEX IF NOT EXISTS idx_nomenclador_sufijos_codigo_posicion
    ON nomenclador_sufijos (codigo_sufijo, posicion);
EOSQL

# Convertir ISO-8859-1 → UTF-8 y generar TSV
echo "Procesando archivo..."
iconv -f ISO-8859-1 -t UTF-8 "$ARCHIVO" | python3 -c "
import sys
for line in sys.stdin:
    line = line.rstrip('\n')
    parts = line.split('@')
    if len(parts) < 5:
        continue
    if not parts[0].isdigit() or not parts[1] or not parts[2]:
        continue
    def esc(s): return s.replace('\t', ' ').replace('\n', ' ')
    print(f'{esc(parts[0])}\t{esc(parts[1])}\t{esc(parts[2])}\t{esc(parts[3])}\t{esc(parts[4].strip())}')
" > /tmp/sufijos_load.tsv

FILAS=$(wc -l < /tmp/sufijos_load.tsv)
echo "Filas a cargar: $FILAS"

# Construir SQL según modo y piping del TSV por STDIN a través de un heredoc psql
if [[ "$MODE" == "truncate" ]]; then
    {
        echo "TRUNCATE nomenclador_sufijos;"
        echo "CREATE TEMP TABLE tmp_ns (tipo smallint, posicion text, codigo_sufijo text, regla text, descripcion text);"
        echo "COPY tmp_ns FROM STDIN;"
        cat /tmp/sufijos_load.tsv
        echo '\.'
        echo "INSERT INTO nomenclador_sufijos SELECT * FROM tmp_ns;"
    } | $PSQL_CMD
else
    {
        echo "CREATE TEMP TABLE tmp_ns (tipo smallint, posicion text, codigo_sufijo text, regla text, descripcion text);"
        echo "COPY tmp_ns FROM STDIN;"
        cat /tmp/sufijos_load.tsv
        echo '\.'
        echo "INSERT INTO nomenclador_sufijos SELECT * FROM tmp_ns"
        echo "ON CONFLICT (tipo, posicion, codigo_sufijo) DO UPDATE"
        echo "    SET regla = EXCLUDED.regla, descripcion = EXCLUDED.descripcion;"
    } | $PSQL_CMD
fi

rm /tmp/sufijos_load.tsv

echo "Listo."
$PSQL_CMD -c "SELECT COUNT(*) AS total_filas FROM nomenclador_sufijos;"
