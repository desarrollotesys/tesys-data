#!/usr/bin/env python3
"""
Script para generar SQL de importacion ventajas desde zR8impo.txt
Genera comandos COPY seguros para PostgreSQL

Archivo fuente: zR8impo.txt o zR8.txt
Tabla destino: importacion_ventajas

Estructura del archivo zR8 (pipe-delimited, campos entre comillas):
0. DESTINACION (despacho_id)
1. ITEM (item_id)
2. VENTAJA (ventaja)

Autor: Sistema automatizado
Fecha: 2025-10-29
"""

import sys
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime

class ImportacionVentajasProcessor:
    """
    Procesador para archivos zR8impo.txt (ventajas de importacion)
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

    def procesar_linea(self, linea: str, numero_linea: int) -> Optional[dict]:
        """
        Procesa una línea del archivo zR8 y retorna dict con campos
        """
        try:
            # Split por pipe
            campos = linea.strip().split('|')

            if len(campos) != 3:
                self.errores.append(f"Línea {numero_linea}: número incorrecto de campos ({len(campos)} != 3)")
                return None

            despacho_id = self.limpiar_campo(campos[0])
            item_id = self.limpiar_campo(campos[1])
            ventaja = self.limpiar_campo(campos[2])

            # Validar campos obligatorios
            if not despacho_id or not item_id or not ventaja:
                self.errores.append(f"Línea {numero_linea}: campos obligatorios vacíos")
                return None

            # Validar longitudes
            if len(despacho_id) > 16:
                self.errores.append(f"Línea {numero_linea}: despacho_id muy largo ({len(despacho_id)})")
                return None

            if len(item_id) > 10:
                self.errores.append(f"Línea {numero_linea}: item_id muy largo ({len(item_id)})")
                return None

            if len(ventaja) > 30:
                self.errores.append(f"Línea {numero_linea}: ventaja muy larga ({len(ventaja)})")
                return None

            return {
                'despacho_id': despacho_id,
                'item_id': item_id,
                'ventaja': ventaja
            }

        except Exception as e:
            self.errores.append(f"Línea {numero_linea}: error procesando - {str(e)}")
            return None

    def generar_sql(self, archivo_entrada: Path, archivo_salida: Path, mes: Optional[str] = None):
        """
        Genera archivo SQL con comandos para cargar ventajas
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
                f.write("-- IMPORTACION VENTAJAS - CARGA VIA STAGING\n")
                f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if mes:
                    f.write(f"-- Periodo: {mes}\n")
                f.write(f"-- Registros: {self.total_validos}\n")
                f.write("-- =====================================================\n\n")

                # Crear tabla staging
                f.write("-- Crear tabla staging temporal\n")
                f.write("DROP TABLE IF EXISTS staging_ventajas CASCADE;\n\n")
                f.write("CREATE TEMPORARY TABLE staging_ventajas (\n")
                f.write("    despacho_id VARCHAR(16),\n")
                f.write("    item_id VARCHAR(10),\n")
                f.write("    ventaja VARCHAR(30)\n")
                f.write(");\n\n")

                # COPY data
                f.write("-- Cargar datos en staging\n")
                f.write("COPY staging_ventajas (despacho_id, item_id, ventaja)\n")
                f.write("FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N');\n")

                for reg in registros_validos:
                    f.write(f"{reg['despacho_id']}\t{reg['item_id']}\t{reg['ventaja']}\n")

                f.write("\\.\n\n")

                # INSERT en tabla final con JOIN
                f.write("-- Insertar en tabla final (con fecha_oficializacion via JOIN)\n")
                f.write("INSERT INTO importacion_ventajas (\n")
                f.write("    despacho_id,\n")
                f.write("    fecha_oficializacion,\n")
                f.write("    item_id,\n")
                f.write("    ventaja\n")
                f.write(")\n")
                f.write("SELECT\n")
                f.write("    v.despacho_id,\n")
                f.write("    i.fecha_oficializacion,\n")
                f.write("    v.item_id,\n")
                f.write("    v.ventaja\n")
                f.write("FROM staging_ventajas v\n")
                f.write("INNER JOIN importacion_items i ON v.despacho_id = i.despacho_id AND v.item_id = i.item_id\n")
                f.write("ON CONFLICT (despacho_id, fecha_oficializacion, item_id, ventaja) DO NOTHING;\n\n")

                # Limpiar
                f.write("-- Limpiar staging\n")
                f.write("DROP TABLE staging_ventajas;\n")

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
        description='Genera SQL para importar ventajas desde zR8impo.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Básico
  python3 generar_importacion_ventajas.py -i zR8.txt -o ventajas.sql

  # Con periodo
  python3 generar_importacion_ventajas.py -i zR8.txt -o ventajas_202501.sql -m 202501

  # Combinar múltiples archivos
  cat zR8_Q1.txt zR8_Q2.txt > zR8_combined.txt
  python3 generar_importacion_ventajas.py -i zR8_combined.txt -o ventajas.sql
        """
    )

    parser.add_argument('-i', '--input', required=True, type=Path,
                        help='Archivo zR8impo.txt de entrada')
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
    processor = ImportacionVentajasProcessor()
    processor.generar_sql(args.input, args.output, args.mes)

if __name__ == '__main__':
    main()
