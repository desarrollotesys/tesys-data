#!/usr/bin/env python3
"""
Script para generar SQL de exportación de despachos desde zR1.txt
Genera comandos COPY seguros para PostgreSQL
Autor: Sistema automatizado
Fecha: 2025-01-10
"""

import sys
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import argparse

class ZR1ExportProcessor:
    """
    Procesador optimizado para archivos zR1.txt (exportación despachos)
    """

    def __init__(self, mes_archivo: str):
        # Validar formato mes_archivo (YYYYMM)
        if not mes_archivo or len(mes_archivo) != 6 or not mes_archivo.isdigit():
            raise ValueError(f"mes_archivo debe ser formato YYYYMM (ej: 202301), recibido: {mes_archivo}")
        self.mes_archivo = mes_archivo

        # Contadores
        self.total_procesados = 0
        self.total_validos = 0
        self.total_errores = 0
        self.errores = []

        # Mapeo de campos según la estructura de zR1.txt exportación
        # Estructura: despacho_id|fecha_oficializacion|fecha_cumplido|fecha_embarque|cuit_exportador|
        #            estado_declaracion|condicion_venta|div_fob|div_flete|div_seguro|
        #            fob_div|flete_div|seguro_div|via_medio_transporte|cantidad_bultos|peso_bultos
        self.field_mapping = {
            0: 'despacho_id',
            1: 'fecha_oficializacion',
            2: 'fecha_cumplido',
            3: 'fecha_embarque',
            4: 'cuit_exportador',
            5: 'estado_declaracion',
            6: 'condicion_venta',
            7: 'fob_divisa',
            8: 'flete_divisa',
            9: 'seguro_divisa',
            10: 'fob_monto',
            11: 'flete_monto',
            12: 'seguro_monto',
            13: 'via_medio_transporte',
            14: 'cantidad_bultos',
            15: 'peso_bultos'
        }

    def validar_despacho_id(self, despacho_id: str) -> bool:
        """
        Valida formato básico de despacho_id
        """
        if not despacho_id or len(despacho_id) != 16:
            return False

        # Validación básica: 16 caracteres alfanuméricos
        # El constraint específico se validará en la BD
        return despacho_id.isalnum()

    def convertir_fecha(self, fecha_str: str) -> Optional[str]:
        """
        Convierte fecha de DD/MM/YY a formato PostgreSQL YYYY-MM-DD
        """
        try:
            # Remover comillas si las tiene
            fecha_str = fecha_str.strip('"').strip()

            if not fecha_str:
                return None

            # Parsear DD/MM/YY
            parts = fecha_str.split('/')
            if len(parts) != 3:
                return None

            dia = int(parts[0])
            mes = int(parts[1])
            anio = int(parts[2])

            # Convertir año de 2 dígitos a 4 dígitos
            if anio >= 0 and anio <= 30:  # 00-30 -> 2000-2030
                anio += 2000
            elif anio >= 31 and anio <= 99:  # 31-99 -> 1931-1999
                anio += 1900

            # Validar rangos
            if mes < 1 or mes > 12 or dia < 1 or dia > 31:
                return None

            return f"{anio:04d}-{mes:02d}-{dia:02d}"

        except (ValueError, IndexError):
            return None

    def limpiar_campo_texto(self, valor: str) -> Optional[str]:
        """
        Limpia y normaliza campos de texto
        """
        if not valor:
            return None

        # Remover comillas
        valor = valor.strip('"').strip()

        if not valor or valor.upper() in ['NULL', 'N/A', '']:
            return None

        # Escapar para PostgreSQL COPY (tab-separated)
        valor = valor.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
        valor = re.sub(r'\s+', ' ', valor).strip()

        return valor if valor else None

    def limpiar_campo_numerico(self, valor: str) -> Optional[str]:
        """
        Limpia y valida campos numéricos
        """
        if not valor:
            return None

        valor = valor.strip('"').strip()

        if not valor or valor.upper() in ['NULL', 'N/A', '']:
            return None

        try:
            # Validar que es un número válido
            float(valor)
            return valor
        except ValueError:
            return None

    def procesar_linea(self, linea: str, num_linea: int) -> Optional[Dict[str, Any]]:
        """
        Procesa una línea del archivo zR1.txt
        """
        try:
            # El archivo usa pipe (|) como delimitador
            campos = linea.strip().split('|')

            if len(campos) < 16:
                self.errores.append(f"Línea {num_linea}: Campos insuficientes ({len(campos)}/16)")
                return None

            # Mapear campos
            registro = {}

            # Campo obligatorio: despacho_id
            despacho_id = self.limpiar_campo_texto(campos[0])
            if not despacho_id or not self.validar_despacho_id(despacho_id):
                self.errores.append(f"Línea {num_linea}: despacho_id inválido: {campos[0]}")
                return None
            registro['despacho_id'] = despacho_id

            # Campo obligatorio: fecha_oficializacion
            fecha = self.convertir_fecha(campos[1])
            if not fecha:
                self.errores.append(f"Línea {num_linea}: fecha inválida: {campos[1]}")
                return None
            registro['fecha_oficializacion'] = fecha

            # Fechas opcionales
            registro['fecha_cumplido'] = self.convertir_fecha(campos[2])
            registro['fecha_embarque'] = self.convertir_fecha(campos[3])

            # Campo obligatorio: cuit_exportador
            cuit = self.limpiar_campo_texto(campos[4])
            if not cuit:
                self.errores.append(f"Línea {num_linea}: CUIT exportador vacío")
                return None
            registro['cuit_exportador'] = cuit

            # Campos opcionales de texto
            registro['estado_declaracion'] = self.limpiar_campo_texto(campos[5])
            registro['condicion_venta'] = self.limpiar_campo_texto(campos[6])
            registro['fob_divisa'] = self.limpiar_campo_texto(campos[7])
            registro['flete_divisa'] = self.limpiar_campo_texto(campos[8])
            registro['seguro_divisa'] = self.limpiar_campo_texto(campos[9])
            registro['via_medio_transporte'] = self.limpiar_campo_texto(campos[13])

            # Campos opcionales numéricos
            registro['fob_monto'] = self.limpiar_campo_numerico(campos[10])
            registro['flete_monto'] = self.limpiar_campo_numerico(campos[11])
            registro['seguro_monto'] = self.limpiar_campo_numerico(campos[12])
            registro['cantidad_bultos'] = self.limpiar_campo_numerico(campos[14])
            registro['peso_bultos'] = self.limpiar_campo_numerico(campos[15])

            return registro

        except Exception as e:
            self.errores.append(f"Línea {num_linea}: Error procesando: {str(e)}")
            return None

    def generar_copy_data(self, registros: list) -> str:
        """
        Genera los datos para el comando COPY en formato tab-separated
        """
        lines = []

        for registro in registros:
            # Orden de campos según tabla exportacion_despachos (con mes_archivo)
            campos_ordenados = [
                registro.get('despacho_id', ''),
                registro.get('fecha_oficializacion', ''),
                self.mes_archivo,  # Nuevo campo
                registro.get('fecha_cumplido') or '\\N',
                registro.get('fecha_embarque') or '\\N',
                registro.get('cuit_exportador', ''),
                registro.get('estado_declaracion') or '\\N',
                registro.get('condicion_venta') or '\\N',
                registro.get('fob_divisa') or '\\N',
                registro.get('flete_divisa') or '\\N',
                registro.get('seguro_divisa') or '\\N',
                registro.get('fob_monto') or '\\N',
                registro.get('flete_monto') or '\\N',
                registro.get('seguro_monto') or '\\N',
                registro.get('via_medio_transporte') or '\\N',
                registro.get('cantidad_bultos') or '\\N',
                registro.get('peso_bultos') or '\\N'
            ]

            # Unir con tabs
            lines.append('\t'.join(str(campo) for campo in campos_ordenados))

        return '\n'.join(lines)

    def generar_sql_header(self, archivo_entrada: str, total_registros: int) -> str:
        """
        Genera la cabecera del archivo SQL
        """
        return f"""-- =====================================================
-- EXPORTACIÓN DE DESPACHOS - POSTGRESQL COPY
-- =====================================================
-- Archivo fuente: {Path(archivo_entrada).name}
-- Mes archivo: {self.mes_archivo}
-- Registros válidos: {total_registros:,}
-- Fecha generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- =====================================================

-- Configuración segura para PostgreSQL
\\set ON_ERROR_STOP on
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- Información previa
\\echo 'Iniciando carga de exportacion_despachos (mes: {self.mes_archivo})...'
SELECT 'Estado antes de la carga:' as info;
SELECT COUNT(*) as registros_existentes FROM exportacion_despachos;
SELECT COUNT(*) as registros_mes_{self.mes_archivo} FROM exportacion_despachos WHERE mes_archivo = '{self.mes_archivo}';

-- Iniciar transacción
BEGIN;

-- Configuraciones de rendimiento (compatibles con Docker)
SET synchronous_commit = off;

-- Crear tabla temporal (sin columnas generadas)
CREATE TEMP TABLE temp_exportacion_despachos (
    despacho_id VARCHAR(16) NOT NULL,
    fecha_oficializacion DATE NOT NULL,
    mes_archivo CHAR(6) NOT NULL,
    fecha_cumplido DATE,
    fecha_embarque DATE,
    cuit_exportador VARCHAR(12) NOT NULL,
    estado_declaracion VARCHAR(10),
    condicion_venta VARCHAR(10),
    fob_divisa VARCHAR(5),
    flete_divisa VARCHAR(5),
    seguro_divisa VARCHAR(5),
    fob_monto DECIMAL(15,2),
    flete_monto DECIMAL(15,2),
    seguro_monto DECIMAL(15,2),
    via_medio_transporte VARCHAR(10),
    cantidad_bultos INTEGER,
    peso_bultos DECIMAL(15,3)
);

-- Mensaje de inicio
\\echo 'Insertando {total_registros:,} registros de despachos de exportación (mes: {self.mes_archivo})...'

-- COPY a tabla temporal
COPY temp_exportacion_despachos (
    despacho_id,
    fecha_oficializacion,
    mes_archivo,
    fecha_cumplido,
    fecha_embarque,
    cuit_exportador,
    estado_declaracion,
    condicion_venta,
    fob_divisa,
    flete_divisa,
    seguro_divisa,
    fob_monto,
    flete_monto,
    seguro_monto,
    via_medio_transporte,
    cantidad_bultos,
    peso_bultos
) FROM STDIN WITH (
    FORMAT text,
    DELIMITER E'\\t',
    NULL '\\N',
    ENCODING 'UTF8'
);
"""

    def generar_sql_footer(self, total_procesados: int, total_validos: int, total_errores: int) -> str:
        """
        Genera el footer del archivo SQL
        """
        return f"""\\.

-- Auto-insertar CUITs exportadores faltantes en padrón
INSERT INTO padron (cuit, razon_social)
SELECT DISTINCT t.cuit_exportador, 'SIN DATOS - PENDIENTE ACTUALIZAR'
FROM temp_exportacion_despachos t
LEFT JOIN padron p ON t.cuit_exportador = p.cuit
WHERE t.cuit_exportador IS NOT NULL AND p.cuit IS NULL
ON CONFLICT (cuit) DO NOTHING;


-- Insertar desde temp table (mes_archivo permite historial, no hay conflictos entre meses)
INSERT INTO exportacion_despachos (
    despacho_id,
    fecha_oficializacion,
    mes_archivo,
    fecha_cumplido,
    fecha_embarque,
    cuit_exportador,
    estado_declaracion,
    condicion_venta,
    fob_divisa,
    flete_divisa,
    seguro_divisa,
    fob_monto,
    flete_monto,
    seguro_monto,
    via_medio_transporte,
    cantidad_bultos,
    peso_bultos
)
SELECT
    despacho_id,
    fecha_oficializacion,
    mes_archivo,
    fecha_cumplido,
    fecha_embarque,
    cuit_exportador,
    estado_declaracion,
    condicion_venta,
    fob_divisa,
    flete_divisa,
    seguro_divisa,
    fob_monto,
    flete_monto,
    seguro_monto,
    via_medio_transporte,
    cantidad_bultos,
    peso_bultos
FROM temp_exportacion_despachos
ON CONFLICT (despacho_id, fecha_oficializacion, mes_archivo) DO NOTHING;

-- Mostrar estadísticas
\\echo 'Registros insertados correctamente'

-- Finalizar transacción
COMMIT;

-- Restaurar configuraciones
RESET synchronous_commit;

-- Verificaciones finales
\\echo 'Carga completada (mes: {self.mes_archivo}). Ejecutando verificaciones...'

-- Conteo total
SELECT
    'Total registros en exportacion_despachos' as verificacion,
    COUNT(*) as cantidad
FROM exportacion_despachos;

-- Conteo por mes_archivo
SELECT
    'Registros por mes_archivo' as verificacion,
    mes_archivo,
    COUNT(*) as cantidad
FROM exportacion_despachos
GROUP BY mes_archivo
ORDER BY mes_archivo DESC;

-- Conteo por año
SELECT
    'Registros por año' as verificacion,
    anio,
    COUNT(*) as cantidad
FROM exportacion_despachos
GROUP BY anio
ORDER BY anio DESC;

-- Verificar foreign keys problemáticas
\\echo 'Verificando posibles problemas de foreign keys...'

SELECT 'Códigos de aduana no encontrados' as problema, COUNT(*) as cantidad
FROM exportacion_despachos d
LEFT JOIN aduanas a ON d.codigo_aduana = a.codigo
WHERE a.codigo IS NULL;

SELECT 'CUITs exportadores no encontrados' as problema, COUNT(*) as cantidad
FROM exportacion_despachos d
LEFT JOIN padron p ON d.cuit_exportador = p.cuit
WHERE p.cuit IS NULL;

SELECT 'Códigos de destinación no encontrados' as problema, COUNT(*) as cantidad
FROM exportacion_despachos d
LEFT JOIN destinaciones dest ON d.tipo_destinacion = dest.codigo
WHERE dest.codigo IS NULL;

\\echo 'Script ejecutado exitosamente!'

-- =====================================================
-- RESUMEN DEL PROCESAMIENTO:
-- Mes archivo: {self.mes_archivo}
-- Líneas procesadas: {total_procesados:,}
-- Registros válidos: {total_validos:,}
-- Registros con errores: {total_errores:,}
-- Tasa de éxito: {(total_validos/total_procesados*100) if total_procesados > 0 else 0:.1f}%
-- =====================================================
"""

    def procesar_archivo(self, archivo_entrada: str, archivo_salida: str = None) -> str:
        """
        Procesa el archivo zR1.txt completo y genera el SQL
        """
        # Configurar archivo de salida
        if archivo_salida is None:
            nombre_base = Path(archivo_entrada).stem
            archivo_salida = f"exportacion_despachos_{nombre_base}.sql"

        print(f"Procesando: {archivo_entrada}")
        print(f"Generando: {archivo_salida}")
        print("-" * 60)

        registros_validos = []

        # Helper para procesar un stream ya abierto y devolver registros
        def _procesar_stream(stream):
            nonlocal registros_validos
            for num_linea, linea in enumerate(stream, 1):
                self.total_procesados += 1

                # Saltar líneas vacías
                if not linea.strip():
                    continue

                registro = self.procesar_linea(linea, num_linea)
                if registro:
                    registros_validos.append(registro)
                    self.total_validos += 1
                else:
                    self.total_errores += 1

                # Mostrar progreso
                if self.total_procesados % 5000 == 0:
                    print(f"Procesadas: {self.total_procesados:,} líneas, "
                          f"válidas: {self.total_validos:,}, "
                          f"errores: {self.total_errores}")

        # Procesar archivo línea por línea: intentar UTF-8 y si falla reintentar con latin-1
        try:
            try:
                with open(archivo_entrada, 'r', encoding='utf-8') as f:
                    _procesar_stream(f)
                used_encoding = 'utf-8'
            except UnicodeDecodeError:
                # Reiniciar contadores y errores antes de reintentar con otro encoding
                print(f"\n⚠️  Advertencia: fallo de decodificación UTF-8 en '{archivo_entrada}', reintentando con 'latin-1'...")
                self.total_procesados = 0
                self.total_validos = 0
                self.total_errores = 0
                self.errores = []
                registros_validos = []

                with open(archivo_entrada, 'r', encoding='latin-1') as f:
                    _procesar_stream(f)
                used_encoding = 'latin-1'

        except FileNotFoundError:
            raise FileNotFoundError(f"Archivo no encontrado: {archivo_entrada}")
        except Exception as e:
            raise Exception(f"Error leyendo archivo: {str(e)}")

        if not registros_validos:
            raise ValueError("No se encontraron registros válidos para procesar")

        # Generar archivo SQL
        try:
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                # Escribir cabecera
                f.write(self.generar_sql_header(archivo_entrada, len(registros_validos)))

                # Escribir datos
                f.write(self.generar_copy_data(registros_validos))
                f.write('\n')

                # Escribir footer
                f.write(self.generar_sql_footer(
                    self.total_procesados,
                    self.total_validos,
                    self.total_errores
                ))

        except Exception as e:
            raise Exception(f"Error escribiendo archivo SQL: {str(e)}")

        return archivo_salida

    def mostrar_resumen(self):
        """
        Muestra resumen del procesamiento
        """
        print(f"\n{'='*60}")
        print("RESUMEN DEL PROCESAMIENTO")
        print(f"{'='*60}")
        print(f"Total procesado:      {self.total_procesados:,}")
        print(f"Registros válidos:    {self.total_validos:,}")
        print(f"Registros con error:  {self.total_errores:,}")

        if self.total_procesados > 0:
            tasa_exito = (self.total_validos / self.total_procesados * 100)
            print(f"Tasa de éxito:        {tasa_exito:.1f}%")

        # Mostrar primeros errores
        if self.errores:
            print(f"\nPRIMEROS ERRORES (máx. 10):")
            for error in self.errores[:10]:
                print(f"  ❌ {error}")
            if len(self.errores) > 10:
                print(f"  ... y {len(self.errores) - 10} errores más")

