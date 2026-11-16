#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para generar SQL de inserción del Padrón AFIP
Fuente: Padron-SELE-SAL-CONSTA.p20out1.20251018.tmp

Formato del archivo:
- CUIT: posiciones 1-11 (11 caracteres)
- Razón Social: posiciones 12-43 (32 caracteres aprox)
- Códigos finales: resto (no se usan)

Ejemplo:
20000033481SUCESION DE PERROTTA CAYETANO ACACNINS00
└─CUIT─────┘└─────RAZON_SOCIAL──────────┘└CÓDIGOS┘

Uso:
python3 generar_padron.py archivo_padron.tmp padron_inserts.sql
"""

import argparse
import logging
import sys
import re
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class GeneradorPadron:
    def __init__(self):
        self.total_procesados = 0
        self.total_validos = 0
        self.total_invalidos = 0
        self.errores = []

    def validar_cuit(self, cuit: str) -> bool:
        """Valida formato básico del CUIT (11 dígitos)"""
        return bool(re.match(r'^\d{11}$', cuit))

    def limpiar_razon_social(self, razon_social: str) -> str:
        """Limpia y normaliza la razón social"""
        # Eliminar espacios extras
        razon_social = re.sub(r'\s+', ' ', razon_social.strip())
        
        # Escapar comillas simples para SQL
        razon_social = razon_social.replace("'", "''")
        
        return razon_social

    def procesar_linea(self, linea: str, numero_linea: int) -> tuple:
        """
        Procesa una línea del archivo del padrón
        
        Returns:
            tuple: (cuit, razon_social) si es válida, None si es inválida
        """
        try:
            # Eliminar salto de línea
            linea = linea.rstrip('\n\r')
            
            # Verificar longitud mínima
            if len(linea) < 43:
                self.errores.append(f"Línea {numero_linea}: Longitud insuficiente ({len(linea)} chars)")
                return None
            
            # Extraer CUIT (posiciones 0-10, 11 caracteres)
            cuit = linea[0:11]
            
            # Extraer razón social (posiciones 11-43, 32 caracteres aproximadamente)
            # Pero vamos hasta encontrar los códigos finales o hasta el final útil
            resto = linea[11:]
            
            # La razón social parece terminar antes de códigos como "ACACNINS00"
            # Buscamos patrones típicos de códigos finales (letras repetidas + números)
            match = re.search(r'[A-Z]{6,}\d{2}$', resto)
            if match:
                # Encontramos códigos finales, la razón social va hasta ahí
                razon_social = resto[:match.start()]
            else:
                # No encontramos patrón, tomamos todo el resto
                razon_social = resto
            
            # Validar CUIT
            if not self.validar_cuit(cuit):
                self.errores.append(f"Línea {numero_linea}: CUIT inválido '{cuit}'")
                return None
            
            # Limpiar razón social
            razon_social = self.limpiar_razon_social(razon_social)
            
            # Verificar que no esté vacía
            if not razon_social:
                self.errores.append(f"Línea {numero_linea}: Razón social vacía")
                return None
            
            return (cuit, razon_social)
            
        except Exception as e:
            self.errores.append(f"Línea {numero_linea}: Error inesperado - {str(e)}")
            return None

    def generar_sql(self, archivo_entrada: str, archivo_salida: str):
        """Genera el archivo SQL con los inserts del padrón"""
        logger.info("🚀 Iniciando procesamiento del padrón")
        logger.info(f"📁 Archivo entrada: {archivo_entrada}")
        logger.info(f"📁 Archivo salida: {archivo_salida}")
        
        entrada_path = Path(archivo_entrada)
        if not entrada_path.exists():
            raise FileNotFoundError(f"Archivo de entrada no encontrado: {archivo_entrada}")
        
        # Detectar encoding
        encodings = ['utf-8', 'latin-1', 'cp1252']
        contenido_lineas = None
        
        for encoding in encodings:
            try:
                with open(entrada_path, 'r', encoding=encoding) as f:
                    contenido_lineas = f.readlines()
                logger.info(f"Archivo leído con encoding: {encoding}")
                break
            except UnicodeDecodeError:
                logger.warning(f"Error con {encoding}, intentando siguiente...")
                continue
        
        if contenido_lineas is None:
            raise ValueError("No se pudo leer el archivo con ningún encoding probado")
        
        logger.info(f"Total de líneas leídas: {len(contenido_lineas)}")
        
        # Procesar líneas y generar SQL
        with open(archivo_salida, 'w', encoding='utf-8') as sql_file:
            # Escribir encabezado
            sql_file.write("-- =====================================================\n")
            sql_file.write("-- Inserción de datos del Padrón AFIP\n")
            sql_file.write(f"-- Archivo fuente: {archivo_entrada}\n")
            sql_file.write(f"-- Fecha generación: {datetime.now().strftime('%Y-%m-%d')}\n")
            sql_file.write("-- =====================================================\n\n")
            
            # Limpiar tabla existente
            sql_file.write("-- Limpiar datos existentes del padrón\n")
            sql_file.write("TRUNCATE TABLE padron CASCADE;\n\n")
            
            sql_file.write("-- Insertar datos usando COPY para máximo rendimiento\n")
            sql_file.write("COPY padron (cuit, razon_social) FROM STDIN WITH (FORMAT CSV, DELIMITER '|', QUOTE '\"');\n")
            
            # Procesar cada línea
            for numero_linea, linea in enumerate(contenido_lineas, 1):
                self.total_procesados += 1
                
                resultado = self.procesar_linea(linea, numero_linea)
                
                if resultado:
                    cuit, razon_social = resultado
                    self.total_validos += 1
                    
                    # Escapar para CSV
                    razon_social_csv = razon_social.replace('"', '""')
                    
                    # Escribir línea en formato COPY
                    sql_file.write(f'{cuit}|"{razon_social_csv}"\n')
                else:
                    self.total_invalidos += 1
                
                # Log de progreso cada 10,000 líneas
                if numero_linea % 10000 == 0:
                    logger.info(f"Procesadas {numero_linea} líneas...")
            
            # Terminar COPY
            sql_file.write("\\.\n\n")
            
            # Agregar estadísticas y verificaciones
            sql_file.write("-- Estadísticas de carga\n")
            sql_file.write("DO $$\n")
            sql_file.write("BEGIN\n")
            sql_file.write(f"    RAISE NOTICE 'Registros insertados en padron: %', (SELECT COUNT(*) FROM padron);\n")
            sql_file.write("END $$;\n\n")
            
            sql_file.write("-- Verificar muestra de los primeros 10 registros\n")
            sql_file.write("SELECT cuit, LEFT(razon_social, 50) as razon_social_resumida \n")
            sql_file.write("FROM padron \n")
            sql_file.write("ORDER BY cuit \n")
            sql_file.write("LIMIT 10;\n")
        
        # Mostrar estadísticas finales
        logger.info("============================================================")
        logger.info("ESTADÍSTICAS DE PROCESAMIENTO")
        logger.info("============================================================")
        logger.info(f"Registros procesados: {self.total_procesados:,}")
        logger.info(f"Registros válidos: {self.total_validos:,}")
        logger.info(f"Registros inválidos: {self.total_invalidos:,}")
        logger.info(f"Tasa de éxito: {(self.total_validos/self.total_procesados)*100:.1f}%")
        
        if self.errores:
            logger.warning(f"Total de errores: {len(self.errores)}")
            # Mostrar primeros 10 errores
            for error in self.errores[:10]:
                logger.warning(f"  - {error}")
            if len(self.errores) > 10:
                logger.warning(f"  ... y {len(self.errores) - 10} errores más")
        
        logger.info("============================================================")
        logger.info(f"Archivo SQL generado: {archivo_salida}")
        logger.info("✅ Procesamiento completado exitosamente")
        
        print(f"\n🎯 SIGUIENTE PASO:")
        print(f"Ejecutar el archivo SQL generado:")
        print(f"docker exec -i postgres_tesys psql -U postgres -d comercio_exterior_argentina < {archivo_salida}")

def main():
    parser = argparse.ArgumentParser(
        description='Generar SQL de inserción del Padrón AFIP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 generar_padron.py ../Catalogos/Padron-extracto.txt padron_inserts.sql
  python3 generar_padron.py ../Catalogos/Padron-SELE-SAL-CONSTA.p20out1.20251018.tmp padron_inserts.sql
        """
    )
    
    parser.add_argument('archivo_entrada', 
                       help='Archivo del padrón (.txt o .tmp)')
    parser.add_argument('archivo_salida', 
                       help='Archivo SQL de salida')
    
    args = parser.parse_args()
    
    try:
        generador = GeneradorPadron()
        generador.generar_sql(args.archivo_entrada, args.archivo_salida)
        
    except FileNotFoundError as e:
        logger.error(f"❌ Archivo no encontrado: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
