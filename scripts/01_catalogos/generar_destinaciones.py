#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generador de Inserts SQL para Tabla Destinaciones
Procesa el archivo destinaciones_full.csv y genera SQL para PostgreSQL
"""

import csv
import sys
import argparse
import unicodedata
import re
from datetime import datetime


class DestinacionesInsertGenerator:
    def __init__(self):
        self.registros_procesados = 0
        self.registros_validos = 0
        self.registros_con_errores = 0
        self.errores = []
        self.correcciones_realizadas = 0
        self.textos_truncados = 0
        self.duplicados_eliminados = 0
        self.codigos_vistos = set()
        
    def limpiar_texto(self, texto):
        """Limpia y normaliza texto para evitar problemas en PostgreSQL"""
        if not texto or texto.strip() == '':
            return None
            
        texto_original = str(texto)
        
        # Convertir a string si no lo es
        texto = str(texto).strip()
        
        # Eliminar caracteres de control y no imprimibles
        texto = ''.join(char for char in texto if ord(char) >= 32 or char in '\t\n\r')
        
        # Normalizar caracteres UTF-8
        texto = unicodedata.normalize('NFC', texto)
        
        # Correcciones específicas de caracteres malformados
        correcciones = {
            'Ã±': 'ñ',
            'Ã¡': 'á', 
            'Ã©': 'é',
            'Ã­': 'í',
            'Ã³': 'ó',
            'Ãº': 'ú',
            'Ã': 'Á',
            'Ã‰': 'É',
            'Ã': 'Í',
            'Ã"': 'Ó',
            'Ãš': 'Ú',
            'Ã': 'Ñ',
            '??': 'Ñ',
            '•': '-',  # Viñetas por guiones
            '·': '-',  # Puntos medios por guiones
            '–': '-',  # En dash por guión normal
            '—': '-',  # Em dash por guión normal
            ''': "'",  # Comilla simple izquierda
            ''': "'",  # Comilla simple derecha
            '"': '"',  # Comilla doble izquierda
            '"': '"',  # Comilla doble derecha
            '…': '...' # Puntos suspensivos
        }
        
        for malformado, correcto in correcciones.items():
            if malformado in texto:
                texto = texto.replace(malformado, correcto)
                self.correcciones_realizadas += 1
        
        # Eliminar caracteres especiales problemáticos pero mantener acentos, ñ y caracteres básicos
        # Permitir: letras, números, espacios, puntos, comas, guiones, paréntesis, barras
        texto = re.sub(r'[^\w\sÁÉÍÓÚÑáéíóúñüÜ.,;:()\-/°&+\'"]+', '', texto)
        
        # Limpiar espacios múltiples y caracteres repetidos
        texto = re.sub(r'\s+', ' ', texto)
        texto = re.sub(r'\.{3,}', '...', texto)  # Múltiples puntos por "..."
        texto = re.sub(r'-{2,}', '-', texto)     # Múltiples guiones por uno solo
        
        # Limpiar espacios alrededor de puntuación
        texto = re.sub(r'\s*([.,;:])\s*', r'\1 ', texto)
        texto = re.sub(r'\s*([()])\s*', r'\1', texto)
        
        # Quitar espacios al inicio y final
        texto = texto.strip()
        
        # Quitar puntos o comas al final si están solos
        texto = re.sub(r'[.,;]+$', '', texto).strip()
        
        # Registrar si hubo cambios significativos
        if texto != texto_original.strip():
            self.correcciones_realizadas += 1
        
        return texto if texto else None
    
    def limpiar_codigo(self, codigo):
        """Limpia específicamente códigos de destinación"""
        if not codigo:
            return None
            
        codigo = str(codigo).strip().upper()
        
        # Eliminar caracteres no alfanuméricos
        codigo = re.sub(r'[^A-Z0-9]', '', codigo)
        
        return codigo if codigo else None
    
    def validar_codigo(self, codigo):
        """Valida el formato del código de destinación"""
        if not codigo:
            return False, "Código vacío"
            
        codigo = codigo.strip()
        
        # Validar longitud (máximo 10 caracteres según DDL)
        if len(codigo) > 10:
            return False, f"Código muy largo: {len(codigo)} caracteres"
            
        # Validar caracteres permitidos (letras, números)
        if not re.match(r'^[A-Z0-9]+$', codigo):
            return False, f"Código contiene caracteres inválidos: {codigo}"
            
        return True, None
    
    def procesar_registro(self, row):
        """Procesa una fila del CSV y retorna los datos limpios"""
        try:
            # Extraer campos (omitimos IE que no se usa)
            codigo = self.limpiar_codigo(row.get('Código', ''))
            tipo = self.limpiar_texto(row.get('TIPO', ''))
            regimen_arancelario = self.limpiar_texto(row.get('Régimen Arancelario', ''))
            descripcion = self.limpiar_texto(row.get('Descripción de la Destinación', ''))
            aplicacion = self.limpiar_texto(row.get('Aplicación', ''))
            
            # Validaciones
            es_valido, error = self.validar_codigo(codigo)
            if not es_valido:
                raise ValueError(f"Código inválido: {error}")
            
            if not tipo:
                raise ValueError("Tipo es obligatorio")
            
            # Verificar duplicados
            if codigo in self.codigos_vistos:
                self.duplicados_eliminados += 1
                raise ValueError(f"Código duplicado: {codigo} (manteniendo primera ocurrencia)")
            
            self.codigos_vistos.add(codigo)
            
            # Truncar campos si exceden límites
            if descripcion and len(descripcion) > 200:
                descripcion = descripcion[:197] + "..."
                self.textos_truncados += 1
            
            # Retornar datos normalizados
            return {
                'codigo': codigo,
                'tipo': tipo,
                'regimen_arancelario': regimen_arancelario,
                'descripcion': descripcion,
                'aplicacion': aplicacion,
                'valido': True,
                'error': None
            }
            
        except Exception as e:
            return {
                'codigo': row.get('Código', ''),
                'tipo': row.get('TIPO', ''),
                'regimen_arancelario': '',
                'descripcion': '',
                'aplicacion': '',
                'valido': False,
                'error': str(e)
            }
    
    def escapar_sql(self, valor):
        """Escapa valores para SQL evitando inyección SQL"""
        if valor is None:
            return 'NULL'
        
        # Escapar comillas simples
        valor_escapado = str(valor).replace("'", "''")
        return f"'{valor_escapado}'"
    
    def generar_insert_tradicional(self, datos):
        """Genera INSERT tradicional para un registro"""
        return f"""INSERT INTO destinaciones (codigo, tipo, regimen_arancelario, descripcion, aplicacion) 