def main():
    parser = argparse.ArgumentParser(
        description='Genera SQL COPY para exportacion_despachos desde zR1.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python3 generar_exportacion_despachos.py zR1.txt -m 202301
  python3 generar_exportacion_despachos.py zR1.txt -m 202301 -o exportacion_despachos_202301.sql
        """
    )

    parser.add_argument('archivo_entrada',
                       help='Archivo zR1.txt de exportación')
    parser.add_argument('-m', '--mes',
                       dest='mes_archivo',
                       required=True,
                       help='Mes del archivo en formato YYYYMM (ej: 202301)')
    parser.add_argument('-o', '--output',
                       dest='archivo_salida',
                       help='Archivo SQL de salida (opcional)')

    args = parser.parse_args()

    try:
        procesador = ZR1ExportProcessor(args.mes_archivo)
        archivo_salida = procesador.procesar_archivo(args.archivo_entrada, args.archivo_salida)

        procesador.mostrar_resumen()

        print(f"\n✅ Archivo SQL generado: {archivo_salida}")
        print(f"📊 {procesador.total_validos:,} registros listos para cargar")
        print(f"\n📋 Para ejecutar en PostgreSQL:")
        print(f"   psql -d comercio_exterior_argentina -f {archivo_salida}")

        return 0

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
