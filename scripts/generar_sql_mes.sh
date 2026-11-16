#!/bin/bash
# ==============================================================================
# Script: generar_sql_mes.sh
# Descripción: Genera scripts SQL para un mes específico
# Uso: ./generar_sql_mes.sh YYYYMM
# Ejemplo: ./generar_sql_mes.sh 202502
# ==============================================================================

# No usar set -e para continuar aunque haya errores

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 PERIODO"
    echo "Ejemplo: $0 202502 (para Febrero 2025)"
    exit 1
fi

PERIODO=$1
ANIO=${PERIODO:0:4}
MES=${PERIODO:4:2}

# Mapear número de mes a nombre
case $MES in
    01) MES_NOMBRE="enero" ;;
    02) MES_NOMBRE="febrero" ;;
    03) MES_NOMBRE="marzo" ;;
    04) MES_NOMBRE="abril" ;;
    05) MES_NOMBRE="mayo" ;;
    06) MES_NOMBRE="junio" ;;
    07) MES_NOMBRE="julio" ;;
    08) MES_NOMBRE="agosto" ;;
    09) MES_NOMBRE="septiembre" ;;
    10) MES_NOMBRE="octubre" ;;
    11) MES_NOMBRE="noviembre" ;;
    12) MES_NOMBRE="diciembre" ;;
    *) echo "Error: Mes inválido"; exit 1 ;;
esac

BASE_DIR="${TESYS_DATA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
MES_DIR="${BASE_DIR}/data/mensuales/${ANIO}/${MES}_${MES_NOMBRE}"
SQL_DIR="${MES_DIR}/sql"
SCRIPTS_DIR="${BASE_DIR}/scripts/02_importador"

echo "=================================================================="
echo "  Generando SQL para ${MES_NOMBRE^^} ${ANIO} (Período: $PERIODO)"
echo "=================================================================="
echo ""

# Verificar que existe el directorio
if [ ! -d "$MES_DIR/raw/importacion" ]; then
    echo "Error: No existe $MES_DIR/raw/importacion"
    exit 1
fi

# Crear directorio SQL
mkdir -p "$SQL_DIR"

# Buscar quincenas
QUINCENAS=($(find "$MES_DIR/raw/importacion" -maxdepth 1 -type d -name "${PERIODO}Impo*" | sort))