VALUES ({self.escapar_sql(datos['codigo'])}, {self.escapar_sql(datos['tipo'])}, {self.escapar_sql(datos['regimen_arancelario'])}, {self.escapar_sql(datos['descripcion'])}, {self.escapar_sql(datos['aplicacion'])});"""
    
    def generar_copy_line(self, datos):
        """Genera línea para comando COPY"""
        campos = [
            datos['codigo'] or '',
            datos['tipo'] or '',
            datos['regimen_arancelario'] or '',
            datos['descripcion'] or '',
            datos['aplicacion'] or ''
        ]
        
        # Escapar campos para formato COPY (separado por tabs)
        campos_escapados = []
        for campo in campos:
            if campo == '' or campo is None:
                campos_escapados.append('\\N')  # NULL en formato COPY
            else:
                # Escapar caracteres especiales para COPY
                campo_escapado = str(campo).replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '\\r')
                campos_escapados.append(campo_escapado)
        
        return '\t'.join(campos_escapados)
    
    def procesar_csv(self, archivo_csv, archivo_salida, usar_copy=False, verbose=False):
        """Procesa el archivo CSV y genera el SQL"""
        
        print(f"Procesando: {archivo_csv}")
        print(f"Salida: {archivo_salida}")
        print(f"Método: {'COPY' if usar_copy else 'INSERT'}")
        print("-" * 50)
        
        # Leer y procesar CSV
        registros_validos = []
        
        try:
            with open(archivo_csv, 'r', encoding='utf-8') as f:
                # Detectar delimitador
                muestra = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                delimitador = sniffer.sniff(muestra).delimiter
                
                reader = csv.DictReader(f, delimiter=delimitador)
                
                for i, row in enumerate(reader, 1):
                    self.registros_procesados += 1
                    
                    resultado = self.procesar_registro(row)
                    
                    if resultado['valido']:
                        registros_validos.append(resultado)
                        self.registros_validos += 1
                        
                        if verbose and self.registros_validos % 50 == 0:
                            print(f"Procesados: {self.registros_validos} registros válidos")
                    else:
                        self.registros_con_errores += 1
                        error_msg = f"Línea {i}: {resultado['error']}"
                        self.errores.append(error_msg)
                        
                        if verbose:
                            print(f"ERROR - {error_msg}")
        
        except Exception as e:
            print(f"ERROR leyendo archivo CSV: {e}")
            return False
        
        # Generar archivo SQL
        try:
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                self.escribir_cabecera_sql(f)
                
                if usar_copy:
                    self.escribir_copy_sql(f, registros_validos)
                else:
                    self.escribir_insert_sql(f, registros_validos)
                
                self.escribir_pie_sql(f)
                
        except Exception as e:
            print(f"ERROR escribiendo archivo SQL: {e}")
            return False
        
        self.mostrar_resumen(archivo_salida)
        return True
    
    def escribir_cabecera_sql(self, f):
        """Escribe la cabecera del archivo SQL"""
        f.write(f"""-- ============================================================================
