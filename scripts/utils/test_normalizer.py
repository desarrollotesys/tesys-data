#!/usr/bin/env python3
"""
Test suite para DataNormalizer
Ejecutar: python3 test_normalizer.py
"""

import sys
from pathlib import Path

# Importar normalizador
from data_normalizer import DataNormalizer


def test_encoding_corrupto():
    """Test: Corrección de encoding corrupto"""
    print("🧪 Test 1: Encoding corrupto")

    normalizer = DataNormalizer()

    tests = [
        ("COMPUTADORAS PORTÃ�TILES", "COMPUTADORAS PORTÁTILES"),
        ("SEÑALIZACIÃ", "SEÑALIZACIÓN"),
        ("Ã±", "ñ"),
        ("Ã©", "é"),
        ("Ã­", "í"),
        ("Ã³", "ó"),
        ("Ãº", "ú"),
    ]

    for entrada, esperado in tests:
        resultado = normalizer.clean_text(entrada)
        if resultado == esperado:
            print(f"  ✅ '{entrada}' → '{resultado}'")
        else:
            print(f"  ❌ '{entrada}' → '{resultado}' (esperado: '{esperado}')")

    print()


def test_guiones_y_espacios():
    """Test: Eliminación de guiones y espacios"""
    print("🧪 Test 2: Guiones y espacios")

    normalizer = DataNormalizer()

    tests = [
        ("  -- PRODUCTO --  ", "PRODUCTO"),
        ("--- PRUEBA ---", "PRUEBA"),
        ("  TEXTO   CON   ESPACIOS  ", "TEXTO CON ESPACIOS"),
        ("\t\tTABS\t\t", "TABS"),
        ("TEXTO\n\nCON\n\nNEWLINES", "TEXTO CON NEWLINES"),
    ]

    for entrada, esperado in tests:
        resultado = normalizer.clean_text(entrada)
        if resultado == esperado:
            print(f"  ✅ '{entrada}' → '{resultado}'")
        else:
            print(f"  ❌ '{entrada}' → '{resultado}' (esperado: '{esperado}')")

    print()


def test_valores_null():
    """Test: Detección de valores NULL"""
    print("🧪 Test 3: Valores NULL")

    normalizer = DataNormalizer()

    valores_null = [
        "",
        "   ",
        "NULL",
        "N/A",
        "-",
        "--",
        "---",
    ]

    for entrada in valores_null:
        resultado = normalizer.clean_text(entrada)
        if resultado is None:
            print(f"  ✅ '{entrada}' → None")
        else:
            print(f"  ❌ '{entrada}' → '{resultado}' (esperado: None)")

    print()


def test_cuit():
    """Test: Validación y limpieza de CUIT"""
    print("🧪 Test 4: CUIT")

    normalizer = DataNormalizer()

    tests = [
        (" 30-50401884-5 ", "30504018845"),
        ("30504018845", "30504018845"),
        ("30-504-018-845", "30504018845"),
        ("INVALIDO", None),
        ("123", None),  # Muy corto
        ("123456789012", None),  # Muy largo
    ]

    for entrada, esperado in tests:
        resultado = normalizer.clean_cuit(entrada)
        if resultado == esperado:
            print(f"  ✅ '{entrada}' → '{resultado}'")
        else:
            print(f"  ❌ '{entrada}' → '{resultado}' (esperado: '{esperado}')")

    print()


def test_fechas():
    """Test: Conversión de fechas"""
    print("🧪 Test 5: Fechas")

    normalizer = DataNormalizer()

    tests = [
        ("07/01/25", "2025-01-07"),
        ("31/12/24", "2024-12-31"),
        ("01/01/00", "2000-01-01"),
        ("15/06/99", "1999-06-15"),
        ("INVALIDO", None),
        ("32/13/25", None),  # Día/mes inválidos
    ]

    for entrada, esperado in tests:
        resultado = normalizer.convert_date(entrada)
        if resultado == esperado:
            print(f"  ✅ '{entrada}' → '{resultado}'")
        else:
            print(f"  ❌ '{entrada}' → '{resultado}' (esperado: '{esperado}')")

    print()


