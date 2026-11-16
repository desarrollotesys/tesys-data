#!/usr/bin/env python3
"""
Script para generar SQL de exportacion subitems desde zR9.txt
Genera comandos COPY seguros para PostgreSQL

Archivo fuente: zR9.txt (exportación)
Tabla destino: exportacion_subitems

Estructura del archivo zR9 (pipe-delimited, sin header):
0. DESTINACION (despacho_id)
1. ITEM (item_id)
2. SUBITEM (subitem_id)
3. DETALLE (detalle_completo con sufijos)
4. CANTIDADUNIDADESSUBITEM
5. FOBDOLSUBITEM

NOTA: La fecha_oficializacion se obtiene mediante JOIN con exportacion_items
durante el proceso de carga SQL.

Autor: Sistema automatizado
Fecha: 2025-01-10
"""

import sys
import csv
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal, InvalidOperation

class ExportacionSubitemsProcessor:
    """
    Procesador para archivos zR9.txt (subitems de exportacion)
    """

    def __init__(self, mes_archivo: str):
        # Validar formato mes_archivo (YYYYMM)
        if not mes_archivo or len(mes_archivo) != 6 or not mes_archivo.isdigit():
            raise ValueError(f"mes_archivo debe ser formato YYYYMM (ej: 202301), recibido: {mes_archivo}")
        self.mes_archivo = mes_archivo

        self.total_procesados = 0
        self.total_validos = 0
        self.total_errores = 0
        self.errores = []

    def limpiar_campo(self, valor: str) -> Optional[str]:
        """
        Limpia campo de texto
        """
        if not valor:
            return None
        valor_limpio = valor.strip().strip('"')
        return valor_limpio if valor_limpio else None

    def convertir_decimal(self, valor: str, decimales: int = 2) -> Optional[str]:
        """
        Convierte string a decimal validado
        """
        try:
            if not valor:
                return None
            valor_limpio = valor.strip().strip('"')
            if not valor_limpio:
                return None

            decimal_val = Decimal(valor_limpio)
            return str(decimal_val)
        except (InvalidOperation, ValueError):
            return None

    def procesar_registro(self, row: List[str], linea_num: int) -> Optional[Dict[str, Any]]:
        """
        Procesa un registro del archivo zR9
        """
        try:
            if len(row) < 6:
                self.errores.append(f"Linea {linea_num}: Numero incorrecto de campos ({len(row)} < 6)")
                return None

            # Extraer campos
            despacho_id = self.limpiar_campo(row[0])
            item_id = self.limpiar_campo(row[1])
            subitem_id = self.limpiar_campo(row[2])
            detalle_completo_raw = self.limpiar_campo(row[3])
            detalle_completo = detalle_completo_raw if detalle_completo_raw else None
            cantidad_unidades_subitem = row[4]
            fob_dolar_subitem = row[5]

            # Validaciones obligatorias
            if not despacho_id or len(despacho_id) != 16:
                self.errores.append(f"Linea {linea_num}: despacho_id invalido")
                return None

            if not item_id:
                self.errores.append(f"Linea {linea_num}: item_id faltante")
                return None

            if not subitem_id:
                self.errores.append(f"Linea {linea_num}: subitem_id faltante")
                return None

            # detalle_completo puede estar vacío, pero al menos debe ser string vacío
            if detalle_completo is None:
                detalle_completo = ''

            # Convertir numericos (opcionales)
            cantidad_unidades_subitem_val = self.convertir_decimal(cantidad_unidades_subitem, 3)
            fob_dolar_subitem_val = self.convertir_decimal(fob_dolar_subitem, 2)

            return {
                'despacho_id': despacho_id,
                'item_id': item_id,
                'subitem_id': subitem_id,
                'detalle_completo': detalle_completo,
                'cantidad_unidades_subitem': cantidad_unidades_subitem_val,
                'fob_dolar_subitem': fob_dolar_subitem_val
            }

        except Exception as e:
            self.errores.append(f"Linea {linea_num}: Error: {str(e)}")
            return None

    def formatear_valor_copy(self, valor: Any, allow_empty_string: bool = False) -> str:
        """
        Formatea valor para COPY
        allow_empty_string: Si es True, '' se mantiene como string vacío en lugar de NULL
        """
        if valor is None:
            return '\\N'
        if valor == '' and not allow_empty_string:
            return '\\N'
        # Escapar tabs, newlines y backslashes para formato COPY
        valor_str = str(valor)
        valor_str = valor_str.replace('\\', '\\\\')
        valor_str = valor_str.replace('\t', '\\t')
        valor_str = valor_str.replace('\n', '\\n')
        valor_str = valor_str.replace('\r', '\\r')
        return valor_str

    def procesar_archivo(self, input_file: Path, output_file: Path):
        """
        Procesa archivo zR9 y genera SQL
        """
        print(f"Procesando archivo: {input_file}")
        print(f"Salida SQL: {output_file}")

        registros_validos = []

        # Detectar encoding
        encoding = 'utf-8'
        try:
            with open(input_file, 'r', encoding=encoding) as f:
                f.read(1024)
        except UnicodeDecodeError:
            encoding = 'latin-1'
            print(f"Advertencia: UTF-8 fallo, usando {encoding}")

        with open(input_file, 'r', encoding=encoding, errors='replace') as f:
            reader = csv.reader(f, delimiter='|')

            linea_num = 1
            for row in reader:
                self.total_procesados += 1

                registro = self.procesar_registro(row, linea_num)
                if registro:
                    registros_validos.append(registro)
                    self.total_validos += 1
                else:
                    self.total_errores += 1

                if self.total_procesados % 50000 == 0:
                    print(f"Procesados: {self.total_procesados} registros...")

                linea_num += 1

        print(f"\nGenerando SQL...")
        self.generar_sql(registros_validos, output_file)
        self.mostrar_resumen()

    def generar_sql(self, registros: List[Dict[str, Any]], output_file: Path):
        """
        Genera archivo SQL con comandos COPY usando staging
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            # Header
            f.write("-- =====================================================\n")
            f.write("-- EXPORTACION SUBITEMS - CARGA VIA STAGING\n")
            f.write(f"-- Mes archivo: {self.mes_archivo}\n")
            f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Registros: {len(registros)}\n")
            f.write("-- =====================================================\n\n")

            f.write("-- NOTA: Este archivo requiere que exportacion_items ya esté cargado\n")
            f.write("-- La fecha_oficializacion y mes_archivo se obtienen mediante JOIN\n\n")

            # Crear tabla staging
            f.write("-- Crear tabla staging temporal\n")
            f.write("DROP TABLE IF EXISTS staging_exportacion_subitems;\n\n")
            f.write("CREATE TEMPORARY TABLE staging_exportacion_subitems (\n")
            f.write("    despacho_id VARCHAR(16),\n")
            f.write("    item_id VARCHAR(10),\n")
            f.write("    subitem_id VARCHAR(10),\n")
            f.write("    detalle_completo TEXT,\n")
            f.write("    cantidad_unidades_subitem DECIMAL(15,3),\n")
            f.write("    fob_dolar_subitem DECIMAL(15,2)\n")
            f.write(");\n\n")

            # Comando COPY a staging
            f.write("-- Cargar datos en staging\n")
            f.write("COPY staging_exportacion_subitems (\n")
            f.write("    despacho_id,\n")
            f.write("    item_id,\n")
            f.write("    subitem_id,\n")
            f.write("    detalle_completo,\n")
            f.write("    cantidad_unidades_subitem,\n")
            f.write("    fob_dolar_subitem\n")
            f.write(") FROM stdin;\n")

            # Datos
            for registro in registros:
                linea = '\t'.join([
                    self.formatear_valor_copy(registro['despacho_id']),
                    self.formatear_valor_copy(registro['item_id']),
                    self.formatear_valor_copy(registro['subitem_id']),
                    self.formatear_valor_copy(registro['detalle_completo'], allow_empty_string=True),  # NOT NULL, permitir ''
                    self.formatear_valor_copy(registro['cantidad_unidades_subitem']),
                    self.formatear_valor_copy(registro['fob_dolar_subitem'])
                ])
                f.write(linea + '\n')

            f.write("\\.\n\n")

            # Insertar en tabla final con JOIN para obtener fecha_oficializacion y mes_archivo
            f.write("-- Insertar en tabla final con fecha_oficializacion y mes_archivo desde exportacion_items\n")
            f.write("INSERT INTO exportacion_subitems (\n")
            f.write("    despacho_id,\n")
            f.write("    fecha_oficializacion,\n")
            f.write("    mes_archivo,\n")
            f.write("    item_id,\n")
            f.write("    subitem_id,\n")
            f.write("    detalle_completo,\n")
            f.write("    cantidad_unidades_subitem,\n")
            f.write("    fob_dolar_subitem\n")
            f.write(")\n")
            f.write("SELECT\n")
            f.write("    s.despacho_id,\n")
            f.write("    i.fecha_oficializacion,\n")
            f.write(f"    '{self.mes_archivo}',\n")
            f.write("    s.item_id,\n")
            f.write("    s.subitem_id,\n")
            f.write("    s.detalle_completo,\n")
            f.write("    s.cantidad_unidades_subitem,\n")
            f.write("    s.fob_dolar_subitem\n")
            f.write("FROM staging_exportacion_subitems s\n")
            f.write("INNER JOIN exportacion_items i\n")
            f.write("    ON s.despacho_id = i.despacho_id\n")
            f.write("    AND s.item_id = i.item_id\n")
            f.write(f"    AND i.mes_archivo = '{self.mes_archivo}'\n")
            f.write("ON CONFLICT (despacho_id, fecha_oficializacion, mes_archivo, item_id, subitem_id) DO NOTHING;\n\n")

            # Reportar items sin match
            f.write("-- Verificar items sin match (no deberían existir en un proceso normal)\n")
            f.write("DO $$\n")
            f.write("DECLARE\n")
            f.write("    items_sin_match INTEGER;\n")
            f.write("BEGIN\n")
            f.write("    SELECT COUNT(*) INTO items_sin_match\n")
            f.write("    FROM staging_exportacion_subitems s\n")
            f.write("    LEFT JOIN exportacion_items i\n")
            f.write("        ON s.despacho_id = i.despacho_id\n")
            f.write("        AND s.item_id = i.item_id\n")
            f.write("    WHERE i.despacho_id IS NULL;\n")
            f.write("    \n")
            f.write("    IF items_sin_match > 0 THEN\n")
            f.write("        RAISE WARNING 'Se encontraron % subitems sin item correspondiente en exportacion_items', items_sin_match;\n")
            f.write("        RAISE WARNING 'Esto puede indicar que falta cargar datos de exportacion_items';\n")
            f.write("    ELSE\n")
            f.write("        RAISE NOTICE 'Todos los subitems tienen items correspondientes';\n")
            f.write("    END IF;\n")
            f.write("END $$;\n\n")

            # Limpiar staging
            f.write("-- Limpiar staging\n")
            f.write("DROP TABLE staging_exportacion_subitems;\n\n")

            # Estadísticas finales
            f.write("-- Estadisticas finales\n")
            f.write("SELECT\n")
            f.write("    'Total subitems cargados' as metrica,\n")
            f.write("    COUNT(*) as cantidad\n")
            f.write("FROM exportacion_subitems;\n\n")

            f.write("-- Ejemplo de consulta de sufijos parseados\n")
            f.write("-- SELECT despacho_id, item_id, subitem_id, marca, modelo, version, presentacion\n")
            f.write("-- FROM exportacion_subitems\n")
            f.write("-- WHERE marca IS NOT NULL\n")
            f.write("-- LIMIT 10;\n\n")

            f.write("-- Fin de carga\n")

    def mostrar_resumen(self):
        """
        Muestra resumen del procesamiento
        """
        print("\n" + "="*60)
        print("RESUMEN DE PROCESAMIENTO")
        print("="*60)
        print(f"Total registros procesados: {self.total_procesados}")
        print(f"Registros validos:          {self.total_validos}")
        print(f"Registros con errores:      {self.total_errores}")

        if self.errores:
            print(f"\nSe encontraron {len(self.errores)} errores:")
            for i, error in enumerate(self.errores[:10], 1):
                print(f"  {i}. {error}")
            if len(self.errores) > 10:
                print(f"  ... y {len(self.errores) - 10} errores mas")

        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Genera SQL para carga de exportacion_subitems desde zR9.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python3 generar_exportacion_subitems.py zR9.txt -m 202301 -o output.sql
  python3 generar_exportacion_subitems.py data/mensuales/2023/01_enero/raw/exportacion/202301Expo/zR9.txt \\
      -m 202301 -o sql/mensuales/01_enero/exportacion_subitems_202301.sql

IMPORTANTE:
  - Este script requiere que la tabla exportacion_items ya esté cargada
  - La fecha_oficializacion y mes_archivo se obtienen mediante JOIN con exportacion_items
  - Los sufijos (marca, modelo, etc.) se parsean automáticamente mediante columnas GENERATED
  - Cargar en orden: 1) despachos, 2) items, 3) ventajas, 4) subitems
        """
    )

    parser.add_argument('input_file', type=str, help='Archivo zR9.txt de entrada')
    parser.add_argument('-m', '--mes', dest='mes_archivo', required=True,
                       help='Mes del archivo en formato YYYYMM (ej: 202301)')
    parser.add_argument('-o', '--output', type=str, required=True, help='Archivo SQL de salida')

    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Archivo de entrada no encontrado: {input_path}")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    processor = ExportacionSubitemsProcessor(args.mes_archivo)
    processor.procesar_archivo(input_path, output_path)

    print(f"\nArchivo SQL generado exitosamente: {output_path}")


if __name__ == '__main__':
    main()
