#!/usr/bin/env python3
"""
Sistema centralizado de normalización y limpieza de datos
Reutilizable para importación, exportación y API backend

Este módulo proporciona funciones para:
- Normalización de encoding (UTF-8, Latin-1, CP1252)
- Limpieza de caracteres especiales
- Corrección de tildes y caracteres corruptos
- Validación de formatos
- Escape de caracteres para PostgreSQL

Autor: Tesys Data Team
Fecha: 2025-11-11
"""

import re
import unicodedata
from typing import Optional, Dict, List, Callable
from pathlib import Path
import chardet
from decimal import Decimal, InvalidOperation


class DataNormalizer:
    """
    Clase principal para normalización de datos

    Diseñada para ser:
    - Reutilizable (importación + exportación)
    - Configurable (reglas personalizables)
    - Extensible (fácil agregar nuevas reglas)
    - Testeable (cada función es independiente)
    """

    # ============================================
    # CONFIGURACIÓN DE REEMPLAZOS
    # ============================================

    # Diccionario de caracteres corruptos comunes -> corrección
    CHAR_REPLACEMENTS = {
        # Tildes corruptas (encoding mixto UTF-8/Latin-1)
        '\xc3\xa1': 'á',  # a con tilde corrupta
        '\xc3\xa9': 'é',  # e con tilde corrupta
        '\xc3\xad': 'í',  # i con tilde corrupta
        '\xc3\xb3': 'ó',  # o con tilde corrupta
        '\xc3\xba': 'ú',  # u con tilde corrupta
        '\xc3\xb1': 'ñ',  # eñe corrupta
        '\xc3\x91': 'Ñ',  # Eñe mayuscula corrupta

        # Símbolos de reemplazo Unicode
        '\ufffd': '',     # Replacement character (eliminar)

        # Espacios y caracteres invisibles
        '\xa0': ' ',  # Non-breaking space
        '\u200b': '', # Zero-width space
        '\u00a0': ' ', # No-break space
    }

    # Patrones regex para limpieza avanzada
    REGEX_PATTERNS = {
        # Múltiples espacios → un solo espacio
        'multiple_spaces': (r'\s+', ' '),

        # Guiones al inicio/final (-- o - al principio/fin)
        'leading_dashes': (r'^-+\s*', ''),
        'trailing_dashes': (r'\s*-+$', ''),

        # Puntos suspensivos excesivos
        'excessive_dots': (r'\.{4,}', '...'),

        # Caracteres de control (excepto tab, newline)
        'control_chars': (r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', ''),
    }

    # Valores considerados NULL
    NULL_VALUES = {
        '',
        'NULL',
        'null',
        'N/A',
        'n/a',
        'NA',
        'none',
        'None',
        '-',
        '--',
        '---',
    }

    def __init__(self, strict_mode: bool = False):
        """
        Inicializa el normalizador

        Args:
            strict_mode: Si True, lanza excepciones en lugar de devolver None
        """
        self.strict_mode = strict_mode
        self.stats = {
            'total_processed': 0,
            'chars_replaced': 0,
            'nulls_converted': 0,
            'errors': 0
        }

    # ============================================
    # DETECCIÓN Y CONVERSIÓN DE ENCODING
    # ============================================

    @staticmethod
    def detect_file_encoding(file_path: Path, sample_size: int = 100000) -> str:
        """
        Detecta el encoding de un archivo automáticamente

        Args:
            file_path: Ruta al archivo
            sample_size: Bytes a leer para detección (default 100KB)

        Returns:
            Encoding detectado ('utf-8', 'latin-1', 'cp1252', etc.)
        """
        with open(file_path, 'rb') as f:
            raw_data = f.read(sample_size)
            result = chardet.detect(raw_data)

            encoding = result['encoding']
            confidence = result['confidence']

            # Si confianza baja, intentar UTF-8 primero
            if confidence < 0.7:
                try:
                    raw_data.decode('utf-8')
                    return 'utf-8'
                except UnicodeDecodeError:
                    pass

            # Normalizar nombres de encoding
            if encoding:
                encoding = encoding.lower()
                if encoding in ['iso-8859-1', 'latin1', 'latin-1']:
                    return 'latin-1'
                elif encoding in ['windows-1252', 'cp1252']:
                    return 'cp1252'

            return encoding or 'utf-8'

    @staticmethod
    def normalize_encoding(text: str, source_encoding: Optional[str] = None) -> str:
        """
        Normaliza texto a UTF-8 desde cualquier encoding

        Args:
            text: Texto a normalizar
            source_encoding: Encoding original (si se conoce)

        Returns:
            Texto normalizado en UTF-8
        """
        if not text:
            return text

        if source_encoding and source_encoding != 'utf-8':
            try:
                # Convertir de source_encoding a UTF-8
                text = text.encode(source_encoding).decode('utf-8', errors='replace')
            except (UnicodeDecodeError, UnicodeEncodeError, LookupError):
                # Si falla, continuar con el texto original
                pass

        # Normalizar forma Unicode (NFD → NFC)
        # NFD: á = 'a' + '´' (2 caracteres)
        # NFC: á = 'á' (1 carácter) ✓ Preferido
        text = unicodedata.normalize('NFC', text)

        return text

    # ============================================
    # LIMPIEZA DE TEXTO
    # ============================================

    def clean_text(
        self,
        text: str,
        fix_encoding: bool = True,
        remove_control_chars: bool = True,
        normalize_spaces: bool = True,
        remove_dashes: bool = True,
        strip: bool = True
    ) -> Optional[str]:
        """
        Limpieza completa de texto

        Args:
            text: Texto a limpiar
            fix_encoding: Corregir caracteres de encoding corrupto
            remove_control_chars: Eliminar caracteres de control
            normalize_spaces: Normalizar espacios múltiples
            remove_dashes: Eliminar guiones al inicio/final
            strip: Aplicar strip() al final

        Returns:
            Texto limpio o None si es un valor NULL
        """
        if not text:
            return None

        self.stats['total_processed'] += 1

        # Convertir a string si no lo es
        text = str(text)

        # Verificar valores NULL
        if text.strip() in self.NULL_VALUES:
            self.stats['nulls_converted'] += 1
            return None

        # 1. Corregir encoding corrupto
        if fix_encoding:
            original_text = text
            for corrupt, correct in self.CHAR_REPLACEMENTS.items():
                text = text.replace(corrupt, correct)

            if text != original_text:
                self.stats['chars_replaced'] += 1

        # 2. Eliminar caracteres de control
        if remove_control_chars:
            pattern, replacement = self.REGEX_PATTERNS['control_chars']
            text = re.sub(pattern, replacement, text)

        # 3. Normalizar espacios múltiples
        if normalize_spaces:
            # Reemplazar tabs y newlines por espacios
            text = text.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')

            # Múltiples espacios → un espacio
            pattern, replacement = self.REGEX_PATTERNS['multiple_spaces']
            text = re.sub(pattern, replacement, text)

        # 4. Eliminar guiones al inicio/final
        if remove_dashes:
            pattern, replacement = self.REGEX_PATTERNS['leading_dashes']
            text = re.sub(pattern, replacement, text)

            pattern, replacement = self.REGEX_PATTERNS['trailing_dashes']
            text = re.sub(pattern, replacement, text)

        # 5. Strip final
        if strip:
            text = text.strip()

        # Verificar si quedó vacío después de limpieza
        if not text or text in self.NULL_VALUES:
            self.stats['nulls_converted'] += 1
            return None

        return text

    # ============================================
    # LIMPIEZA ESPECÍFICA POR TIPO DE DATO
    # ============================================

    def clean_numeric(self, value: str) -> Optional[str]:
        """
        Limpia y valida valores numéricos

        Args:
            value: Valor numérico como string

        Returns:
            Valor limpio o None si inválido
        """
        if not value:
            return None

        # Limpiar texto básico
        cleaned = self.clean_text(value, remove_dashes=False)
        if not cleaned:
            return None

        # Validar formato numérico
        try:
            # Intentar convertir a float para validar
            float(cleaned)
            return cleaned
        except ValueError:
            self.stats['errors'] += 1
            return None

    def clean_decimal(self, value: str, decimals: int = 2) -> Optional[str]:
        """
        Limpia y formatea valores decimales

        Args:
            value: Valor decimal como string
            decimals: Número de decimales (default: 2)

        Returns:
            Valor decimal formateado o None
        """
        if not value:
            return None

        cleaned = self.clean_numeric(value)
        if not cleaned:
            return None

        try:
            decimal_val = Decimal(cleaned)
            return str(decimal_val)
        except (InvalidOperation, ValueError):
            self.stats['errors'] += 1
            return None

    def clean_integer(self, value: str) -> Optional[int]:
        """
        Limpia y convierte a entero

        Args:
            value: Valor entero como string

        Returns:
            Valor entero o None
        """
        if not value:
            return None

        cleaned = self.clean_numeric(value)
        if not cleaned:
            return None

        try:
            return int(float(cleaned))  # float() primero por si tiene .0
        except ValueError:
            self.stats['errors'] += 1
            return None

    def clean_cuit(self, cuit: str) -> Optional[str]:
        """
        Limpia y valida formato de CUIT

        Args:
            cuit: CUIT como string

        Returns:
            CUIT limpio (solo dígitos) o None
        """
        if not cuit:
            return None

        # Limpiar texto básico
        cleaned = self.clean_text(cuit)
        if not cleaned:
            return None

        # Remover guiones y espacios
        cleaned = cleaned.replace('-', '').replace(' ', '')

        # Validar que sea solo dígitos
        if not cleaned.isdigit():
            self.stats['errors'] += 1
            return None

        # Validar longitud (11 dígitos)
        if len(cleaned) != 11:
            self.stats['errors'] += 1
            return None

        return cleaned

    def clean_posicion_sim(self, posicion: str) -> Optional[str]:
        """
        Limpia código de posición arancelaria SIM

        Formato esperado: NNNN.NN.NN.NNNX (14-16 caracteres)
        Ejemplo: 8471.30.00.900D

        Args:
            posicion: Posición SIM

        Returns:
            Posición limpia o None
        """
        if not posicion:
            return None

        cleaned = self.clean_text(posicion)
        if not cleaned:
            return None

        # Validar formato básico (dígitos, puntos, letra final opcional)
        if not re.match(r'^\d{4}\.\d{2}\.\d{2}\.', cleaned):
            self.stats['errors'] += 1
            return None

        return cleaned

    # ============================================
    # CONVERSIÓN DE FECHAS
    # ============================================

    def convert_date(self, date_str: str, input_format: str = 'DD/MM/YY') -> Optional[str]:
        """
        Convierte fecha al formato PostgreSQL (YYYY-MM-DD)

        Args:
            date_str: Fecha como string
            input_format: Formato de entrada ('DD/MM/YY' o 'DD/MM/YYYY')

        Returns:
            Fecha en formato YYYY-MM-DD o None
        """
        if not date_str:
            return None

        # Limpiar texto
        cleaned = self.clean_text(date_str)
        if not cleaned:
            return None

        try:
            parts = cleaned.split('/')
            if len(parts) != 3:
                self.stats['errors'] += 1
                return None

            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2])

            # Convertir año de 2 dígitos a 4 dígitos
            if year < 100:
                if year <= 30:  # 00-30 → 2000-2030
                    year += 2000
                else:  # 31-99 → 1931-1999
                    year += 1900

            # Validar rangos
            if not (1 <= month <= 12):
                self.stats['errors'] += 1
                return None

            if not (1 <= day <= 31):
                self.stats['errors'] += 1
                return None

            return f"{year:04d}-{month:02d}-{day:02d}"

        except (ValueError, IndexError):
            self.stats['errors'] += 1
            return None

    # ============================================
    # ESCAPE PARA BASES DE DATOS
    # ============================================

    @staticmethod
    def escape_for_copy(text: str, delimiter: str = '\t') -> str:
        """
        Escapa texto para PostgreSQL COPY command

        Args:
            text: Texto a escapar
            delimiter: Delimitador usado (default: tab)

        Returns:
            Texto escapado
        """
        if not text:
            return ''

        # Reemplazar caracteres especiales de COPY
        text = text.replace('\\', '\\\\')  # Backslash → \\
        text = text.replace('\n', '\\n')   # Newline → \n
        text = text.replace('\r', '\\r')   # Carriage return → \r
        text = text.replace('\t', '\\t')   # Tab → \t

        # Escapar delimitador si es diferente
        if delimiter != '\t':
            text = text.replace(delimiter, '\\' + delimiter)

        return text

    @staticmethod
    def escape_for_csv(text: str) -> str:
        """
        Escapa texto para CSV (formato RFC 4180)

        Args:
            text: Texto a escapar

        Returns:
            Texto escapado y entre comillas si necesario
        """
        if not text:
            return ''

        # Si contiene comillas, comas, o newlines → envolver en comillas
        if any(char in text for char in ['"', ',', '\n', '\r']):
            # Duplicar comillas dobles
            text = text.replace('"', '""')
            return f'"{text}"'

        return text

    # ============================================
    # PROCESAMIENTO BATCH
    # ============================================

    def clean_row(
        self,
        row: List[str],
        field_cleaners: Dict[int, Callable] = None
    ) -> List[Optional[str]]:
        """
        Limpia una fila completa de datos

        Args:
            row: Lista de campos
            field_cleaners: Diccionario {índice: función_limpieza}
                           Si no se especifica, usa clean_text por defecto

        Returns:
            Lista de campos limpios

        Example:
            cleaners = {
                0: normalizer.clean_text,      # Campo 0: texto
                1: normalizer.convert_date,    # Campo 1: fecha
                2: normalizer.clean_cuit,      # Campo 2: CUIT
                3: normalizer.clean_decimal,   # Campo 3: decimal
            }
            cleaned_row = normalizer.clean_row(row, cleaners)
        """
        if field_cleaners is None:
            # Default: clean_text para todos los campos
            return [self.clean_text(field) for field in row]

        cleaned = []
        for idx, field in enumerate(row):
            if idx in field_cleaners:
                cleaner = field_cleaners[idx]
                cleaned.append(cleaner(field))
            else:
                # Sin limpiador específico → clean_text
                cleaned.append(self.clean_text(field))

        return cleaned

    # ============================================
    # ESTADÍSTICAS Y REPORTES
    # ============================================

    def get_stats(self) -> Dict[str, int]:
        """
        Obtiene estadísticas de limpieza

        Returns:
            Diccionario con contadores
        """
        return self.stats.copy()

    def reset_stats(self):
        """Resetea contadores de estadísticas"""
        self.stats = {
            'total_processed': 0,
            'chars_replaced': 0,
            'nulls_converted': 0,
            'errors': 0
        }

    def print_stats(self):
        """Imprime estadísticas en formato legible"""
        print("=" * 50)
        print("ESTADÍSTICAS DE NORMALIZACIÓN")
        print("=" * 50)
        print(f"Total procesados:     {self.stats['total_processed']:,}")
        print(f"Caracteres corregidos: {self.stats['chars_replaced']:,}")
        print(f"Valores NULL:          {self.stats['nulls_converted']:,}")
        print(f"Errores:               {self.stats['errors']:,}")
        print("=" * 50)


