#!/bin/bash
# ==============================================================================
# Script: batch_generar_sql_todos_meses.sh
# Descripción: Genera scripts SQL para todos los meses de 2025 con datos
# Uso: ./batch_generar_sql_todos_meses.sh [año]
# ==============================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ANIO=${1:-2025}
BASE_DIR="${TESYS_DATA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SCRIPTS_DIR="$BASE_DIR/scripts/02_importador"

# Meses a procesar
declare -A MESES=(
    ["01"]="enero"
    ["02"]="febrero"
    ["03"]="marzo"
    ["04"]="abril"
    ["05"]="mayo"
    ["06"]="junio"
    ["07"]="julio"
    ["08"]="agosto"
    ["09"]="septiembre"
    ["10"]="octubre"
    ["11"]="noviembre"
    ["12"]="diciembre"
)

# Contadores
TOTAL_MESES=0
MESES_PROCESADOS=0
MESES_SALTADOS=0
TOTAL_SCRIPTS=0

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Generación Masiva de Scripts SQL - Año $ANIO                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Función para procesar un mes
procesar_mes() {
    local num_mes=$1
    local nombre_mes=$2
    local mes_dir="${BASE_DIR}/data/mensuales/${ANIO}/${num_mes}_${nombre_mes}"
    local sql_dir="${mes_dir}/sql"
    local periodo="${ANIO}${num_mes}"

    echo -e "${YELLOW}═══ Procesando ${num_mes}_${nombre_mes} (${periodo}) ═══${NC}"

    # Verificar si hay datos
    if [ ! -d "$mes_dir/raw/importacion" ]; then
        echo -e "${RED}  ✗ No existe carpeta de importación${NC}"
        ((MESES_SALTADOS++))
        return
    fi

    # Buscar quincenas
    local quincenas=($(find "$mes_dir/raw/importacion" -type d -name "${periodo}Impo*" | sort))

    if [ ${#quincenas[@]} -eq 0 ]; then
        echo -e "${RED}  ✗ No se encontraron carpetas de quincenas${NC}"
        ((MESES_SALTADOS++))
        return
    fi

    echo -e "  📂 Quincenas encontradas: ${#quincenas[@]}"

    # Crear directorio sql si no existe
    mkdir -p "$sql_dir"

    local scripts_generados=0

    # Procesar cada quincena
    for quincena_dir in "${quincenas[@]}"; do
        local quincena_nombre=$(basename "$quincena_dir")
        echo -e "  ${BLUE}→ $quincena_nombre${NC}"

        # 1. DESPACHOS (zR1)
        if [ -f "$quincena_dir/zR1.txt" ]; then
            echo -n "     Despachos (zR1)... "
            if python3 "$SCRIPTS_DIR/generar_importacion_despachos.py" \
                "$quincena_dir/zR1.txt" \
                "$sql_dir/importacion_despachos_${periodo}_${quincena_nombre}.sql" \
                "$periodo" > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC}"
                ((scripts_generados++))
            else
                echo -e "${RED}✗${NC}"
            fi
        fi

        # 2. ITEMS (zR5)
        if [ -f "$quincena_dir/zR5.txt" ]; then
            echo -n "     Items (zR5)... "
            if python3 "$SCRIPTS_DIR/generar_importacion_items.py" \
                "$quincena_dir/zR5.txt" \
                "$sql_dir/importacion_items_${periodo}_${quincena_nombre}.sql" \
                "$periodo" > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC}"
                ((scripts_generados++))
            else
                echo -e "${RED}✗${NC}"
            fi
        fi

        # 3. SUBITEMS (zR9)
        if [ -f "$quincena_dir/zR9.txt" ]; then
            echo -n "     Subitems (zR9)... "
            if python3 "$SCRIPTS_DIR/generar_importacion_subitems.py" \
                "$quincena_dir/zR9.txt" \
                "$sql_dir/importacion_subitems_${periodo}_${quincena_nombre}.sql" \
                "$periodo" > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC}"
                ((scripts_generados++))
            else
                echo -e "${RED}✗${NC}"
            fi
        fi

        # 4. OBLIGACIONES (zR8)
        if [ -f "$quincena_dir/zR8.txt" ]; then
            echo -n "     Obligaciones (zR8)... "
            if python3 "$SCRIPTS_DIR/generar_importacion_obligaciones.py" \
                "$quincena_dir/zR8.txt" \
                "$sql_dir/importacion_obligaciones_${periodo}_${quincena_nombre}.sql" \
                "$periodo" > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC}"
                ((scripts_generados++))
            else
                echo -e "${RED}✗${NC}"
            fi
        fi

        # 5. VENTAJAS (zR6 o zRA)
        local archivo_ventajas=""
        if [ -f "$quincena_dir/zR6.txt" ]; then
            archivo_ventajas="$quincena_dir/zR6.txt"
        elif [ -f "$quincena_dir/zRA.txt" ]; then
            archivo_ventajas="$quincena_dir/zRA.txt"
        fi

        if [ -n "$archivo_ventajas" ]; then
            echo -n "     Ventajas ($(basename $archivo_ventajas))... "
            if python3 "$SCRIPTS_DIR/generar_importacion_ventajas.py" \
                "$archivo_ventajas" \
                "$sql_dir/importacion_ventajas_${periodo}_${quincena_nombre}.sql" \
                "$periodo" > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC}"
                ((scripts_generados++))
            else
                echo -e "${RED}✗${NC}"
            fi
        fi
    done

    # 6. PROVEEDORES (ProvMes*.txt)
    local archivo_prov=$(find "$mes_dir/raw/proveedores" -name "ProvMes*.txt" -o -name "provMes*.txt" 2>/dev/null | head -1)
    if [ -n "$archivo_prov" ]; then
        echo -n "  Proveedores ($(basename $archivo_prov))... "
        if python3 "$SCRIPTS_DIR/generar_importacion_auxiliar.py" \
            "$archivo_prov" \
            "$sql_dir/proveedores_${periodo}.sql" \
            "$periodo" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC}"
            ((scripts_generados++))
        else
            echo -e "${RED}✗${NC}"
        fi
    fi

    echo -e "  ${GREEN}✓ Scripts generados: $scripts_generados${NC}"
    echo ""

    ((MESES_PROCESADOS++))
    ((TOTAL_SCRIPTS += scripts_generados))
}

# Procesar cada mes
for num_mes in $(seq -w 1 12); do
    nombre_mes=${MESES[$num_mes]}
    ((TOTAL_MESES++))
    procesar_mes "$num_mes" "$nombre_mes"
done

# Resumen final
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                      RESUMEN FINAL                               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Total meses evaluados:    ${TOTAL_MESES}"
echo -e "  ${GREEN}Meses procesados:         ${MESES_PROCESADOS}${NC}"
echo -e "  ${YELLOW}Meses saltados:           ${MESES_SALTADOS}${NC}"
echo -e "  ${GREEN}Total scripts generados:  ${TOTAL_SCRIPTS}${NC}"
echo ""
echo -e "${GREEN}✓ Proceso completado${NC}"
echo ""
echo "Próximos pasos:"
echo "1. Revisar scripts en: data/mensuales/2025/*/sql/"
echo "2. Importar a DB (ver script: batch_importar_todos_meses.sh)"
echo ""
