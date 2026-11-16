#!/bin/bash
# ==============================================================================
# Script: generar_sql_todos_meses.sh
# Descripción: Genera SQL para todos los meses de 2025 que tengan datos
# Uso: ./generar_sql_todos_meses.sh
# ==============================================================================

BASE_DIR="${TESYS_DATA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     Generación Masiva de Scripts SQL - Todos los Meses 2025     ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Meses a procesar (Febrero a Agosto 2025)
MESES=(
    "202502"
    "202503"
    "202504"
    "202505"
    "202506"
    "202507"
    "202508"
)

TOTAL_PROCESADOS=0
TOTAL_SCRIPTS=0

for PERIODO in "${MESES[@]}"; do
    echo ""
    echo "────────────────────────────────────────────────────────────────"

    # Ejecutar script individual para cada mes
    if "$BASE_DIR/scripts/generar_sql_mes.sh" "$PERIODO"; then
        ((TOTAL_PROCESADOS++))
    fi

    echo "────────────────────────────────────────────────────────────────"
done

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                        RESUMEN FINAL                             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "  Meses procesados:     $TOTAL_PROCESADOS / ${#MESES[@]}"
echo ""
echo "  Scripts generados en:"
echo "    data/mensuales/2025/*/sql/"
echo ""
echo "✓ Generación masiva completada"
echo ""
echo "Próximos pasos:"
echo "1. Revisar logs de errores (si los hay)"
echo "2. Importar a DB: ./scripts/importar_sql_mes.sh [PERIODO]"
echo "3. Generar reportes"
echo ""
