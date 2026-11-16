#!/usr/bin/env python3
"""
Script para generar SQL de importacion obligaciones desde zRAimpo.txt
Genera comandos COPY seguros para PostgreSQL

Archivo fuente: zRAimpo.txt o zRA.txt
Tabla destino: importacion_obligaciones

Estructura del archivo zRA (pipe-delimited, campos entre comillas):
0. DESTINACION (despacho_id)
1. ITEM (item_id)
2. CONCEPTO (concepto)
3. OBLIGACION (obligacion)
4. MONTO (monto)

Autor: Sistema automatizado
Fecha: 2025-10-30
"""

import sys
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime
from decimal import Decimal, InvalidOperation

class ImportacionObligacionesProcessor:
    """
    Procesador para archivos zRAimpo.txt (obligaciones de importacion)
    """

    def __init__(self):
        self.total_procesados = 0
        self.total_validos = 0
        self.total_errores = 0
        self.errores = []

    def limpiar_campo(self, valor: str) -> Optional[str]:
        """
        Limpia campo de texto y escapa caracteres especiales para COPY
        """
        if not valor:
            return None

        # Remover comillas y espacios
        valor_limpio = valor.strip().strip('"')
        if not valor_limpio:
            return None

        # Escapar para formato COPY
        valor_limpio = valor_limpio.replace('\\', '\\\\')
        valor_limpio = valor_limpio.replace('\t', ' ')
        valor_limpio = valor_limpio.replace('\n', ' ')
        valor_limpio = valor_limpio.replace('\r', ' ')

        return valor_limpio if valor_limpio else None

    def convertir_decimal(self, valor: str) -> Optional[Decimal]:
        """
        Convierte string a Decimal de forma segura
        """
        if not valor:
            return None

        valor_limpio = valor.strip().strip('"')
        if not valor_limpio:
            return None

        try:
            return Decimal(valor_limpio)
        except (InvalidOperation, ValueError):
            return None

    def procesar_linea(self, linea: str, numero_linea: int) -> Optional[dict]:
        """
        Procesa una línea del archivo zRA y retorna dict con campos
        """
        try:
            # Split por pipe
            campos = linea.strip().split('|')

            if len(campos) != 5:
                self.errores.append(f"Línea {numero_linea}: número incorrecto de campos ({len(campos)} != 5)")
                return None

            despacho_id = self.limpiar_campo(campos[0])
            item_id = self.limpiar_campo(campos[1])
            concepto = self.limpiar_campo(campos[2])
            obligacion = self.limpiar_campo(campos[3])
            monto = self.convertir_decimal(campos[4])

            # Validar campos obligatorios
            if not despacho_id or not item_id or not concepto or not obligacion:
                self.errores.append(f"Línea {numero_linea}: campos obligatorios vacíos")
                return None

            # Validar longitudes
            if len(despacho_id) > 16:
                self.errores.append(f"Línea {numero_linea}: despacho_id muy largo ({len(despacho_id)})")
                return None

            if len(item_id) > 10:
                self.errores.append(f"Línea {numero_linea}: item_id muy largo ({len(item_id)})")
                return None

            if len(concepto) > 10:
                self.errores.append(f"Línea {numero_linea}: concepto muy largo ({len(concepto)})")
                return None

            if len(obligacion) > 10:
                self.errores.append(f"Línea {numero_linea}: obligacion muy larga ({len(obligacion)})")
                return None

            return {
                'despacho_id': despacho_id,
                'item_id': item_id,
                'concepto': concepto,
                'obligacion': obligacion,
                'monto': monto
            }

        except Exception as e:
            self.errores.append(f"Línea {numero_linea}: error procesando - {str(e)}")
            return None

    def generar_sql(self, archivo_entrada: Path, archivo_salida: Path, mes: Optional[str] = None):
        """
        Genera archivo SQL con comandos para cargar obligaciones
        """
        print(f"Procesando: {archivo_entrada}")
        print(f"Generando: {archivo_salida}")

        # Leer y procesar archivo
        registros_validos = []

        try:
            with open(archivo_entrada, 'r', encoding='utf-8', errors='replace') as f:
                for numero_linea, linea in enumerate(f, 1):
                    self.total_procesados += 1

                    if not linea.strip():
                        continue

                    registro = self.procesar_linea(linea, numero_linea)
                    if registro:
                        registros_validos.append(registro)
                        self.total_validos += 1
                    else:
                        self.total_errores += 1

        except Exception as e:
            print(f"ERROR leyendo archivo: {e}", file=sys.stderr)
            sys.exit(1)

        # Generar SQL
        try:
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                # Header
                f.write("-- =====================================================\n")
                f.write("-- IMPORTACION OBLIGACIONES - CARGA VIA STAGING\n")
                f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if mes:
                    f.write(f"-- Periodo: {mes}\n")
                f.write(f"-- Registros: {self.total_validos}\n")
                f.write("-- =====================================================\n\n")

                # Crear tabla staging
                f.write("-- Crear tabla staging temporal\n")
                f.write("DROP TABLE IF EXISTS staging_obligaciones CASCADE;\n\n")
                f.write("CREATE TEMPORARY TABLE staging_obligaciones (\n")
                f.write("    despacho_id VARCHAR(16),\n")
                f.write("    item_id VARCHAR(10),\n")
                f.write("    concepto VARCHAR(10),\n")
                f.write("    obligacion VARCHAR(10),\n")
                f.write("    monto DECIMAL(18,2)\n")
                f.write(");\n\n")

                # COPY data
                f.write("-- Cargar datos en staging\n")
                f.write("COPY staging_obligaciones (despacho_id, item_id, concepto, obligacion, monto)\n")
                f.write("FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N');\n")

                for reg in registros_validos:
                    monto_str = str(reg['monto']) if reg['monto'] is not None else '\\N'
                    f.write(f"{reg['despacho_id']}\t{reg['item_id']}\t{reg['concepto']}\t{reg['obligacion']}\t{monto_str}\n")

                f.write("\\.\n\n")

                # INSERT en tabla final con JOIN
                f.write("-- Insertar en tabla final (con fecha_oficializacion via JOIN)\n")
                f.write("INSERT INTO importacion_obligaciones (\n")
                f.write("    despacho_id,\n")
                f.write("    fecha_oficializacion,\n")
                f.write("    item_id,\n")
                f.write("    concepto,\n")
                f.write("    obligacion,\n")
                f.write("    monto\n")
                f.write(")\n")
                f.write("SELECT\n")
                f.write("    o.despacho_id,\n")
                f.write("    i.fecha_oficializacion,\n")
                f.write("    o.item_id,\n")
                f.write("    o.concepto,\n")
                f.write("    o.obligacion,\n")
                f.write("    o.monto\n")
                f.write("FROM staging_obligaciones o\n")
                f.write("INNER JOIN importacion_items i ON o.despacho_id = i.despacho_id AND o.item_id = i.item_id\n")
                f.write("ON CONFLICT (despacho_id, fecha_oficializacion, item_id, concepto, obligacion) DO NOTHING;\n\n")

                # Limpiar
                f.write("-- Limpiar staging\n")
                f.write("DROP TABLE staging_obligaciones;\n")

        except Exception as e:
            print(f"ERROR generando SQL: {e}", file=sys.stderr)
            sys.exit(1)

        # Reporte
        print(f"\n{'='*60}")
        print(f"RESUMEN")
        print(f"{'='*60}")
        print(f"Registros procesados: {self.total_procesados:,}")
        print(f"Registros válidos:    {self.total_validos:,}")
        print(f"Registros con error:  {self.total_errores:,}")

        if self.errores and len(self.errores) <= 10:
            print(f"\nErrores encontrados:")
            for error in self.errores[:10]:
                print(f"  - {error}")
            if len(self.errores) > 10:
                print(f"  ... y {len(self.errores) - 10} más")

        print(f"\nSQL generado: {archivo_salida}")
        print(f"{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(
        description='Genera SQL para importar obligaciones desde zRAimpo.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Básico
  python3 generar_importacion_obligaciones.py -i zRA.txt -o obligaciones.sql

  # Con periodo
  python3 generar_importacion_obligaciones.py -i zRA.txt -o obligaciones_202501.sql -m 202501

  # Combinar múltiples archivos
  cat zRA_Q1.txt zRA_Q2.txt > zRA_combined.txt
  python3 generar_importacion_obligaciones.py -i zRA_combined.txt -o obligaciones.sql
        """
    )

    parser.add_argument('-i', '--input', required=True, type=Path,
                        help='Archivo zRAimpo.txt de entrada')
    parser.add_argument('-o', '--output', required=True, type=Path,
                        help='Archivo SQL de salida')
    parser.add_argument('-m', '--mes', type=str,
                        help='Periodo YYYYMM (opcional, para documentación)')

    args = parser.parse_args()

    # Validar archivo entrada
    if not args.input.exists():
        print(f"ERROR: Archivo no encontrado: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Crear directorio salida si no existe
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Procesar
    processor = ImportacionObligacionesProcessor()
    processor.generar_sql(args.input, args.output, args.mes)

if __name__ == '__main__':
    main()
