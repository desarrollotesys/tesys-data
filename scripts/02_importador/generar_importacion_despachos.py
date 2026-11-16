#!/usr/bin/env python3
"""
Script para generar SQL de importación de despachos desde zR1.txt
Genera comandos COPY seguros para PostgreSQL
Autor: Sistema automatizado
Fecha: 2025-10-21
"""

import sys
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import argparse

class ZR1ImportProcessor:
    """
    Procesador optimizado para archivos zR1.txt (importación despachos)
    """
    
    def __init__(self):
        # Contadores
        self.total_procesados = 0
        self.total_validos = 0
        self.total_errores = 0
        self.errores = []
        
        # Mapeo de campos según la estructura de zR1.txt
        self.field_mapping = {
            0: 'despacho_id',           # "25001DIR3000001G"
            1: 'fecha_oficializacion',  # "07/01/25" 
            2: 'cuit_importador',       # "30504018845"
            3: 'estado_declaracion',    # "SALI"
            4: 'condicion_venta',       # "CFR"
            5: 'fob_divisa',           # "DOL"
            6: 'flete_divisa',         # "DOL" 
            7: 'seguro_divisa',        # "DOL"
            8: 'fob_monto',            # 572521.44
            9: 'flete_monto',          # 7680.00
            10: 'seguro_monto',        # 297.52
            11: 'medio',               # "4"
            12: 'cantidad_bultos',     # 5
            13: 'peso_bruto',          # 31429.760
            14: 'matricula',           # "TRASNPORTE RICO"
            15: 'titulo_transporte'    # ""
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
            
            # Campo obligatorio: cuit_importador
            cuit = self.limpiar_campo_texto(campos[2])
            if not cuit:
                self.errores.append(f"Línea {num_linea}: CUIT importador vacío")
                return None
            registro['cuit_importador'] = cuit
            
            # Campos opcionales de texto
            registro['estado_declaracion'] = self.limpiar_campo_texto(campos[3])
            registro['condicion_venta'] = self.limpiar_campo_texto(campos[4])
            registro['fob_divisa'] = self.limpiar_campo_texto(campos[5])
            registro['flete_divisa'] = self.limpiar_campo_texto(campos[6])
            registro['seguro_divisa'] = self.limpiar_campo_texto(campos[7])
            registro['medio'] = self.limpiar_campo_texto(campos[11])
            registro['matricula'] = self.limpiar_campo_texto(campos[14])
            registro['titulo_transporte'] = self.limpiar_campo_texto(campos[15])
            
            # Campos opcionales numéricos
            registro['fob_monto'] = self.limpiar_campo_numerico(campos[8])
            registro['flete_monto'] = self.limpiar_campo_numerico(campos[9])
            registro['seguro_monto'] = self.limpiar_campo_numerico(campos[10])
            registro['cantidad_bultos'] = self.limpiar_campo_numerico(campos[12])
            registro['peso_bruto'] = self.limpiar_campo_numerico(campos[13])
            
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
            # Orden de campos según tabla importacion_despachos
            campos_ordenados = [
                registro.get('despacho_id', ''),
                registro.get('fecha_oficializacion', ''),
                registro.get('cuit_importador', ''),
                registro.get('estado_declaracion') or '\\N',
                registro.get('condicion_venta') or '\\N',
                registro.get('fob_divisa') or '\\N',
                registro.get('flete_divisa') or '\\N', 
                registro.get('seguro_divisa') or '\\N',
                registro.get('fob_monto') or '\\N',
                registro.get('flete_monto') or '\\N',
                registro.get('seguro_monto') or '\\N',
                registro.get('medio') or '\\N',
                registro.get('cantidad_bultos') or '\\N',
                registro.get('peso_bruto') or '\\N',
                registro.get('matricula') or '\\N',
                registro.get('titulo_transporte') or '\\N'
            ]
            
            # Unir con tabs
            lines.append('\t'.join(str(campo) for campo in campos_ordenados))
        
        return '\n'.join(lines)
    
    def generar_sql_header(self, archivo_entrada: str, total_registros: int) -> str:
        """
        Genera la cabecera del archivo SQL
        """
        return f"""-- =====================================================
-- IMPORTACIÓN DE DESPACHOS - POSTGRESQL COPY
-- =====================================================
-- Archivo fuente: {Path(archivo_entrada).name}
-- Registros válidos: {total_registros:,}
-- Fecha generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- =====================================================

-- Configuración segura para PostgreSQL
\\set ON_ERROR_STOP on
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- Información previa
\\echo 'Iniciando carga de importacion_despachos...'
SELECT 'Estado antes de la carga:' as info;
SELECT COUNT(*) as registros_existentes FROM importacion_despachos;

-- Iniciar transacción
BEGIN;

-- Configuraciones de rendimiento (compatibles con Docker)
SET synchronous_commit = off;

-- Crear tabla temporal (sin columnas generadas)
CREATE TEMP TABLE temp_despachos (LIKE importacion_despachos INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES);

-- Mensaje de inicio
\\echo 'Insertando {total_registros:,} registros de despachos de importación...'

-- COPY a tabla temporal
COPY temp_despachos (
    despacho_id,
    fecha_oficializacion,
    cuit_importador,
    estado_declaracion,
    condicion_venta,
    fob_divisa,
    flete_divisa,
    seguro_divisa,
    fob_monto,
    flete_monto,
    seguro_monto,
    medio,
    cantidad_bultos,
    peso_bruto,
    matricula,
    titulo_transporte
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

-- Insertar desde temp table con manejo de duplicados
INSERT INTO importacion_despachos (
    despacho_id,
    fecha_oficializacion,
    cuit_importador,
    estado_declaracion,
    condicion_venta,
    fob_divisa,
    flete_divisa,
    seguro_divisa,
    fob_monto,
    flete_monto,
    seguro_monto,
    medio,
    cantidad_bultos,
    peso_bruto,
    matricula,
    titulo_transporte
)
SELECT
    despacho_id,
    fecha_oficializacion,
    cuit_importador,
    estado_declaracion,
    condicion_venta,
    fob_divisa,
    flete_divisa,
    seguro_divisa,
    fob_monto,
    flete_monto,
    seguro_monto,
    medio,
    cantidad_bultos,
    peso_bruto,
    matricula,
    titulo_transporte
FROM temp_despachos
ON CONFLICT (despacho_id, fecha_oficializacion) DO UPDATE SET
    cuit_importador = EXCLUDED.cuit_importador,
    estado_declaracion = EXCLUDED.estado_declaracion,
    condicion_venta = EXCLUDED.condicion_venta,
    fob_divisa = EXCLUDED.fob_divisa,
    flete_divisa = EXCLUDED.flete_divisa,
    seguro_divisa = EXCLUDED.seguro_divisa,
    fob_monto = EXCLUDED.fob_monto,
    flete_monto = EXCLUDED.flete_monto,
    seguro_monto = EXCLUDED.seguro_monto,
    medio = EXCLUDED.medio,
    cantidad_bultos = EXCLUDED.cantidad_bultos,
    peso_bruto = EXCLUDED.peso_bruto,
    matricula = EXCLUDED.matricula,
    titulo_transporte = EXCLUDED.titulo_transporte;

-- Mostrar estadísticas
\\echo 'Registros insertados correctamente'

-- Finalizar transacción
COMMIT;

-- Restaurar configuraciones
RESET synchronous_commit;

-- Verificaciones finales
\\echo 'Carga completada. Ejecutando verificaciones...'

-- Conteo total
SELECT 
    'Total registros en importacion_despachos' as verificacion,
    COUNT(*) as cantidad
FROM importacion_despachos;

-- Conteo por año
SELECT 
    'Registros por año' as verificacion,
    anio,
    COUNT(*) as cantidad
FROM importacion_despachos 
GROUP BY anio 
ORDER BY anio DESC;

-- Conteo por aduana (top 10)
SELECT 
    'Top 10 aduanas' as verificacion,
    codigo_aduana,
    COUNT(*) as cantidad
FROM importacion_despachos 
GROUP BY codigo_aduana 
ORDER BY cantidad DESC 
LIMIT 10;

-- Verificar foreign keys problemáticas
\\echo 'Verificando posibles problemas de foreign keys...'

SELECT 'Códigos de aduana no encontrados' as problema, COUNT(*) as cantidad
FROM importacion_despachos d
LEFT JOIN aduanas a ON d.codigo_aduana = a.codigo
WHERE a.codigo IS NULL;

SELECT 'CUITs importadores no encontrados' as problema, COUNT(*) as cantidad  
FROM importacion_despachos d
LEFT JOIN padron p ON d.cuit_importador = p.cuit
WHERE p.cuit IS NULL;

SELECT 'Códigos de destinación no encontrados' as problema, COUNT(*) as cantidad
FROM importacion_despachos d  
LEFT JOIN destinaciones dest ON d.tipo_destinacion = dest.codigo
WHERE dest.codigo IS NULL;

\\echo 'Script ejecutado exitosamente!'

-- =====================================================
-- RESUMEN DEL PROCESAMIENTO:
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
            archivo_salida = f"importacion_despachos_{nombre_base}.sql"
        
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
        description='Genera SQL COPY para importacion_despachos desde zR1.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python3 generar_importacion_despachos.py zR1.txt
  python3 generar_importacion_despachos.py zR1.txt -o importacion_despachos_enero.sql
        """
    )
    
    parser.add_argument('archivo_entrada', 
                       help='Archivo zR1.txt de importación')
    parser.add_argument('-o', '--output',
                       dest='archivo_salida', 
                       help='Archivo SQL de salida (opcional)')
    
    args = parser.parse_args()
    
    try:
        procesador = ZR1ImportProcessor()
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