-- INSERTS PARA TABLA DESTINACIONES - GENERADO AUTOMÁTICAMENTE
-- ============================================================================
-- Archivo generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- Total de registros: {self.registros_validos}
-- Herramienta: Generador de Destinaciones PostgreSQL
-- ============================================================================

-- Configuración PostgreSQL
\\set ON_ERROR_STOP on
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- Información previa
SELECT 'Iniciando inserción de destinaciones...' as mensaje;
SELECT COUNT(*) as registros_actuales FROM destinaciones;

-- Limpiar datos existentes (descomente si es necesario)
-- DELETE FROM destinaciones;

-- Iniciar transacción
BEGIN;

-- Configuraciones de rendimiento (compatibles con Docker)
SET synchronous_commit = off;

""")
    
    def escribir_insert_sql(self, f, registros):
        """Escribe comandos INSERT tradicionales"""
        f.write("-- Inserción mediante comandos INSERT individuales\n\n")
        
        for i, registro in enumerate(registros, 1):
            f.write(self.generar_insert_tradicional(registro))
            f.write("\n")
            
            # Commit intermedio cada 1000 registros
            if i % 1000 == 0:
                f.write(f"\n-- Commit intermedio ({i} registros)\nCOMMIT;\nBEGIN;\n\n")
    
    def escribir_copy_sql(self, f, registros):
        """Escribe comando COPY masivo"""
        f.write("""-- Inserción mediante comando COPY (más eficiente)
COPY destinaciones (codigo, tipo, regimen_arancelario, descripcion, aplicacion) FROM STDIN WITH (
    FORMAT text,
    DELIMITER E'\\t',
    NULL '\\N',
    ENCODING 'UTF8'
);
""")
        
        # Datos para COPY
        for registro in registros:
            f.write(self.generar_copy_line(registro))
            f.write("\n")
        
        f.write("\\.\n\n")
    
    def escribir_pie_sql(self, f):
        """Escribe el pie del archivo SQL"""
        f.write(f"""
-- Finalizar transacción
COMMIT;

-- Verificaciones finales
SELECT 'Inserción completada exitosamente' as mensaje;
SELECT COUNT(*) as total_destinaciones FROM destinaciones;

