#!/bin/bash
#
# Script para cargar datos de exportación en PostgreSQL via Docker
# Uso: ./cargar_exportacion_docker.sh YYYYMM [CONTAINER] [USER] [DB]
# Ejemplo: ./cargar_exportacion_docker.sh 202501
#

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Parámetros con valores por defecto
PERIODO=$1
CONTAINER_NAME=${2:-postgres_tesys}
DB_USER=${3:-postgres}
DB_NAME=${4:-comercio_exterior_argentina}

if [ -z "$PERIODO" ]; then
    log_error "Uso: $0 PERIODO [CONTAINER] [USER] [DB]"
    echo "Ejemplo: $0 202501"
    echo "Ejemplo: $0 202501 postgres_tesys postgres comercio_exterior_argentina"
    exit 1
fi

SQL_DIR="output/exportacion/${PERIODO}"

if [ ! -d "$SQL_DIR" ]; then
    log_error "Directorio no encontrado: $SQL_DIR"
    log_warn "Primero ejecuta: ./scripts/generar_sql_exportacion_mes.sh ${PERIODO:0:4} ${PERIODO:4:2}"
    exit 1
fi

log_info "=============================================="
log_info "Cargando Exportación ${PERIODO} en Docker"
log_info "=============================================="
log_info "Contenedor: $CONTAINER_NAME"
log_info "Base de datos: $DB_NAME"
log_info "Usuario: $DB_USER"
echo ""

# Verificar que el contenedor esté corriendo
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    log_error "Contenedor '$CONTAINER_NAME' no está corriendo"
    log_info "Contenedores disponibles:"
    docker ps --format "  - {{.Names}}"
    exit 1
fi

# Verificar conexión a la base de datos
log_info "Verificando conexión a la base de datos..."
if ! docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    log_error "No se puede conectar a la base de datos"
    exit 1
fi
log_info "✓ Conexión exitosa"
echo ""

# Mostrar estado antes de la carga
log_info "Estado antes de la carga:"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
  (SELECT COUNT(*) FROM exportacion_despachos) as despachos,
  (SELECT COUNT(*) FROM exportacion_items) as items,
  (SELECT COUNT(*) FROM exportacion_ventajas) as ventajas,
  (SELECT COUNT(*) FROM exportacion_subitems) as subitems;
"
echo ""

# Array de tablas en orden de carga
declare -a TABLAS=("despachos" "items" "ventajas" "subitems")

# Cargar cada tabla
for i in "${!TABLAS[@]}"; do
    tabla="${TABLAS[$i]}"
    num=$((i+1))
    archivo="${SQL_DIR}/exportacion_${tabla}_${PERIODO}.sql"

    if [ ! -f "$archivo" ]; then
        log_error "Archivo no encontrado: $archivo"
        exit 1
    fi

    log_info "[$num/4] Cargando exportacion_${tabla}..."

    # Ejecutar SQL
    if docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$archivo" > /dev/null 2>&1; then
        log_info "✓ exportacion_${tabla} cargado exitosamente"
    else
        log_error "✗ Error cargando exportacion_${tabla}"
        log_warn "Ejecuta manualmente para ver el error:"
        echo "  docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME < $archivo"
        exit 1
    fi

    echo ""
done

log_info "=============================================="
log_info "Carga Completada Exitosamente"
log_info "=============================================="
echo ""

# Mostrar estado después de la carga
log_info "Estado después de la carga:"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
  (SELECT COUNT(*) FROM exportacion_despachos) as despachos,
  (SELECT COUNT(*) FROM exportacion_items) as items,
  (SELECT COUNT(*) FROM exportacion_ventajas) as ventajas,
  (SELECT COUNT(*) FROM exportacion_subitems) as subitems;
"
echo ""

# Mostrar estadísticas del periodo cargado
log_info "Estadísticas del periodo ${PERIODO}:"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
  (SELECT COUNT(*) FROM exportacion_despachos WHERE anio = ${PERIODO:0:4} AND EXTRACT(MONTH FROM fecha_oficializacion) = ${PERIODO:4:2}) as despachos_${PERIODO},
  (SELECT COUNT(*) FROM exportacion_items WHERE EXTRACT(YEAR FROM fecha_oficializacion) = ${PERIODO:0:4} AND EXTRACT(MONTH FROM fecha_oficializacion) = ${PERIODO:4:2}) as items_${PERIODO},
  (SELECT COUNT(*) FROM exportacion_ventajas WHERE EXTRACT(YEAR FROM fecha_oficializacion) = ${PERIODO:0:4} AND EXTRACT(MONTH FROM fecha_oficializacion) = ${PERIODO:4:2}) as ventajas_${PERIODO},
  (SELECT COUNT(*) FROM exportacion_subitems WHERE EXTRACT(YEAR FROM fecha_oficializacion) = ${PERIODO:0:4} AND EXTRACT(MONTH FROM fecha_oficializacion) = ${PERIODO:4:2}) as subitems_${PERIODO};
"

log_info "Proceso completado!"
exit 0
