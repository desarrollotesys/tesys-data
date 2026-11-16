#!/usr/bin/env python3
"""
Script para generar SQL de exportacion items desde zR5.txt
Genera comandos COPY seguros para PostgreSQL

Archivo fuente: zR5.txt (exportación)
Tabla destino: exportacion_items

Estructura del archivo zR5 (pipe-delimited, sin header):
0. DESTINACION (despacho_id)
1. ITEM (item_id)
2. FECHAOFICIALIZACION
3. POSICIONSIM
4. CODPAISORIGEN → mapeado como cod_pais_destino (país destino real de la exportación)
5. CODPAISPROCEDENCIA → mapeado como cod_pais_origen (jurisdicción/aduana argentina, ej: BA, SF, JU)
6. UNIDADMEDIDA (código de unidad)
7. CANTIDADUNIDADES
8. KGSNETOS
9. MONTOFOBDOLAR
10. MONTOFOBDIVISA
11. ESTADOMERCADERIA

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

class ExportacionItemsProcessor:
    """
    Procesador para archivos zR5.txt (items de exportacion)
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

    def convertir_fecha(self, fecha_str: str) -> Optional[str]:
        """
        Convierte fecha de DD/MM/YY a formato PostgreSQL YYYY-MM-DD
        """
        try:
            fecha_str = fecha_str.strip().strip('"')
            if not fecha_str:
                return None

            parts = fecha_str.split('/')
            if len(parts) != 3:
                return None

            dia = int(parts[0])
            mes = int(parts[1])
            anio = int(parts[2])

            # Convertir año de 2 digitos a 4 digitos
            if anio >= 0 and anio <= 30:
                anio += 2000
            elif anio >= 31 and anio <= 99:
                anio += 1900

            if mes < 1 or mes > 12 or dia < 1 or dia > 31:
                return None

            return f"{anio:04d}-{mes:02d}-{dia:02d}"

        except (ValueError, IndexError):
            return None

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
        Procesa un registro del archivo zR5
        """
        try:
            if len(row) < 12:
                self.errores.append(f"Linea {linea_num}: Numero incorrecto de campos ({len(row)} < 12)")
                return None

            # Extraer campos
            despacho_id = self.limpiar_campo(row[0])
            item_id = self.limpiar_campo(row[1])
            fecha_str = row[2]
            posicion_sim = self.limpiar_campo(row[3])
            # Campo 4: CODPAISORIGEN = país destino real | Campo 5: CODPAISPROCEDENCIA = jurisdicción argentina
            cod_pais_destino = self.limpiar_campo(row[4])  # CODPAISORIGEN → país destino real
            cod_pais_origen = self.limpiar_campo(row[5])   # CODPAISPROCEDENCIA → jurisdicción argentina (BA, SF, JU, etc.)
            codigo_unidad = self.limpiar_campo(row[6])
            cantidad_unidades = row[7]
            kgs_netos = row[8]
            monto_fob_dolar = row[9]
            monto_fob_divisa = row[10]
            estado_mercaderia = self.limpiar_campo(row[11])

            # Validaciones obligatorias
            if not despacho_id or len(despacho_id) != 16:
                self.errores.append(f"Linea {linea_num}: despacho_id invalido")
                return None

            if not item_id:
                self.errores.append(f"Linea {linea_num}: item_id faltante")
                return None

            fecha_oficializacion = self.convertir_fecha(fecha_str)
            if not fecha_oficializacion:
                self.errores.append(f"Linea {linea_num}: fecha invalida: {fecha_str}")
                return None

            if not posicion_sim:
                self.errores.append(f"Linea {linea_num}: posicion_sim faltante")
                return None

            if not codigo_unidad:
                self.errores.append(f"Linea {linea_num}: codigo_unidad faltante")
                return None

            # Si estado_mercaderia está vacío o es solo espacios, usar código por defecto
            if not estado_mercaderia or estado_mercaderia.strip() == '':
                estado_mercaderia = '1'  # Código por defecto para exportación

            # Convertir numericos
            cantidad_unidades_val = self.convertir_decimal(cantidad_unidades, 3)
            kgs_netos_val = self.convertir_decimal(kgs_netos, 3)
            monto_fob_dolar_val = self.convertir_decimal(monto_fob_dolar, 2)
            monto_fob_divisa_val = self.convertir_decimal(monto_fob_divisa, 2)

            if not cantidad_unidades_val:
                self.errores.append(f"Linea {linea_num}: cantidad_unidades invalida")
                return None

            if not kgs_netos_val:
                self.errores.append(f"Linea {linea_num}: kgs_netos invalido")
                return None

            if not monto_fob_dolar_val:
                self.errores.append(f"Linea {linea_num}: monto_fob_dolar invalido")
                return None

            return {
                'despacho_id': despacho_id,
                'fecha_oficializacion': fecha_oficializacion,
                'item_id': item_id,
                'posicion_sim': posicion_sim,
                'cod_pais_destino': cod_pais_destino,
                'cod_pais_origen': cod_pais_origen,
                'codigo_unidad': codigo_unidad,
                'cantidad_unidades': cantidad_unidades_val,
                'kgs_netos': kgs_netos_val,
                'monto_fob_dolar': monto_fob_dolar_val,
                'monto_fob_divisa': monto_fob_divisa_val,
                'estado_mercaderia': estado_mercaderia
            }

        except Exception as e:
            self.errores.append(f"Linea {linea_num}: Error: {str(e)}")
            return None

    def formatear_valor_copy(self, valor: Any) -> str:
        """
        Formatea valor para COPY
        """
        if valor is None or valor == '':
            return '\\N'
        return str(valor)

    def procesar_archivo(self, input_file: Path, output_file: Path):
        """
        Procesa archivo zR5 y genera SQL
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
            f.write("-- EXPORTACION ITEMS - CARGA VIA STAGING\n")
            f.write(f"-- Mes archivo: {self.mes_archivo}\n")
            f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Registros: {len(registros)}\n")
            f.write("-- =====================================================\n\n")

            # Crear tabla staging
            f.write("-- Crear tabla staging temporal\n")
            f.write("DROP TABLE IF EXISTS staging_exportacion_items;\n\n")
            f.write("CREATE TEMPORARY TABLE staging_exportacion_items (\n")
            f.write("    despacho_id VARCHAR(16),\n")
            f.write("    fecha_oficializacion DATE,\n")
            f.write("    mes_archivo CHAR(6),\n")
            f.write("    item_id VARCHAR(10),\n")
            f.write("    posicion_sim VARCHAR(20),\n")
            f.write("    cod_pais_destino VARCHAR(10),\n")
            f.write("    cod_pais_origen VARCHAR(10),\n")
            f.write("    codigo_unidad VARCHAR(10),\n")
            f.write("    cantidad_unidades DECIMAL(15,3),\n")
            f.write("    kgs_netos DECIMAL(12,3),\n")
            f.write("    monto_fob_dolar DECIMAL(15,2),\n")
            f.write("    monto_fob_divisa DECIMAL(15,2),\n")
            f.write("    estado_mercaderia VARCHAR(5)\n")
            f.write(");\n\n")

            # Comando COPY a staging
            f.write("-- Cargar datos en staging\n")
            f.write("COPY staging_exportacion_items (\n")
            f.write("    despacho_id,\n")
            f.write("    fecha_oficializacion,\n")
            f.write("    mes_archivo,\n")
            f.write("    item_id,\n")
            f.write("    posicion_sim,\n")
            f.write("    cod_pais_destino,\n")
            f.write("    cod_pais_origen,\n")
            f.write("    codigo_unidad,\n")
            f.write("    cantidad_unidades,\n")
            f.write("    kgs_netos,\n")
            f.write("    monto_fob_dolar,\n")
            f.write("    monto_fob_divisa,\n")
            f.write("    estado_mercaderia\n")
            f.write(") FROM stdin;\n")

            # Datos
            for registro in registros:
                linea = '\t'.join([
                    self.formatear_valor_copy(registro['despacho_id']),
                    self.formatear_valor_copy(registro['fecha_oficializacion']),
                    self.mes_archivo,  # Nuevo campo
                    self.formatear_valor_copy(registro['item_id']),
                    self.formatear_valor_copy(registro['posicion_sim']),
                    self.formatear_valor_copy(registro['cod_pais_destino']),
                    self.formatear_valor_copy(registro['cod_pais_origen']),
                    self.formatear_valor_copy(registro['codigo_unidad']),
                    self.formatear_valor_copy(registro['cantidad_unidades']),
                    self.formatear_valor_copy(registro['kgs_netos']),
                    self.formatear_valor_copy(registro['monto_fob_dolar']),
                    self.formatear_valor_copy(registro['monto_fob_divisa']),
                    self.formatear_valor_copy(registro['estado_mercaderia'])
                ])
                f.write(linea + '\n')

            f.write("\\.\n\n")

            # Auto-insertar unidades faltantes
            f.write("-- Auto-insertar unidades faltantes\n")
            f.write("INSERT INTO unidades (codigo, descripcion, activo)\n")
            f.write("SELECT DISTINCT\n")
            f.write("    s.codigo_unidad,\n")
            f.write("    'Unidad ' || s.codigo_unidad || ' - Por determinar',\n")
            f.write("    TRUE\n")
            f.write("FROM staging_exportacion_items s\n")
            f.write("WHERE s.codigo_unidad IS NOT NULL\n")
            f.write("  AND s.codigo_unidad NOT IN (SELECT codigo FROM unidades)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            # Auto-insertar paises faltantes
            f.write("-- Auto-insertar paises faltantes\n")
            f.write("INSERT INTO paises (codigo, nombre)\n")
            f.write("SELECT DISTINCT codigo, 'Pais ' || codigo || ' - Por determinar'\n")
            f.write("FROM (\n")
            f.write("    SELECT cod_pais_destino as codigo FROM staging_exportacion_items WHERE cod_pais_destino IS NOT NULL\n")
            f.write("    UNION\n")
            f.write("    SELECT cod_pais_origen as codigo FROM staging_exportacion_items WHERE cod_pais_origen IS NOT NULL\n")
            f.write(") codigos\n")
            f.write("WHERE codigo NOT IN (SELECT codigo FROM paises)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            # Auto-insertar estados faltantes
            f.write("-- Auto-insertar estados faltantes\n")
            f.write("INSERT INTO estados (codigo, descripcion)\n")
            f.write("SELECT DISTINCT\n")
            f.write("    s.estado_mercaderia,\n")
            f.write("    'Estado ' || s.estado_mercaderia || ' - Por determinar'\n")
            f.write("FROM staging_exportacion_items s\n")
            f.write("WHERE s.estado_mercaderia IS NOT NULL\n")
            f.write("  AND s.estado_mercaderia NOT IN (SELECT codigo FROM estados)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            # Auto-insertar posiciones faltantes en nomenclador
            f.write("-- Auto-insertar posiciones faltantes en nomenclador\n")
            f.write("INSERT INTO nomenclador (posicion_sim, descripcion, codigo_unidad)\n")
            f.write("SELECT DISTINCT\n")
            f.write("    s.posicion_sim,\n")
            f.write("    'PARTIDA NUEVA - EN PROCESO DE CLASIFICACION',\n")
            f.write("    NULL\n")
            f.write("FROM staging_exportacion_items s\n")
            f.write("WHERE s.posicion_sim NOT IN (SELECT posicion_sim FROM nomenclador)\n")
            f.write("ON CONFLICT (posicion_sim) DO NOTHING;\n\n")

            # Reporte de catalogos agregados
            f.write("-- Reporte de codigos agregados automaticamente\n")
            f.write("DO $$\n")
            f.write("DECLARE\n")
            f.write("    unidades_nuevas TEXT;\n")
            f.write("    paises_nuevos TEXT;\n")
            f.write("    estados_nuevos TEXT;\n")
            f.write("    posiciones_nuevas INTEGER;\n")
            f.write("BEGIN\n")
            f.write("    SELECT string_agg(codigo, ', ' ORDER BY codigo) INTO unidades_nuevas\n")
            f.write("    FROM unidades WHERE descripcion LIKE '%Por determinar';\n")
            f.write("    \n")
            f.write("    SELECT string_agg(codigo, ', ' ORDER BY codigo) INTO paises_nuevos\n")
            f.write("    FROM paises WHERE nombre LIKE '%Por determinar';\n")
            f.write("    \n")
            f.write("    SELECT string_agg(codigo, ', ' ORDER BY codigo) INTO estados_nuevos\n")
            f.write("    FROM estados WHERE descripcion LIKE '%Por determinar';\n")
            f.write("    \n")
            f.write("    SELECT COUNT(*) INTO posiciones_nuevas\n")
            f.write("    FROM nomenclador WHERE descripcion LIKE '%PARTIDA NUEVA%';\n")
            f.write("    \n")
            f.write("    RAISE NOTICE '';\n")
            f.write("    RAISE NOTICE '=========================================';\n")
            f.write("    RAISE NOTICE 'CODIGOS AGREGADOS AUTOMATICAMENTE';\n")
            f.write("    RAISE NOTICE '=========================================';\n")
            f.write("    \n")
            f.write("    IF unidades_nuevas IS NOT NULL THEN\n")
            f.write("        RAISE NOTICE 'Unidades: %', unidades_nuevas;\n")
            f.write("    END IF;\n")
            f.write("    \n")
            f.write("    IF paises_nuevos IS NOT NULL THEN\n")
            f.write("        RAISE NOTICE 'Paises: %', paises_nuevos;\n")
            f.write("    END IF;\n")
            f.write("    \n")
            f.write("    IF estados_nuevos IS NOT NULL THEN\n")
            f.write("        RAISE NOTICE 'Estados: %', estados_nuevos;\n")
            f.write("    END IF;\n")
            f.write("    \n")
            f.write("    IF posiciones_nuevas > 0 THEN\n")
            f.write("        RAISE NOTICE 'Posiciones nomenclador: % nuevas', posiciones_nuevas;\n")
            f.write("    END IF;\n")
            f.write("    \n")
            f.write("    RAISE NOTICE '';\n")
            f.write("    RAISE NOTICE 'Agregar a docs/TODO_codigos_automaticos.md';\n")
            f.write("    RAISE NOTICE 'Consultar documentacion oficial AFIP';\n")
            f.write("    RAISE NOTICE '=========================================';\n")
            f.write("END $$;\n\n")

            # Insertar en tabla final
            f.write("-- Insertar en tabla final\n")
            f.write("INSERT INTO exportacion_items (\n")
            f.write("    despacho_id,\n")
            f.write("    fecha_oficializacion,\n")
            f.write("    mes_archivo,\n")
            f.write("    item_id,\n")
            f.write("    posicion_sim,\n")
            f.write("    cod_pais_destino,\n")
            f.write("    cod_pais_origen,\n")
            f.write("    codigo_unidad,\n")
            f.write("    cantidad_unidades,\n")
            f.write("    kgs_netos,\n")
            f.write("    monto_fob_dolar,\n")
            f.write("    monto_fob_divisa,\n")
            f.write("    estado_mercaderia\n")
            f.write(")\n")
            f.write("SELECT\n")
            f.write("    despacho_id,\n")
            f.write("    fecha_oficializacion,\n")
            f.write("    mes_archivo,\n")
            f.write("    item_id,\n")
            f.write("    posicion_sim,\n")
            f.write("    cod_pais_destino,\n")
            f.write("    cod_pais_origen,\n")
            f.write("    codigo_unidad,\n")
            f.write("    cantidad_unidades,\n")
            f.write("    kgs_netos,\n")
            f.write("    monto_fob_dolar,\n")
            f.write("    monto_fob_divisa,\n")
            f.write("    estado_mercaderia\n")
            f.write("FROM staging_exportacion_items\n")
            f.write("ON CONFLICT (despacho_id, fecha_oficializacion, mes_archivo, item_id) DO NOTHING;\n\n")

            # Limpiar staging
            f.write("-- Limpiar staging\n")
            f.write("DROP TABLE staging_exportacion_items;\n\n")

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
        description='Genera SQL para carga de exportacion_items desde zR5.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python3 generar_exportacion_items.py zR5.txt -m 202301 -o output.sql
  python3 generar_exportacion_items.py data/mensuales/2023/01_enero/raw/exportacion/202301Expo/zR5.txt \\
      -m 202301 -o sql/mensuales/01_enero/exportacion_items_202301.sql

IMPORTANTE:
  Si al ejecutar el SQL hay errores de FK en posicion_sim, significa que
  faltan posiciones en la tabla nomenclador. Insertar las faltantes con
  descripcion temporal antes de reintentar la carga.
        """
    )

    parser.add_argument('input_file', type=str, help='Archivo zR5.txt de entrada')
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

    processor = ExportacionItemsProcessor(args.mes_archivo)
    processor.procesar_archivo(input_path, output_path)

    print(f"\nArchivo SQL generado exitosamente: {output_path}")


if __name__ == '__main__':
    main()
