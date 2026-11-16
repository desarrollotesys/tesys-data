#!/usr/bin/env python3
"""
Script mejorado para generar inserts SQL para PostgreSQL
Tabla: proveedores_destinatarios
Fuente: archivos ProvMes{MMYY}.txt procesados

Características:
- Optimizado para PostgreSQL
- Validaciones robustas de datos
- Manejo de errores transaccionales
- Limpieza automática de caracteres problemáticos
- Inserción masiva con COPY (opcional)
- Detección y corrección de duplicados
- Manejo de caracteres especiales UTF-8

Uso:
    python3 generar_inserts_proveedores_mejorado.py archivo_entrada.txt periodo [opciones]
"""

import sys
import re
import argparse
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

class PostgreSQLInsertsGenerator:
    """
    Generador de inserts optimizado para PostgreSQL
    """
    
    def __init__(self, periodo: str, usar_copy: bool = False, limpiar_duplicados: bool = True):
        self.periodo = periodo
        self.usar_copy = usar_copy
        self.limpiar_duplicados = limpiar_duplicados
        
        # Contadores
        self.procesados = 0
        self.validos = 0
        self.duplicados = 0
        self.corregidos = 0
        
        # Errores y warnings
        self.errores: List[str] = []
        self.warnings: List[str] = []
        
        # Set para detectar duplicados
        self.despachos_vistos = set()
        
        # Configurar logging
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)
    
    def validar_despacho_id(self, despacho_id: str) -> bool:
        """
        Valida formato de despacho_id según schema actualizado
        Formato: ^[0-9]{2}[0-9]{3}[A-Z0-9]{4}[0-9]{6}[A-Z]$
        Ejemplos: 25001IC04000106C, 25049ECA1000046D
        """
        if not despacho_id or len(despacho_id) != 16:
            return False
            
        patron = r'^[0-9]{2}[0-9]{3}[A-Z0-9]{4}[0-9]{6}[A-Z]$'
        return bool(re.match(patron, despacho_id.upper()))
    
    def validar_periodo(self, periodo: str) -> bool:
        """
        Valida formato de período: YYYYMM
        """
        if not periodo or len(periodo) != 6:
            return False
            
        try:
            año = int(periodo[:4])
            mes = int(periodo[4:6])
            
            # Validaciones de rango
            if año < 2000 or año > 2100:
                return False
            if mes < 1 or mes > 12:
                return False
                
            return True
        except ValueError:
            return False
    
    def limpiar_texto(self, texto: str) -> str:
        """
        Limpia y normaliza texto para PostgreSQL
        - Normaliza caracteres Unicode
        - Corrige caracteres malformados comunes
        - Remueve caracteres de control
        - Normaliza espacios
        """
        if not texto:
            return texto
            
        # Normalizar Unicode (NFD -> NFC)
        texto = unicodedata.normalize('NFC', texto)
        
        # Correcciones específicas de caracteres malformados
        correcciones = {
            '??': 'Ñ',
            'Ã±': 'ñ',
            'Ã¡': 'á',
            'Ã©': 'é',
            'Ã­': 'í',
            'Ã³': 'ó',
            'Ãº': 'ú',
            'Ã': 'Á',
            'Ã‰': 'É',
            'ÃÃ': 'Í',
            'Ã"': 'Ó',
            'Ãš': 'Ú',
            'Ã§': 'ç',
            'Ã‡': 'Ç',
            # Patrones comunes en datos de AFIP
            'IMPORTA??O': 'IMPORTAÇÃO',
            'EXPORTA??O': 'EXPORTAÇÃO',  
            'COMPA?Y': 'COMPANY',
            'IND?STRIA': 'INDÚSTRIA',
            'SOLU??ES': 'SOLUÇÕES',
            'CONSTRU??O': 'CONSTRUÇÃO',
            'IRRIGA??O': 'IRRIGAÇÃO',
            'SERVI?OS': 'SERVIÇOS',
            'A?O': 'AÇO'
        }
        
        texto_original = texto
        for malformado, correcto in correcciones.items():
            if malformado in texto:
                texto = texto.replace(malformado, correcto)
                if texto != texto_original:
                    self.corregidos += 1
        
        # Remover caracteres de control (excepto espacios y saltos de línea)
        texto = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', texto)
        
        # Normalizar espacios múltiples
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def escapar_sql_postgres(self, texto: Optional[str]) -> str:
        """
        Escapa texto para PostgreSQL usando formato estándar SQL
        """
        if texto is None:
            return 'NULL'
            
        # Escapar comillas simples duplicándolas
        texto_escapado = str(texto).replace("'", "''")
        return f"'{texto_escapado}'"
    
    def detectar_duplicados(self, despacho_id: str) -> bool:
        """
        Detecta si un despacho_id ya fue procesado
        """
        if despacho_id in self.despachos_vistos:
            self.duplicados += 1
            return True
        
        self.despachos_vistos.add(despacho_id)
        return False
    
    def procesar_linea(self, linea: str, num_linea: int) -> Optional[Dict[str, str]]:
        """
        Procesa una línea del archivo ProvMes
        Formato esperado: despacho_id,razon_social
        """
        linea = linea.strip()
        if not linea or linea.startswith('#'):
            return None
        
        # Separar por la primera coma solamente
        try:
            despacho_id, razon_social = linea.split(',', 1)
        except ValueError:
            self.errores.append(f"Línea {num_linea}: Formato inválido (falta coma) - {linea[:50]}...")
            return None
        
        # Limpiar campos
        despacho_id = despacho_id.strip().upper()
        razon_social = self.limpiar_texto(razon_social.strip())
        
        # Validar despacho_id
        if not self.validar_despacho_id(despacho_id):
            self.errores.append(f"Línea {num_linea}: Formato de despacho_id inválido - {despacho_id}")
            return None
        
        # Validar razón social
        if not razon_social:
            self.errores.append(f"Línea {num_linea}: Razón social vacía - {despacho_id}")
            return None
        
        if len(razon_social) > 200:
            self.warnings.append(f"Línea {num_linea}: Razón social truncada (>200 chars) - {despacho_id}")
            razon_social = razon_social[:200].strip()
        
        # Verificar duplicados
        if self.limpiar_duplicados and self.detectar_duplicados(despacho_id):
            self.warnings.append(f"Línea {num_linea}: Despacho duplicado ignorado - {despacho_id}")
            return None
        
        return {
            'despacho_id': despacho_id,
            'razon_social': razon_social
        }
    
    def generar_insert_sql(self, registro: Dict[str, str]) -> str:
        """
        Genera INSERT SQL estándar para un registro
        """
        return (f"INSERT INTO proveedores_destinatarios (despacho_id, razon_social, periodo) "
                f"VALUES ({self.escapar_sql_postgres(registro['despacho_id'])}, "
                f"{self.escapar_sql_postgres(registro['razon_social'])}, "
                f"{self.escapar_sql_postgres(self.periodo)});")
    
    def generar_copy_sql(self, registros: List[Dict[str, str]]) -> str:
        """
        Genera comando COPY para inserción masiva (más eficiente)
        """
        copy_data = []
        for registro in registros:
            # Formato COPY: tab-separated, escapando tabs y newlines
            despacho_id = registro['despacho_id'].replace('\t', '\\t').replace('\n', '\\n')
            razon_social = registro['razon_social'].replace('\t', '\\t').replace('\n', '\\n').replace('\\', '\\\\')
            periodo = self.periodo
            
            copy_data.append(f"{despacho_id}\t{razon_social}\t{periodo}")
        
        copy_command = """COPY proveedores_destinatarios (despacho_id, razon_social, periodo) FROM STDIN;"""
        copy_command += "\n" + "\n".join(copy_data) + "\n\\.\n"
        
        return copy_command
    
    def escribir_cabecera_sql(self, f, archivo_entrada: str, total_registros: int):
        """
        Escribe la cabecera del archivo SQL
        """
        f.write(f"""-- =====================================================
-- Inserts para proveedores_destinatarios (PostgreSQL)
-- =====================================================
-- Archivo fuente: {Path(archivo_entrada).name}
-- Período: {self.periodo}
-- Registros válidos: {total_registros:,}
-- Fecha generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- Método: {'COPY' if self.usar_copy else 'INSERT'}
-- =====================================================

-- Configuración para PostgreSQL
\\set ON_ERROR_STOP on
SET client_encoding = 'UTF8';

-- Eliminar registros existentes del período para evitar duplicados
DELETE FROM proveedores_destinatarios WHERE periodo = {self.escapar_sql_postgres(self.periodo)};

-- Mensaje de inicio
\\echo 'Iniciando inserción de registros para el período {self.periodo}...'

-- INICIO DE TRANSACCIÓN
BEGIN;

-- Configuraciones de rendimiento para grandes volúmenes
SET synchronous_commit = off;
SET wal_buffers = '16MB';
SET checkpoint_completion_target = 0.9;

""")
    
    def escribir_footer_sql(self, f):
        """
        Escribe el footer del archivo SQL
        """
        f.write(f"""

-- FIN DE TRANSACCIÓN
COMMIT;

-- Restaurar configuraciones
RESET synchronous_commit;
RESET wal_buffers;
RESET checkpoint_completion_target;

-- Mensaje de finalización
\\echo 'Inserción completada. Verificando resultados...'

-- Verificación de resultados
SELECT 
    COUNT(*) as total_insertados,
    periodo,
    MIN(fecha_registro) as primera_fecha,
    MAX(fecha_registro) as ultima_fecha
FROM proveedores_destinatarios 
WHERE periodo = {self.escapar_sql_postgres(self.periodo)}
GROUP BY periodo;

-- Verificación adicional de integridad
SELECT 
    'Total de registros únicos por despacho_id' as verificacion,
    COUNT(DISTINCT despacho_id) as registros_unicos
FROM proveedores_destinatarios 
WHERE periodo = {self.escapar_sql_postgres(self.periodo)}
UNION ALL
SELECT 
    'Total de registros (incluyendo duplicados)' as verificacion,
    COUNT(*) as registros_totales
FROM proveedores_destinatarios 
WHERE periodo = {self.escapar_sql_postgres(self.periodo)};

\\echo 'Script ejecutado exitosamente!'

-- =====================================================
-- Resumen del procesamiento:
-- Total procesado: {self.procesados:,}
-- Registros válidos: {self.validos:,}
-- Duplicados removidos: {self.duplicados:,}
-- Correcciones aplicadas: {self.corregidos:,}
-- Errores: {len(self.errores):,}
-- Warnings: {len(self.warnings):,}
-- =====================================================
""")
    
    def procesar_archivo(self, archivo_entrada: str, archivo_salida: Optional[str] = None) -> str:
        """
        Procesa el archivo completo y genera el SQL
        """
        # Validar período
        if not self.validar_periodo(self.periodo):
            raise ValueError(f"Formato de período inválido: {self.periodo}. Usar formato YYYYMM")
        
        # Configurar archivo de salida
        if archivo_salida is None:
            metodo = "copy" if self.usar_copy else "insert"
            archivo_salida = f"proveedores_{self.periodo}_{metodo}_postgresql.sql"
        
        self.logger.info(f"Procesando: {archivo_entrada}")
        self.logger.info(f"Período: {self.periodo}")
        self.logger.info(f"Salida: {archivo_salida}")
        self.logger.info(f"Método: {'COPY' if self.usar_copy else 'INSERT'}")
        self.logger.info(f"Duplicados: {'Limpiar' if self.limpiar_duplicados else 'Mantener'}")
        print("-" * 60)
        
        registros_validos = []
        
        # Procesar archivo de entrada
        try:
            with open(archivo_entrada, 'r', encoding='utf-8') as f:
                for num_linea, linea in enumerate(f, 1):
                    self.procesados += 1
                    
                    registro = self.procesar_linea(linea, num_linea)
                    if registro:
                        registros_validos.append(registro)
                        self.validos += 1
                    
                    # Mostrar progreso
                    if self.procesados % 5000 == 0:
                        self.logger.info(f"Procesadas: {self.procesados:,} líneas, "
                                       f"válidas: {self.validos:,}, "
                                       f"errores: {len(self.errores)}")
        
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
                self.escribir_cabecera_sql(f, archivo_entrada, len(registros_validos))
                
                # Escribir datos
                if self.usar_copy:
                    # Método COPY (más eficiente para grandes volúmenes)
                    f.write("-- Inserción masiva usando COPY\n")
                    f.write(self.generar_copy_sql(registros_validos))
                else:
                    # Método INSERT tradicional
                    f.write("-- Inserción usando INSERT statements\n")
                    for i, registro in enumerate(registros_validos, 1):
                        f.write(self.generar_insert_sql(registro) + "\n")
                        
                        # Commits intermedios cada 1000 registros para evitar transacciones muy largas
                        if i % 1000 == 0 and i < len(registros_validos):
                            f.write(f"\n-- Commit intermedio: {i:,} registros procesados\n")
                
                # Escribir footer
                self.escribir_footer_sql(f)
                
        except Exception as e:
            raise Exception(f"Error escribiendo archivo de salida: {str(e)}")
        
        return archivo_salida
    
    def mostrar_resumen(self):
        """
        Muestra resumen detallado del procesamiento
        """
        print(f"\n{'='*60}")
        print("RESUMEN DEL PROCESAMIENTO")
        print(f"{'='*60}")
        print(f"Total procesado:       {self.procesados:,}")
        print(f"Registros válidos:     {self.validos:,}")
        print(f"Duplicados removidos:  {self.duplicados:,}")
        print(f"Correcciones UTF-8:    {self.corregidos:,}")
        print(f"Errores:              {len(self.errores):,}")
        print(f"Warnings:             {len(self.warnings):,}")
        
        if self.procesados > 0:
            tasa_exito = (self.validos / self.procesados * 100)
            print(f"Tasa de éxito:        {tasa_exito:.1f}%")
        
        # Mostrar primeros errores si los hay
        if self.errores:
            print(f"\nPRIMEROS ERRORES:")
            for error in self.errores[:10]:
                print(f"  ❌ {error}")
            if len(self.errores) > 10:
                print(f"  ... y {len(self.errores) - 10} errores más")
        
        # Mostrar primeros warnings si los hay  
        if self.warnings:
            print(f"\nPRIMEROS WARNINGS:")
            for warning in self.warnings[:5]:
                print(f"  ⚠️  {warning}")
            if len(self.warnings) > 5:
                print(f"  ... y {len(self.warnings) - 5} warnings más")