-- Estadísticas por tipo
SELECT 
    tipo,
    COUNT(*) as cantidad,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM destinaciones), 2) as porcentaje
FROM destinaciones 
GROUP BY tipo 
ORDER BY cantidad DESC;

-- Verificar códigos duplicados (no debería haber)
SELECT 
    codigo,
    COUNT(*) as duplicados
FROM destinaciones 
GROUP BY codigo 
HAVING COUNT(*) > 1;

-- ============================================================================
-- INSERCIÓN COMPLETADA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- Total insertado: {self.registros_validos} destinaciones
-- ============================================================================
""")
    
    def mostrar_resumen(self, archivo_salida):
        """Muestra resumen del procesamiento"""
        print("\n" + "=" * 60)
        print("RESUMEN DE PROCESAMIENTO")
        print("=" * 60)
        print(f"Registros procesados:      {self.registros_procesados}")
        print(f"Registros válidos:         {self.registros_validos}")
        print(f"Registros con errores:     {self.registros_con_errores}")
        print(f"Duplicados eliminados:     {self.duplicados_eliminados}")
        print(f"Correcciones de texto:     {self.correcciones_realizadas}")
        print(f"Textos truncados:          {self.textos_truncados}")
        
        if self.errores:
            print(f"\nPrimeros errores ({min(5, len(self.errores))}):")
            for error in self.errores[:5]:
                print(f"  ❌ {error}")
        
        # Información del archivo generado
        try:
            import os
            size = os.path.getsize(archivo_salida)
            size_mb = size / (1024 * 1024)
            print(f"\nArchivo generado:          {archivo_salida}")
            print(f"Tamaño:                    {size_mb:.2f} MB")
        except:
            pass
        
        # Mostrar estadísticas de calidad
        calidad = (self.registros_validos / self.registros_procesados) * 100 if self.registros_procesados > 0 else 0
        print(f"Calidad de datos:          {calidad:.1f}%")
        
        print(f"\n✅ Procesamiento completado exitosamente")


def main():
    parser = argparse.ArgumentParser(
        description="Generador de inserts SQL para tabla destinaciones desde CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python3 generar_destinaciones.py destinaciones_full.csv
  python3 generar_destinaciones.py destinaciones_full.csv --copy
  python3 generar_destinaciones.py destinaciones_full.csv -o destinaciones_custom.sql
  python3 generar_destinaciones.py destinaciones_full.csv --verbose
        """
    )
    
    parser.add_argument('archivo_csv', 
                       help='Archivo CSV con datos de destinaciones')
    
    parser.add_argument('-o', '--output', 
                       help='Archivo SQL de salida (default: destinaciones_postgresql.sql)')
    
    parser.add_argument('--copy', 
                       action='store_true',
                       help='Usar método COPY en lugar de INSERT (más rápido)')
    
    parser.add_argument('--verbose', '-v',
                       action='store_true', 
                       help='Mostrar información detallada del proceso')
    
    args = parser.parse_args()
    
    # Determinar archivo de salida
    if args.output:
        archivo_salida = args.output
    else:
        metodo = "copy" if args.copy else "insert"
        archivo_salida = f"destinaciones_{metodo}_postgresql.sql"
    
    # Verificar archivo de entrada
    import os
    if not os.path.isfile(args.archivo_csv):
        print(f"ERROR: Archivo no encontrado: {args.archivo_csv}")
        sys.exit(1)
    
    # Procesar
    generador = DestinacionesInsertGenerator()
    
    try:
        exito = generador.procesar_csv(
            args.archivo_csv, 
            archivo_salida, 
            usar_copy=args.copy,
            verbose=args.verbose
        )
        
        if exito:
            print(f"\n🎉 Archivo SQL generado: {archivo_salida}")
            print("\nPara ejecutar en PostgreSQL:")
            print(f"  psql -d tu_base_de_datos -f {archivo_salida}")
        else:
            print("\n❌ Error en el procesamiento")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()