# ============================================
# FUNCIONES HELPER (API simplificada)
# ============================================

# Instancia global (singleton) para uso simple
_default_normalizer = DataNormalizer()

def clean_text(text: str) -> Optional[str]:
    """Shortcut: Limpia texto con configuración por defecto"""
    return _default_normalizer.clean_text(text)

def clean_numeric(value: str) -> Optional[str]:
    """Shortcut: Limpia valor numérico"""
    return _default_normalizer.clean_numeric(value)

def clean_cuit(cuit: str) -> Optional[str]:
    """Shortcut: Limpia CUIT"""
    return _default_normalizer.clean_cuit(cuit)

def convert_date(date_str: str) -> Optional[str]:
    """Shortcut: Convierte fecha"""
    return _default_normalizer.convert_date(date_str)

def detect_encoding(file_path: Path) -> str:
    """Shortcut: Detecta encoding de archivo"""
    return DataNormalizer.detect_file_encoding(file_path)


# ============================================
# EJEMPLO DE USO
# ============================================

if __name__ == "__main__":
    # Demo de uso
    normalizer = DataNormalizer()

    print("🧹 DEMO: DataNormalizer\n")

    # Ejemplo 1: Texto con encoding corrupto
    texto_corrupto = "COMPUTADORAS PORTÃ�TILES"
    texto_limpio = normalizer.clean_text(texto_corrupto)
    print(f"1. Encoding corrupto:")
    print(f"   Entrada:  {texto_corrupto}")
    print(f"   Salida:   {texto_limpio}\n")

    # Ejemplo 2: Guiones y espacios
    texto_guiones = "  -- PRODUCTO DE PRUEBA --  "
    texto_limpio = normalizer.clean_text(texto_guiones)
    print(f"2. Guiones y espacios:")
    print(f"   Entrada:  '{texto_guiones}'")
    print(f"   Salida:   '{texto_limpio}'\n")

    # Ejemplo 3: CUIT
    cuit_sucio = " 30-50401884-5 "
    cuit_limpio = normalizer.clean_cuit(cuit_sucio)
    print(f"3. CUIT:")
    print(f"   Entrada:  '{cuit_sucio}'")
    print(f"   Salida:   '{cuit_limpio}'\n")

    # Ejemplo 4: Fecha
    fecha_str = "07/01/25"
    fecha_limpia = normalizer.convert_date(fecha_str)
    print(f"4. Fecha:")
    print(f"   Entrada:  {fecha_str}")
    print(f"   Salida:   {fecha_limpia}\n")

    # Ejemplo 5: Fila completa con diferentes tipos
    row = [
        "25001DIR3000001G",           # despacho_id
        "07/01/25",                   # fecha
        "30504018845",                # CUIT
        "  PRODUCTO CON Ã± Y Ã³  ",  # descripción corrupta
        "1234.56",                    # decimal
        "---",                        # valor NULL
    ]

    cleaners = {
        0: normalizer.clean_text,
        1: normalizer.convert_date,
        2: normalizer.clean_cuit,
        3: normalizer.clean_text,
        4: normalizer.clean_decimal,
        5: normalizer.clean_text,
    }

    cleaned_row = normalizer.clean_row(row, cleaners)

    print("5. Fila completa:")
    print("   Entrada:")
    for i, val in enumerate(row):
        print(f"     [{i}] '{val}'")
    print("\n   Salida:")
    for i, val in enumerate(cleaned_row):
        print(f"     [{i}] '{val}'")

    print("\n")
    normalizer.print_stats()