def test_numeros():
    """Test: Validación de números"""
    print("🧪 Test 6: Números")

    normalizer = DataNormalizer()

    # Decimales
    tests_decimal = [
        ("1234.56", "1234.56"),
        ("  1234.56  ", "1234.56"),
        ("0.00", "0.00"),
        ("INVALIDO", None),
    ]

    print("  📊 Decimales:")
    for entrada, esperado in tests_decimal:
        resultado = normalizer.clean_decimal(entrada)
        if resultado == esperado:
            print(f"    ✅ '{entrada}' → '{resultado}'")
        else:
            print(f"    ❌ '{entrada}' → '{resultado}' (esperado: '{esperado}')")

    # Enteros
    tests_integer = [
        ("1234", 1234),
        ("1234.0", 1234),
        ("  123  ", 123),
        ("INVALIDO", None),
    ]

    print("  📊 Enteros:")
    for entrada, esperado in tests_integer:
        resultado = normalizer.clean_integer(entrada)
        if resultado == esperado:
            print(f"    ✅ '{entrada}' → {resultado}")
        else:
            print(f"    ❌ '{entrada}' → {resultado} (esperado: {esperado})")

    print()


def test_fila_completa():
    """Test: Limpieza de fila completa"""
    print("🧪 Test 7: Fila completa")

    normalizer = DataNormalizer()

    row = [
        "25001DIR3000001G",           # despacho_id
        "07/01/25",                   # fecha
        "30504018845",                # CUIT
        "  PRODUCTO CON Ã± Y Ã³  ",  # descripción corrupta
        "1234.56",                    # decimal
        "---",                        # valor NULL
    ]

    field_cleaners = {
        0: normalizer.clean_text,
        1: normalizer.convert_date,
        2: normalizer.clean_cuit,
        3: normalizer.clean_text,
        4: normalizer.clean_decimal,
        5: normalizer.clean_text,
    }

    resultado = normalizer.clean_row(row, field_cleaners)
    esperado = [
        "25001DIR3000001G",
        "2025-01-07",
        "30504018845",
        "PRODUCTO CON ñ Y ó",
        "1234.56",
        None,
    ]

    print("  Entrada:")
    for i, val in enumerate(row):
        print(f"    [{i}] '{val}'")

    print("\n  Resultado:")
    for i, val in enumerate(resultado):
        print(f"    [{i}] '{val}'")

    print("\n  Esperado:")
    for i, val in enumerate(esperado):
        print(f"    [{i}] '{val}'")

    if resultado == esperado:
        print("\n  ✅ Test pasado")
    else:
        print("\n  ❌ Test fallido")

    print()


def test_escape_postgresql():
    """Test: Escape para PostgreSQL COPY"""
    print("🧪 Test 8: Escape PostgreSQL")

    tests = [
        ("Texto normal", "Texto normal"),
        ("Línea 1\nLínea 2", "Línea 1\\nLínea 2"),
        ("Texto\tcon\ttabs", "Texto\\tcon\\ttabs"),
        ("Backslash\\test", "Backslash\\\\test"),
    ]

    for entrada, esperado in tests:
        resultado = DataNormalizer.escape_for_copy(entrada)
        if resultado == esperado:
            print(f"  ✅ '{entrada}' → '{resultado}'")
        else:
            print(f"  ❌ '{entrada}' → '{resultado}' (esperado: '{esperado}')")

    print()


def test_escape_csv():
    """Test: Escape para CSV"""
    print("🧪 Test 9: Escape CSV")

    tests = [
        ("Texto normal", "Texto normal"),
        ('Texto con "comillas"', '"Texto con ""comillas"""'),
        ("Texto, con, comas", '"Texto, con, comas"'),
        ("Línea 1\nLínea 2", '"Línea 1\nLínea 2"'),
    ]

    for entrada, esperado in tests:
        resultado = DataNormalizer.escape_for_csv(entrada)
        if resultado == esperado:
            print(f"  ✅ '{entrada}' → '{resultado}'")
        else:
            print(f"  ❌ '{entrada}' → '{resultado}' (esperado: '{esperado}')")

    print()


def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 80)
    print("TEST SUITE: DataNormalizer")
    print("=" * 80)
    print()

    test_encoding_corrupto()
    test_guiones_y_espacios()
    test_valores_null()
    test_cuit()
    test_fechas()
    test_numeros()
    test_fila_completa()
    test_escape_postgresql()
    test_escape_csv()

    print("=" * 80)
    print("✅ TESTS COMPLETADOS")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
