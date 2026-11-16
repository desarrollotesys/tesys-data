#!/usr/bin/env python3
"""
Script para generar SQL de inserción del nomenclador AFIP
Archivo: nomenclador_23102025.txt → tabla nomenclador

Formato del archivo (pipe-delimited):
Posición 1-15: Posición SIM (ej: 0101.01.01.001A)
Posición 17-??: Descripción 
Posición ??-??: Código de unidad (con formato "01", "02", etc.)

Modos de ejecución:
1. --analizar: Genera nomenclador-fixes.csv con palabras problemáticas
2. --generar: Usa nomenclador-fixes.csv para generar SQL corregido

Genera: nomenclador_23102025.sql con comandos COPY seguros
"""

import sys
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Set
import re
import csv
import argparse

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NomencladorProcessor:
    def __init__(self, input_file: str, output_file: str, modo: str = 'generar', fixes_file: str = 'nomenclador-fixes.csv'):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.fixes_file = Path(fixes_file)
        self.modo = modo
        self.registros_procesados = 0
        self.registros_validos = 0
        self.errores = []
        self.registros_invalidos_muestra = []
        self.palabras_problematicas = set()  # Para el modo análisis
        self.correcciones = {}  # Para el modo generación
        
        # Cargar correcciones si estamos en modo generación
        if self.modo == 'generar':
            self.cargar_correcciones()
        # Cargar correcciones si estamos en modo generación
        if self.modo == 'generar':
            self.cargar_correcciones()
    
    def cargar_correcciones(self):
        """Carga las correcciones desde el archivo CSV"""
        if not self.fixes_file.exists():
            logger.error(f"Archivo de correcciones no encontrado: {self.fixes_file}")
            logger.error("Ejecuta primero el modo --analizar para generar el archivo de correcciones")
            sys.exit(1)
        
        try:
            with open(self.fixes_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for linea_num, row in enumerate(reader, 1):
                    if len(row) >= 2:
                        palabra_problema = row[0].strip()
                        palabra_corregida = row[1].strip()
                        
                        if palabra_problema and palabra_corregida:
                            self.correcciones[palabra_problema] = palabra_corregida
                        else:
                            logger.warning(f"Línea {linea_num} del archivo de correcciones está incompleta: {row}")
                    else:
                        logger.warning(f"Línea {linea_num} del archivo de correcciones tiene formato incorrecto: {row}")
            
            logger.info(f"Cargadas {len(self.correcciones)} correcciones desde {self.fixes_file}")
            
        except Exception as e:
            logger.error(f"Error cargando correcciones: {e}")
            sys.exit(1)
    
    def validar_correcciones_completas(self, texto: str) -> List[str]:
        """Valida que todas las palabras con ? tengan corrección"""
        palabras_sin_corregir = []
        
        # Buscar todas las palabras que contienen ?
        palabras_con_interrogacion = re.findall(r'\b\w*\?\w*\b', texto)
        
        for palabra in palabras_con_interrogacion:
            if palabra not in self.correcciones:
                palabras_sin_corregir.append(palabra)
        
        return palabras_sin_corregir
    
    def extraer_palabras_problematicas(self, texto: str):
        """Extrae palabras que contienen ? para el modo análisis"""
        # Buscar todas las palabras que contienen ?
        palabras_con_interrogacion = re.findall(r'\b\w*\?\w*\b', texto)
        
        for palabra in palabras_con_interrogacion:
            # Filtrar casos que no son problemáticos
            if self.es_palabra_problematica_valida(palabra):
                self.palabras_problematicas.add(palabra)
    
    def es_palabra_problematica_valida(self, palabra: str) -> bool:
        """Determina si una palabra con ? es realmente problemática"""
        
        # Ignorar palabras muy cortas (menos de 3 caracteres)
        if len(palabra) < 3:
            return False
        
        # Ignorar temperaturas (número + ?C o ?F)
        if re.match(r'^\d+\?[CF]$', palabra):
            return False
        
        # Ignorar casos donde ? está al final seguido de una sola letra
        if re.match(r'^.+\?[A-Z]$', palabra) and len(palabra) <= 4:
            return False
        
        # Ignorar fragmentos que empiezan o terminan solo con ?
        if re.match(r'^\?[a-zA-Z]{1,2}$', palabra) or re.match(r'^[a-zA-Z]{1,2}\?$', palabra):
            return False
        
        # Ignorar números con ?
        if re.match(r'^\d+\?\d*$', palabra):
            return False
        
        # Aceptar palabras que tienen ? en el medio y son de al menos 4 caracteres
        if '?' in palabra and len(palabra) >= 4:
            # Verificar que tenga al menos 2 letras antes o después del ?
            if re.search(r'[a-zA-Z]{2,}', palabra):
                return True
        
        return False
    
    def generar_archivo_fixes(self) -> bool:
        """Genera archivo CSV con palabras problemáticas (modo análisis)"""
        try:
            logger.info(f"MODO ANÁLISIS: Procesando archivo para identificar palabras problemáticas")
            logger.info(f"Archivo fuente: {self.input_file}")
            
            # Leer archivo con múltiples intentos de encoding
            try:
                with open(self.input_file, 'r', encoding='utf-8') as f:
                    lineas = f.readlines()
            except UnicodeDecodeError:
                logger.warning("Error con UTF-8, intentando con Latin-1...")
                try:
                    with open(self.input_file, 'r', encoding='latin-1') as f:
                        lineas = f.readlines()
                except UnicodeDecodeError:
                    logger.warning("Error con Latin-1, intentando con cp1252...")
                    with open(self.input_file, 'r', encoding='cp1252', errors='replace') as f:
                        lineas = f.readlines()
            
            logger.info(f"Total de líneas leídas: {len(lineas)}")
            
            # Procesar líneas para extraer palabras problemáticas
            for num_linea, linea in enumerate(lineas, 1):
                if num_linea % 5000 == 0:
                    logger.info(f"Analizadas {num_linea} líneas...")
                
                # Extraer descripción de la línea
                campos = linea.split('@')
                if len(campos) >= 10:
                    descripcion_parts = []
                    for i in range(10, len(campos)):
                        if campos[i].strip():
                            descripcion_parts.append(campos[i].strip())
                    descripcion = ' '.join(descripcion_parts)
                    
                    if descripcion:
                        self.extraer_palabras_problematicas(descripcion)
            
            # Generar archivo CSV con palabras problemáticas
            with open(self.fixes_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['palabra_problema', 'palabra_corregida'])  # Header
                
                for palabra in sorted(self.palabras_problematicas):
                    writer.writerow([palabra, ''])  # Dejar vacío para corrección manual
            
            logger.info(f"✅ Archivo de correcciones generado: {self.fixes_file}")
            logger.info(f"📝 Palabras problemáticas encontradas: {len(self.palabras_problematicas)}")
            logger.info(f"🔧 SIGUIENTE PASO: Edita manualmente el archivo {self.fixes_file}")
            logger.info(f"   - Completa la columna 'palabra_corregida' para cada palabra")
            logger.info(f"   - Luego ejecuta: python {sys.argv[0]} --generar <archivo_entrada> <archivo_salida>")
            
            return True
            
        except Exception as e:
            logger.error(f"Error en modo análisis: {e}")
            return False
        """Analiza y reporta caracteres especiales en un texto"""
        especiales = []
        for char in texto:
            if ord(char) < 32 or ord(char) > 126:
                especiales.append(f"'{char}'(U+{ord(char):04X})")
        return " ".join(especiales) if especiales else "Sin caracteres especiales"
    
    def validar_posicion_sim(self, posicion: str) -> bool:
        """Valida formato de posición SIM: 9999.99.99.999X"""
        patron = r'^\d{4}\.\d{2}\.\d{2}\.\d{3}[A-Z]$'
        return bool(re.match(patron, posicion))
    
    def limpiar_descripcion(self, descripcion: str) -> str:
        """Limpia descripción aplicando correcciones y convirtiendo a MAYÚSCULAS"""
        # Eliminar saltos de línea, tabs y caracteres de control
        descripcion = re.sub(r'[\r\n\t\x00-\x1f\x7f-\x9f]', ' ', descripcion)
        
        if self.modo == 'generar':
            # Validar que todas las palabras con ? tengan corrección
            palabras_sin_corregir = self.validar_correcciones_completas(descripcion)
            if palabras_sin_corregir:
                raise ValueError(f"Palabras sin corrección encontradas: {', '.join(palabras_sin_corregir)}")
            
            # Aplicar correcciones desde el archivo CSV
            for palabra_problema, palabra_corregida in self.correcciones.items():
                if palabra_problema in descripcion:
                    descripcion = descripcion.replace(palabra_problema, palabra_corregida)
                    logger.debug(f"Aplicada corrección: '{palabra_problema}' → '{palabra_corregida}'")
        
        # Convertir a MAYÚSCULAS
        descripcion = descripcion.upper()
        
        # Eliminar guiones al inicio de la descripción (-- o -)
        if descripcion.startswith('--'):
            descripcion = descripcion[2:].strip()
        elif descripcion.startswith('-'):
            descripcion = descripcion[1:].strip()
        
        # Limpiar caracteres problemáticos restantes
        descripcion = re.sub(r'[^\w\s\-\.\,\(\)\[\]\+\:\;\&\%\$\#\@\!/\\ÁÉÍÓÚÑÜÇ]', '', descripcion)
        
        # Limpiar espacios duplicados
        descripcion = re.sub(r'\s+', ' ', descripcion)
        
        # Escapar comillas para SQL
        descripcion = descripcion.replace("'", "''")
        
        return descripcion.strip()
    
    def analizar_caracteres_especiales(self, texto: str) -> str:
        """Analiza y reporta caracteres especiales en un texto"""
        especiales = []
        for char in texto:
            if ord(char) < 32 or ord(char) > 126:
                especiales.append(f"'{char}'(U+{ord(char):04X})")
        return " ".join(especiales) if especiales else "Sin caracteres especiales"
    
    def detectar_nivel(self, posicion_raw: str) -> Optional[Tuple[str, str]]:
        """
        Detecta el nivel jerárquico de una posición AFIP y devuelve (posicion_normalizada, nivel).
        Niveles reconocidos:
          sim      → 8450.11.00.111L  (SIM completa, letra al final)
          ncm_8    → 8450.11.00        (8 dígitos en notación con puntos)
          partida  → 8450.11 / 8450.1  (4+2 dígitos)
          capitulo → 84.50             (2+2 dígitos)
        """
        p = posicion_raw.strip()

        # SIM completa: 4.2.2.3L
        m = re.match(r'^(\d{4}\.\d{2}\.\d{2}\.\d{3}[A-Z])$', p)
        if m:
            return m.group(1), 'sim'

        # NCM 8 dígitos: 8450.11.00
        m = re.match(r'^(\d{4}\.\d{2}\.\d{2})$', p)
        if m:
            return m.group(1), 'ncm_8'

        # Partida (6 dígitos con punto): 8450.11 o 8450.1
        m = re.match(r'^(\d{4}\.\d{1,2})$', p)
        if m:
            return m.group(1), 'partida'

        # Capítulo: 84.50
        m = re.match(r'^(\d{2}\.\d{2})$', p)
        if m:
            return m.group(1), 'capitulo'

        return None

    def parsear_linea(self, linea: str) -> Optional[Tuple[str, str, str, str]]:
        """Parsea una línea del nomenclador y extrae (posición, descripción, código_unidad, nivel)"""
        try:
            linea = linea.rstrip('\n\r')

            if len(linea) < 20:
                return None

            campos = linea.split('@')

            if len(campos) < 10:
                return None

            posicion_sim_raw = campos[1].strip() if len(campos) > 1 else ""
            codigo_unidad = campos[8].strip() if len(campos) > 8 else ""
            descripcion_parts = []
            for i in range(10, len(campos)):
                if campos[i].strip():
                    descripcion_parts.append(campos[i].strip())
            descripcion = ' '.join(descripcion_parts)

            resultado_nivel = self.detectar_nivel(posicion_sim_raw)
            if not resultado_nivel:
                error_msg = f"Posición no reconocida: {posicion_sim_raw}"
                self.errores.append(error_msg)
                if len(self.registros_invalidos_muestra) < 20:
                    chars_especiales = self.analizar_caracteres_especiales(linea)
                    self.registros_invalidos_muestra.append({
                        'linea': linea[:200],
                        'error': error_msg,
                        'caracteres_especiales': chars_especiales,
                        'longitud': len(linea),
                        'posicion_sim_raw': posicion_sim_raw,
                        'campos_count': len(campos)
                    })
                return None

            posicion_sim, nivel = resultado_nivel

            if not descripcion:
                self.errores.append(f"Descripción vacía para posición: {posicion_sim}")
                return None

            # código_unidad solo obligatorio para SIM completa
            if nivel == 'sim' and not re.match(r'^\d{2}$', codigo_unidad):
                self.errores.append(f"Código unidad inválido '{codigo_unidad}' para posición: {posicion_sim}")
                return None

            try:
                descripcion_limpia = self.limpiar_descripcion(descripcion)
            except ValueError as e:
                self.errores.append(f"Error en correcciones para {posicion_sim}: {str(e)}")
                return None

            return posicion_sim, descripcion_limpia, codigo_unidad if re.match(r'^\d{2}$', codigo_unidad) else '', nivel

        except Exception as e:
            error_msg = f"Error parseando línea: {str(e)[:100]}"
            self.errores.append(error_msg)
            if len(self.registros_invalidos_muestra) < 20:
                chars_especiales = self.analizar_caracteres_especiales(linea)
                self.registros_invalidos_muestra.append({
                    'linea': linea[:200],
                    'error': error_msg,
                    'caracteres_especiales': chars_especiales,
                    'longitud': len(linea)
                })
            return None
    
    def procesar(self) -> bool:
        """Método principal que ejecuta según el modo seleccionado"""
        if self.modo == 'analizar':
            return self.generar_archivo_fixes()
        elif self.modo == 'generar':
            return self.generar_sql()
        else:
            logger.error(f"Modo desconocido: {self.modo}")
            return False
    
    def generar_sql(self) -> bool:
        """Genera archivo SQL con comandos COPY"""
        try:
            logger.info(f"Procesando archivo: {self.input_file}")
            logger.info(f"Generando SQL: {self.output_file}")
            
            # Leer y procesar archivo con múltiples intentos de encoding
            try:
                with open(self.input_file, 'r', encoding='utf-8') as f:
                    lineas = f.readlines()
            except UnicodeDecodeError:
                logger.warning("Error con UTF-8, intentando con Latin-1...")
                try:
                    with open(self.input_file, 'r', encoding='latin-1') as f:
                        lineas = f.readlines()
                except UnicodeDecodeError:
                    logger.warning("Error con Latin-1, intentando con cp1252...")
                    with open(self.input_file, 'r', encoding='cp1252', errors='replace') as f:
                        lineas = f.readlines()
            
            logger.info(f"Total de líneas leídas: {len(lineas)}")
            
            # Procesar líneas y generar datos
            datos_validos = []
            posiciones_vistas = set()

            for num_linea, linea in enumerate(lineas, 1):
                self.registros_procesados += 1

                if num_linea % 5000 == 0:
                    logger.info(f"Procesadas {num_linea} líneas...")

                resultado = self.parsear_linea(linea)
                if resultado:
                    posicion_sim, descripcion, codigo_unidad, nivel = resultado
                    if posicion_sim not in posiciones_vistas:
                        posiciones_vistas.add(posicion_sim)
                        datos_validos.append((posicion_sim, descripcion, codigo_unidad, nivel))
                        self.registros_validos += 1
            
            # Generar archivo SQL
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(f"""-- =====================================================
-- Inserción de datos del nomenclador AFIP
-- Archivo fuente: {self.input_file.name}
-- Fecha generación: 2025-10-23
-- Registros válidos: {len(datos_validos):,}
-- =====================================================

-- Verificar que los códigos de unidades estén normalizados
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM unidades WHERE codigo IN ('01', '02', '05', '07', '08')
    ) THEN
        RAISE EXCEPTION 'Error: Códigos de unidades no normalizados. Ejecutar: SELECT normalizar_codigos_unidades();';
    END IF;
    RAISE NOTICE 'Códigos de unidades verificados correctamente';
END $$;

-- Limpiar datos existentes del nomenclador
TRUNCATE TABLE nomenclador CASCADE;

-- Insertar datos usando COPY para máximo rendimiento
COPY nomenclador (posicion_sim, descripcion, codigo_unidad, nivel) FROM STDIN WITH (FORMAT CSV, DELIMITER '|', QUOTE '"');
""")
                
                # Escribir datos en formato CSV para COPY
                for posicion_sim, descripcion, codigo_unidad, nivel in datos_validos:
                    descripcion_csv = descripcion.replace('"', '""')
                    f.write(f'{posicion_sim}|"{descripcion_csv}"|{codigo_unidad}|{nivel}\n')
                
                f.write("\\.\n\n")
                
                # Agregar estadísticas y verificaciones
                f.write(f"""-- =====================================================
-- ESTADÍSTICAS Y VERIFICACIONES
-- =====================================================

-- Verificar carga
DO $$
DECLARE
    total_registros INTEGER;
    registros_con_fk_validas INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_registros FROM nomenclador;
    
    SELECT COUNT(*) INTO registros_con_fk_validas 
    FROM nomenclador n 
    INNER JOIN unidades u ON n.codigo_unidad = u.codigo;
    
    RAISE NOTICE 'Registros insertados en nomenclador: %', total_registros;
    RAISE NOTICE 'Registros con FK válidas: %', registros_con_fk_validas;
    
    IF total_registros != {len(datos_validos)} THEN
        RAISE WARNING 'Discrepancia en cantidad de registros esperados';
    END IF;
    
    IF registros_con_fk_validas != total_registros THEN
        RAISE WARNING 'Hay registros con códigos de unidad inválidos';
    END IF;
END $$;

-- Estadísticas por código de unidad
SELECT 
    n.codigo_unidad,
    u.descripcion as unidad_descripcion,
    COUNT(*) as cantidad_registros
FROM nomenclador n
INNER JOIN unidades u ON n.codigo_unidad = u.codigo
GROUP BY n.codigo_unidad, u.descripcion
ORDER BY n.codigo_unidad;

-- Ejemplos de registros insertados
SELECT posicion_sim, LEFT(descripcion, 60) as descripcion_resumida, codigo_unidad
FROM nomenclador 
ORDER BY posicion_sim 
LIMIT 10;
""")
            
            return True
            
        except Exception as e:
            logger.error(f"Error generando SQL: {e}")
            return False
    
    def mostrar_estadisticas(self):
        """Muestra estadísticas del procesamiento"""
        logger.info("=" * 60)
        logger.info("ESTADÍSTICAS DE PROCESAMIENTO")
        logger.info("=" * 60)
        
        if self.modo == 'analizar':
            logger.info(f"Palabras problemáticas encontradas: {len(self.palabras_problematicas)}")
            logger.info(f"Archivo de correcciones generado: {self.fixes_file}")
        else:
            logger.info(f"Registros procesados: {self.registros_procesados:,}")
            logger.info(f"Registros válidos: {self.registros_validos:,}")
            logger.info(f"Registros inválidos: {self.registros_procesados - self.registros_validos:,}")
            if self.registros_procesados > 0:
                logger.info(f"Tasa de éxito: {(self.registros_validos/self.registros_procesados)*100:.1f}%")
            logger.info(f"Correcciones aplicadas: {len(self.correcciones)}")
        
        if self.errores:
            logger.warning(f"Total de errores: {len(self.errores)}")
            if len(self.errores) <= 10:
                for error in self.errores:
                    logger.warning(f"  - {error}")
            else:
                for i, error in enumerate(self.errores[:5]):
                    logger.warning(f"  - {error}")
                logger.warning(f"  ... y {len(self.errores)-5} errores más")
        
        # Mostrar análisis de registros inválidos
        if self.registros_invalidos_muestra:
            logger.info("=" * 60)
            logger.info("ANÁLISIS DE REGISTROS INVÁLIDOS (Primeros 10)")
            logger.info("=" * 60)
            
            for i, muestra in enumerate(self.registros_invalidos_muestra[:10], 1):
                logger.info(f"\n--- Registro inválido #{i} ---")
                logger.info(f"Longitud: {muestra['longitud']} caracteres")
                logger.info(f"Error: {muestra['error']}")
                logger.info(f"Caracteres especiales: {muestra['caracteres_especiales']}")
                if 'campos_count' in muestra:
                    logger.info(f"Campos encontrados: {muestra['campos_count']}")
                if 'posicion_sim_raw' in muestra:
                    logger.info(f"Posición SIM raw: '{muestra['posicion_sim_raw']}'")
                logger.info(f"Línea: {muestra['linea']}")
        
        if self.modo == 'generar':
            logger.info(f"Archivo SQL generado: {self.output_file}")

def main():
    parser = argparse.ArgumentParser(description='Procesador de nomenclador AFIP')
    parser.add_argument('--analizar', action='store_true', 
                       help='Modo análisis: genera archivo de correcciones CSV')
    parser.add_argument('--generar', action='store_true', 
                       help='Modo generación: usa archivo de correcciones para generar SQL')
    parser.add_argument('input_file', help='Archivo de entrada (nomenclador_23102025.txt)')
    parser.add_argument('output_file', nargs='?', help='Archivo de salida (.sql)')
    parser.add_argument('--fixes-file', default='nomenclador-fixes.csv',
                       help='Archivo de correcciones CSV (default: nomenclador-fixes.csv)')
    
    args = parser.parse_args()
    
    # Validar argumentos
    if not args.analizar and not args.generar:
        parser.error("Debe especificar --analizar o --generar")
    
    if args.analizar and args.generar:
        parser.error("No puede especificar ambos --analizar y --generar")
    
    if args.generar and not args.output_file:
        parser.error("En modo --generar debe especificar archivo de salida")
    
    if not Path(args.input_file).exists():
        logger.error(f"Archivo de entrada no encontrado: {args.input_file}")
        sys.exit(1)
    
    # Determinar modo y archivos
    modo = 'analizar' if args.analizar else 'generar'
    output_file = args.output_file if args.output_file else 'nomenclador_procesado.sql'
    
    logger.info(f"🚀 Iniciando procesamiento en modo: {modo.upper()}")
    logger.info(f"📁 Archivo entrada: {args.input_file}")
    if modo == 'analizar':
        logger.info(f"📝 Archivo correcciones: {args.fixes_file}")
    else:
        logger.info(f"📁 Archivo salida: {output_file}")
        logger.info(f"📝 Archivo correcciones: {args.fixes_file}")
    
    processor = NomencladorProcessor(
        input_file=args.input_file,
        output_file=output_file,
        modo=modo,
        fixes_file=args.fixes_file
    )
    
    if processor.procesar():
        processor.mostrar_estadisticas()
        logger.info("✅ Procesamiento completado exitosamente")
        
        if modo == 'analizar':
            print(f"\n🎯 SIGUIENTE PASO:")
            print(f"1. Edita manualmente: {args.fixes_file}")
            print(f"2. Completa las correcciones en la segunda columna")
            print(f"3. Ejecuta: python {sys.argv[0]} --generar {args.input_file} {output_file}")
        else:
            print(f"\n🎯 SIGUIENTE PASO:")
            print(f"Ejecutar el archivo SQL generado:")
            print(f"docker exec -i postgres_tesys psql -U postgres -d comercio_exterior_argentina < {output_file}")
    else:
        logger.error("❌ Error en el procesamiento")
        sys.exit(1)

if __name__ == "__main__":
    main()