if [ ${#QUINCENAS[@]} -eq 0 ]; then
    echo "Error: No se encontraron quincenas en $MES_DIR/raw/importacion"
    exit 1
fi

echo "Quincenas encontradas: ${#QUINCENAS[@]}"
echo ""

TOTAL_SCRIPTS=0

# Procesar cada quincena
for i in "${!QUINCENAS[@]}"; do
    QUINCENA_DIR="${QUINCENAS[$i]}"
    QUINCENA_NOMBRE=$(basename "$QUINCENA_DIR")
    Q_NUM=$((i+1))

    echo "=== QUINCENA $Q_NUM: $QUINCENA_NOMBRE ==="
    echo ""

    # 1. Despachos (zR1.txt)
    if [ -f "$QUINCENA_DIR/zR1.txt" ]; then
        echo -n "  1/5 Despachos (zR1)... "
        if python3 "$SCRIPTS_DIR/generar_importacion_despachos.py" \
            "$QUINCENA_DIR/zR1.txt" \
            -o "$SQL_DIR/importacion_despachos_${PERIODO}_q${Q_NUM}.sql" > /dev/null 2>&1; then
            echo "✓"
            ((TOTAL_SCRIPTS++))
        else
            echo "✗"
        fi
    else
        echo "  1/5 Despachos (zR1)... ⊘ (no encontrado)"
    fi

    # 2. Items (zR5.txt) - Nota: -o ANTES del input_file
    if [ -f "$QUINCENA_DIR/zR5.txt" ]; then
        echo -n "  2/5 Items (zR5)... "
        if python3 "$SCRIPTS_DIR/generar_importacion_items.py" \
            -o "$SQL_DIR/importacion_items_${PERIODO}_q${Q_NUM}.sql" \
            "$QUINCENA_DIR/zR5.txt" > /dev/null 2>&1; then
            echo "✓"
            ((TOTAL_SCRIPTS++))
        else
            echo "✗"
        fi
    else
        echo "  2/5 Items (zR5)... ⊘ (no encontrado)"
    fi

    # 3. Subitems (zR9.txt) - Nota: -o ANTES del input_file
    if [ -f "$QUINCENA_DIR/zR9.txt" ]; then
        echo -n "  3/5 Subitems (zR9)... "
        if python3 "$SCRIPTS_DIR/generar_importacion_subitems.py" \
            -o "$SQL_DIR/importacion_subitems_${PERIODO}_q${Q_NUM}.sql" \
            "$QUINCENA_DIR/zR9.txt" > /dev/null 2>&1; then
            echo "✓"
            ((TOTAL_SCRIPTS++))
        else
            echo "✗"
        fi
    else
        echo "  3/5 Subitems (zR9)... ⊘ (no encontrado)"
    fi

    # 4. Obligaciones (zRA.txt)
    if [ -f "$QUINCENA_DIR/zRA.txt" ]; then
        echo -n "  4/5 Obligaciones (zRA)... "
        if python3 "$SCRIPTS_DIR/generar_importacion_obligaciones.py" \
            -i "$QUINCENA_DIR/zRA.txt" \
            -o "$SQL_DIR/importacion_obligaciones_${PERIODO}_q${Q_NUM}.sql" \
            -m "$PERIODO" > /dev/null 2>&1; then
            echo "✓"
            ((TOTAL_SCRIPTS++))
        else
            echo "✗"
        fi
    else
        echo "  4/5 Obligaciones (zRA)... ⊘ (no encontrado)"
    fi

    # 5. Ventajas (zR8.txt)
    if [ -f "$QUINCENA_DIR/zR8.txt" ]; then
        echo -n "  5/5 Ventajas (zR8)... "
        if python3 "$SCRIPTS_DIR/generar_importacion_ventajas.py" \
            -i "$QUINCENA_DIR/zR8.txt" \
            -o "$SQL_DIR/importacion_ventajas_${PERIODO}_q${Q_NUM}.sql" \
            -m "$PERIODO" > /dev/null 2>&1; then
            echo "✓"
            ((TOTAL_SCRIPTS++))
        else
            echo "✗"
        fi
    else
        echo "  5/5 Ventajas (zR8)... ⊘ (no encontrado)"
    fi

    echo ""
done

# Proveedores
echo "=== PROVEEDORES ==="
ARCHIVO_PROV=$(find "$MES_DIR/raw/proveedores" -iname "ProvMes*.txt" 2>/dev/null | head -1)

if [ -n "$ARCHIVO_PROV" ]; then
    echo -n "Proveedores ($(basename $ARCHIVO_PROV))... "
    if python3 "$SCRIPTS_DIR/generar_importacion_auxiliar.py" \
        "$ARCHIVO_PROV" \
        -o "$SQL_DIR/proveedores_${PERIODO}.sql" > /dev/null 2>&1; then
        echo "✓"
        ((TOTAL_SCRIPTS++))
    else
        echo "✗"
    fi
else
    echo "Proveedores... ⊘ (no encontrado)"
fi

echo ""
echo "=================================================================="
echo "✓ Generación completada para $MES_NOMBRE $ANIO"
echo ""
echo "Scripts generados: $TOTAL_SCRIPTS"
echo "Ubicación: $SQL_DIR"
echo ""
echo "Archivos:"
ls -1 "$SQL_DIR"/*.sql 2>/dev/null | sed 's|.*/|  - |' || echo "  (ninguno)"
echo ""
echo "Tamaño total:"
du -sh "$SQL_DIR" 2>/dev/null || echo "  0B"
echo ""
