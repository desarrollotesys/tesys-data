#!/usr/bin/env python3
"""
Script para generar SQL de importacion auxiliar desde ImpoAux{MMYY}.txt
Genera comandos COPY seguros para PostgreSQL

Archivo fuente: ImpoAux{MMYY}.txt
Tabla destino: importacion_auxiliar (via staging temporal)

Estructura del archivo ImpoAux (TSV con header):
- Declaracion (despacho_id)
- Cuit Despachante
- Canal (R/V/N)
- Razon Social (proveedor)
- Sumaria (manifiesto)
- Doc. Transporte
- Cuit del Transportista

NOTA IMPORTANTE: fecha_oficializacion NO esta en este archivo.
Se debe obtener via JOIN con importacion_despachos durante la carga.

Autor: Sistema automatizado
Fecha: 2025-10-28
"""

import sys
import csv
import re
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

class ImpoAuxProcessor:
    """
    Procesador para archivos ImpoAux{MMYY}.txt (informacion auxiliar de importacion)
    """

    def __init__(self):
        # Contadores
        self.total_procesados = 0
        self.total_validos = 0
        self.total_errores = 0
        self.errores = []

        # Mapeo de campos desde el archivo TSV
        self.field_names = [
            'declaracion',           # despacho_id
            'cuit_despachante',
            'canal',
            'razon_social',          # razon_social_proveedor
            'sumaria',               # manifiesto
            'doc_transporte',        # documento_transporte
            'cuit_transportista'
        ]

    def validar_despacho_id(self, despacho_id: str) -> bool:
        """
        Valida formato basico de despacho_id (16 caracteres alfanumericos)
        """
        if not despacho_id or len(despacho_id) != 16:
            return False
        return despacho_id.isalnum()

    def validar_cuit(self, cuit: str) -> bool:
        """
        Valida formato basico de CUIT (11 digitos)
        """
        if not cuit:
            return True  # CUIT puede ser NULL

        cuit_limpio = cuit.strip().replace('-', '')
        return cuit_limpio.isdigit() and len(cuit_limpio) == 11

    def validar_canal(self, canal: str) -> bool:
        """
        Valida que el canal sea R (Rojo), V (Verde), N (Naranja) o X
        """
        if not canal:
            return True  # Canal puede ser NULL
        return canal.upper() in ['R', 'V', 'N', 'X']

    def limpiar_campo_texto(self, valor: str) -> Optional[str]:
        """
        Limpia y normaliza campos de texto
        Elimina saltos de linea y espacios extras
        """
        if not valor or valor.strip() == '' or valor.strip() == '-':
            return None

        # Eliminar saltos de linea y normalizar espacios
        # .split() sin argumentos divide por cualquier whitespace (espacios, tabs, newlines)
        valor_limpio = ' '.join(valor.split())

        # Escapar caracteres especiales para COPY
        valor_limpio = valor_limpio.replace('\\', '\\\\')

        return valor_limpio if valor_limpio else None

    def procesar_registro(self, row: List[str], linea_num: int) -> Optional[Dict[str, Any]]:
        """
        Procesa un registro del archivo ImpoAux
        """
        try:
            # Verificar que tengamos todos los campos
            if len(row) < 7:
                self.errores.append(f"Linea {linea_num}: Numero incorrecto de campos ({len(row)} < 7)")
                return None

            # Extraer campos
            despacho_id = row[0].strip().strip('"')
            cuit_despachante = row[1].strip().strip('"')
            canal = row[2].strip().strip('"')
            razon_social = row[3].strip().strip('"')
            manifiesto = row[4].strip().strip('"')
            documento_transporte = row[5].strip().strip('"')
            cuit_transportista = row[6].strip().strip('"')

            # Validaciones
            if not self.validar_despacho_id(despacho_id):
                self.errores.append(f"Linea {linea_num}: despacho_id invalido: {despacho_id}")
                return None

            if not self.validar_canal(canal):
                self.errores.append(f"Linea {linea_num}: canal invalido: {canal}")
                return None

            # Limpiar campos de texto
            cuit_despachante_clean = self.limpiar_campo_texto(cuit_despachante)
            canal_clean = canal.upper() if canal else None
            razon_social_clean = self.limpiar_campo_texto(razon_social)
            manifiesto_clean = self.limpiar_campo_texto(manifiesto)
            documento_transporte_clean = self.limpiar_campo_texto(documento_transporte)
            cuit_transportista_clean = self.limpiar_campo_texto(cuit_transportista)

            # Validar CUIT despachante (este si debe ser CUIT valido)
            if cuit_despachante_clean and not self.validar_cuit(cuit_despachante_clean):
                self.errores.append(f"Linea {linea_num}: CUIT despachante invalido: {cuit_despachante_clean}")
                return None

            # NOTA: cuit_transportista NO se valida porque puede contener
            # otros identificadores (manifiestos, codigos internacionales, etc.)

            return {
                'despacho_id': despacho_id,
                'cuit_despachante': cuit_despachante_clean,
                'canal': canal_clean,
                'razon_social_proveedor': razon_social_clean,
                'manifiesto': manifiesto_clean,
                'documento_transporte': documento_transporte_clean,
                'cuit_transportista': cuit_transportista_clean
            }

        except Exception as e:
            self.errores.append(f"Linea {linea_num}: Error procesando registro: {str(e)}")
            return None

    def formatear_valor_copy(self, valor: Any) -> str:
        """
        Formatea un valor para el comando COPY de PostgreSQL
        """
        if valor is None or valor == '':
            return '\\N'  # NULL en formato COPY
        return str(valor)

    def procesar_archivo(self, input_file: Path, output_file: Path):
        """
        Procesa el archivo ImpoAux y genera SQL
        Maneja campos con saltos de linea dentro de comillas
        """
        print(f"Procesando archivo: {input_file}")
        print(f"Salida SQL: {output_file}")

        registros_validos = []

        # Leer archivo completo para manejar campos multilinea
        # Usar csv.reader que maneja correctamente campos entre comillas con saltos de linea
        encoding = 'utf-8'
        try:
            with open(input_file, 'r', encoding=encoding) as f:
                f.read(1024)  # Test encoding
        except UnicodeDecodeError:
            encoding = 'latin-1'
            print(f"Advertencia: UTF-8 fallo, usando {encoding}")

        with open(input_file, 'r', encoding=encoding, errors='replace') as f:
            # Usar csv.reader con delimiter tab
            reader = csv.reader(f, delimiter='\t')

            # Leer header
            header = next(reader)
            print(f"Header detectado: {header}")

            linea_num = 2  # Empezar en 2 porque linea 1 es header
            for row in reader:
                self.total_procesados += 1

                registro = self.procesar_registro(row, linea_num)
                if registro:
                    registros_validos.append(registro)
                    self.total_validos += 1
                else:
                    self.total_errores += 1

                # Mostrar progreso cada 10000 registros
                if self.total_procesados % 10000 == 0:
                    print(f"Procesados: {self.total_procesados} registros...")

                linea_num += 1

        # Generar SQL
        print(f"\nGenerando SQL...")
        self.generar_sql(registros_validos, output_file)

        # Mostrar resumen
        self.mostrar_resumen()

    def decodificar_linea(self, linea_bytes: bytes) -> str:
        """
        Intenta decodificar una linea con multiples encodings
        Primero UTF-8, luego Latin-1, finalmente con reemplazo de errores
        """
        for encoding in ['utf-8', 'latin-1']:
            try:
                return linea_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue

        # Si todo falla, usar UTF-8 con reemplazo de caracteres invalidos
        return linea_bytes.decode('utf-8', errors='replace')

    def generar_sql(self, registros: List[Dict[str, Any]], output_file: Path):
        """
        Genera archivo SQL con comandos COPY
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            # Header del archivo SQL
            f.write("-- =====================================================\n")
            f.write("-- IMPORTACION AUXILIAR - CARGA VIA STAGING\n")
            f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Registros: {len(registros)}\n")
            f.write("-- =====================================================\n\n")

            # Crear tabla temporal staging
            f.write("-- Crear tabla staging temporal\n")
            f.write("DROP TABLE IF EXISTS staging_impoaux;\n\n")
            f.write("CREATE TEMPORARY TABLE staging_impoaux (\n")
            f.write("    despacho_id VARCHAR(16) NOT NULL,\n")
            f.write("    cuit_despachante VARCHAR(20),\n")
            f.write("    canal VARCHAR(1),\n")
            f.write("    razon_social_proveedor VARCHAR(200),\n")
            f.write("    manifiesto VARCHAR(20),\n")
            f.write("    documento_transporte VARCHAR(50),\n")
            f.write("    cuit_transportista VARCHAR(20)\n")
            f.write(");\n\n")

            # Comando COPY
            f.write("-- Cargar datos en staging\n")
            f.write("COPY staging_impoaux (\n")
            f.write("    despacho_id,\n")
            f.write("    cuit_despachante,\n")
            f.write("    canal,\n")
            f.write("    razon_social_proveedor,\n")
            f.write("    manifiesto,\n")
            f.write("    documento_transporte,\n")
            f.write("    cuit_transportista\n")
            f.write(") FROM stdin;\n")

            # Datos
            for registro in registros:
                linea = '\t'.join([
                    self.formatear_valor_copy(registro['despacho_id']),
                    self.formatear_valor_copy(registro['cuit_despachante']),
                    self.formatear_valor_copy(registro['canal']),
                    self.formatear_valor_copy(registro['razon_social_proveedor']),
                    self.formatear_valor_copy(registro['manifiesto']),
                    self.formatear_valor_copy(registro['documento_transporte']),
                    self.formatear_valor_copy(registro['cuit_transportista'])
                ])
                f.write(linea + '\n')

            f.write("\\.\n\n")

            # INSERT final con JOIN para obtener fecha_oficializacion
            f.write("-- Insertar en tabla final con fecha_oficializacion desde importacion_despachos\n")
            f.write("INSERT INTO importacion_auxiliar (\n")
            f.write("    despacho_id,\n")
            f.write("    fecha_oficializacion,\n")
            f.write("    cuit_despachante,\n")
            f.write("    canal,\n")
            f.write("    razon_social_proveedor,\n")
            f.write("    manifiesto,\n")
            f.write("    documento_transporte,\n")
            f.write("    cuit_transportista\n")
            f.write(")\n")
            f.write("SELECT\n")
            f.write("    s.despacho_id,\n")
            f.write("    d.fecha_oficializacion,\n")
            f.write("    s.cuit_despachante,\n")
            f.write("    s.canal,\n")
            f.write("    s.razon_social_proveedor,\n")
            f.write("    s.manifiesto,\n")
            f.write("    s.documento_transporte,\n")
            f.write("    s.cuit_transportista\n")
            f.write("FROM staging_impoaux s\n")
            f.write("INNER JOIN importacion_despachos d ON s.despacho_id = d.despacho_id;\n\n")

            # Limpiar staging
            f.write("-- Limpiar staging\n")
            f.write("DROP TABLE staging_impoaux;\n\n")

            # Footer
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
        description='Genera SQL para carga de importacion_auxiliar desde ImpoAux{MMYY}.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python3 generar_importacion_auxiliar.py ImpoAux0125.txt -o output.sql
  python3 generar_importacion_auxiliar.py data/mensuales/2025/01_enero/raw/ImpoAux0125.txt \\
      -o sql/mensuales/01_enero/importacion_auxiliar_202501.sql

IMPORTANTE:
  Este script genera una tabla staging temporal y realiza un JOIN con
  importacion_despachos para obtener la fecha_oficializacion, que NO
  esta presente en el archivo ImpoAux.

  Asegurese de haber cargado importacion_despachos ANTES de ejecutar
  el SQL generado por este script.
        """
    )

    parser.add_argument(
        'input_file',
        type=str,
        help='Archivo ImpoAux{MMYY}.txt de entrada'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        required=True,
        help='Archivo SQL de salida'
    )

    args = parser.parse_args()

    # Validar archivos
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Archivo de entrada no encontrado: {input_path}")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Procesar
    processor = ImpoAuxProcessor()
    processor.procesar_archivo(input_path, output_path)

    print(f"\nArchivo SQL generado exitosamente: {output_path}")


if __name__ == '__main__':
    main()
