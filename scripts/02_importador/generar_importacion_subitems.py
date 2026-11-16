#!/usr/bin/env python3
"""
Script para generar SQL de importacion subitems desde zR9impo.txt
Genera comandos COPY seguros para PostgreSQL

Archivo fuente: zR9impo.txt
Tabla destino: importacion_subitems

Estructura del archivo zR9 (pipe-delimited, sin header):
0. DESTINACION (despacho_id)
1. ITEM (item_id)
2. SUBITEM (subitem_id)
3. DETALLE (detalle_completo - sufijos estructurados)
4. CANTIDADUNIDADESSUBITEM
5. FOBDOLSUBITEM

Autor: Sistema automatizado
Fecha: 2025-10-28
"""

import sys
import csv
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal, InvalidOperation

class ImportacionSubitemsProcessor:
    """
    Procesador para archivos zR9impo.txt (subitems de importacion)
    """

    def __init__(self):
        self.total_procesados = 0
        self.total_validos = 0
        self.total_errores = 0
        self.errores = []

    def limpiar_campo(self, valor: str, *, permitir_vacio: bool = False) -> Optional[str]:
        """
        Limpia campo de texto y escapa caracteres especiales para COPY.

        permitir_vacio=True: distingue '' (campo presente pero vacío, ej.
        DETALLE="" en subitems reales con cantidad/FOB != 0) de None (campo
        ausente o malformado). Sin esto, ambos casos colapsaban a None y
        procesar_registro() descartaba la fila entera — BUGFIX 2026-10-01,
        ver docs/... : 43.171 filas de agosto 2026 con DETALLE="" real
        se perdían (ej. 26001IC04160560N/0005/0001, cantidad=1440, fob=1440).
        """
        if valor is None:
            return None
        if valor == '' and not permitir_vacio:
            return None

        valor_limpio = valor.strip().strip('"')
        if valor_limpio == '' and not permitir_vacio:
            return None

        # Eliminar caracteres de control (excepto espacios normales)
        valor_limpio = ''.join(char if char >= ' ' or char == '\t' else ' ' for char in valor_limpio)

        # Escapar backslashes y tabs para formato COPY
        valor_limpio = valor_limpio.replace('\\', '\\\\')
        valor_limpio = valor_limpio.replace('\t', ' ')

        if valor_limpio == '' and not permitir_vacio:
            return None
        return valor_limpio

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
            # permitir_vacio=True: DETALLE="" es un valor real en el zR9
            # (subitem sin sufijos codificados, pero con cantidad/FOB propios).
            # None sigue significando "campo ausente/malformado" y se descarta.
            detalle_completo = self.limpiar_campo(row[3], permitir_vacio=True)
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

            # BUGFIX 2026-10-01: antes se descartaba la fila si detalle_completo
            # era None O ''. DETALLE="" es un valor real (ver nota en
            # limpiar_campo) — solo None (campo verdaderamente ausente/
            # malformado) debe rechazar la fila.
            if detalle_completo is None:
                self.errores.append(f"Linea {linea_num}: detalle_completo faltante")
                return None

            # Convertir numericos (pueden ser NULL)
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
        Formatea valor para COPY.

        allow_empty_string=True: '' se escribe como cadena vacía real (no '\\N').
        Usar solo para detalle_completo, donde '' es un valor legítimo distinto
        de None (ver limpiar_campo/procesar_registro). Los demás campos nunca
        llegan aquí como '' (se descartan antes si lo fueran).
        """
        if valor is None:
            return '\\N'
        if valor == '' and not allow_empty_string:
            return '\\N'
        return str(valor)

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
            f.write("-- IMPORTACION SUBITEMS - CARGA VIA STAGING\n")
            f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Registros: {len(registros)}\n")
            f.write("-- =====================================================\n\n")

            # Crear tabla staging
            f.write("-- Crear tabla staging temporal\n")
            f.write("DROP TABLE IF EXISTS staging_subitems;\n\n")
            f.write("CREATE TEMPORARY TABLE staging_subitems (\n")
            f.write("    despacho_id VARCHAR(16),\n")
            f.write("    item_id VARCHAR(10),\n")
            f.write("    subitem_id VARCHAR(10),\n")
            f.write("    detalle_completo TEXT,\n")
            f.write("    cantidad_unidades_subitem DECIMAL(15,3),\n")
            f.write("    fob_dolar_subitem DECIMAL(15,2)\n")
            f.write(");\n\n")

            # Comando COPY a staging
            f.write("-- Cargar datos en staging\n")
            f.write("COPY staging_subitems (\n")
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
                    self.formatear_valor_copy(registro['detalle_completo'], allow_empty_string=True),
                    self.formatear_valor_copy(registro['cantidad_unidades_subitem']),
                    self.formatear_valor_copy(registro['fob_dolar_subitem'])
                ])
                f.write(linea + '\n')

            f.write("\\.\n\n")

            # Insertar en tabla final con JOIN para obtener fecha_oficializacion
            f.write("-- Insertar en tabla final con JOIN a importacion_items\n")
            f.write("INSERT INTO importacion_subitems (\n")
            f.write("    despacho_id,\n")
            f.write("    item_id,\n")
            f.write("    subitem_id,\n")
            f.write("    fecha_oficializacion,\n")
            f.write("    detalle_completo,\n")
            f.write("    cantidad_unidades_subitem,\n")
            f.write("    fob_dolar_subitem\n")
            f.write(")\n")
            f.write("SELECT\n")
            f.write("    s.despacho_id,\n")
            f.write("    s.item_id,\n")
            f.write("    s.subitem_id,\n")
            f.write("    i.fecha_oficializacion,\n")
            f.write("    s.detalle_completo,\n")
            f.write("    s.cantidad_unidades_subitem,\n")
            f.write("    s.fob_dolar_subitem\n")
            f.write("FROM staging_subitems s\n")
            f.write("INNER JOIN importacion_items i ON s.despacho_id = i.despacho_id AND s.item_id = i.item_id\n")
            # Mismo motivo que en importacion_items: despachos en el borde
            # entre quincenas pueden venir en ambos archivos AFIP.
            f.write("ON CONFLICT (despacho_id, fecha_oficializacion, item_id, subitem_id) DO NOTHING;\n\n")

            # Limpiar staging
            f.write("-- Limpiar staging\n")
            f.write("DROP TABLE staging_subitems;\n\n")

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
        description='Genera SQL para carga de importacion_subitems desde zR9impo.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python3 generar_importacion_subitems.py zR9.txt -o output.sql
  python3 generar_importacion_subitems.py data/mensuales/2025/01_enero/raw/importacion/202501ImpoQ1/zR9.txt \\
      -o sql/mensuales/01_enero/importacion_subitems_202501.sql

IMPORTANTE:
  Este script genera un JOIN con importacion_items para obtener fecha_oficializacion.
  Asegurese de haber cargado importacion_items ANTES de ejecutar el SQL generado.
        """
    )

    parser.add_argument('input_file', type=str, help='Archivo zR9impo.txt de entrada')
    parser.add_argument('-o', '--output', type=str, required=True, help='Archivo SQL de salida')

    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Archivo de entrada no encontrado: {input_path}")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    processor = ImportacionSubitemsProcessor()
    processor.procesar_archivo(input_path, output_path)

    print(f"\nArchivo SQL generado exitosamente: {output_path}")


if __name__ == '__main__':
    main()