def main():
    parser = argparse.ArgumentParser(
        description='Genera inserts SQL optimizados para PostgreSQL desde archivos ProvMes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Método INSERT estándar
  python3 generar_inserts_proveedores_mejorado.py ProvMes0125-clean.txt 202501
  
  # Método COPY (más rápido para grandes volúmenes)
  python3 generar_inserts_proveedores_mejorado.py ProvMes0125-clean.txt 202501 --copy
  
  # Mantener duplicados
  python3 generar_inserts_proveedores_mejorado.py ProvMes0125-clean.txt 202501 --no-clean-duplicates
  
  # Archivo personalizado
  python3 generar_inserts_proveedores_mejorado.py ProvMes0125-clean.txt 202501 -o proveedores_enero.sql
        """
    )
    
    parser.add_argument('archivo_entrada', 
                       help='Archivo ProvMes procesado (formato CSV: despacho_id,razon_social)')
    parser.add_argument('periodo', 
                       help='Período en formato YYYYMM (ej: 202501)')
    parser.add_argument('-o', '--output', 
                       dest='archivo_salida',
                       help='Archivo SQL de salida (opcional)')
    parser.add_argument('--copy', 
                       action='store_true',
                       help='Usar método COPY en lugar de INSERT (más rápido)')
    parser.add_argument('--no-clean-duplicates', 
                       action='store_true',
                       help='No limpiar registros duplicados')
    parser.add_argument('--verbose', '-v', 
                       action='store_true',
                       help='Mostrar información detallada durante el procesamiento')
    
    args = parser.parse_args()
    
    # Configurar nivel de logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Crear generador y procesar
        generador = PostgreSQLInsertsGenerator(
            periodo=args.periodo,
            usar_copy=args.copy,
            limpiar_duplicados=not args.no_clean_duplicates
        )
        
        archivo_salida = generador.procesar_archivo(args.archivo_entrada, args.archivo_salida)
        
        # Mostrar resumen
        generador.mostrar_resumen()
        
        print(f"\n✅ Archivo generado exitosamente: {archivo_salida}")
        print(f"📊 {generador.validos:,} registros listos para insertar")
        
        # Mostrar instrucciones de uso
        print(f"\n📋 Para ejecutar en PostgreSQL:")
        print(f"   psql -d tu_base_de_datos -f {archivo_salida}")
        
        if generador.errores:
            print(f"\n⚠️  Se encontraron {len(generador.errores)} errores durante el procesamiento")
            print("   Revisa los detalles arriba y considera limpiar el archivo fuente")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())