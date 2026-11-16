#!/usr/bin/env python3
"""Tests para generar_exportacion_subitems.py

Verifican la lógica de parseo de detalle_completo (campo DETALLE del zR9).
Ejecutar: python3 test_exportacion_subitems.py
"""

import csv
import io
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generar_exportacion_subitems import ExportacionSubitemsProcessor


def make_proc():
    return ExportacionSubitemsProcessor("202607")


def test_detalle_corto_sin_truncado():
    """DETALLE < 100 chars: se almacena completo."""
    proc = make_proc()
    row = ['"26008ECR1007715D"', '"0001"', '"0001"',
           '"AA(TOYOTA)-AB(HILUX)-NA00-"', '3.00', '103266.00']
    # limpiar_campo elimina comillas
    raw = proc.limpiar_campo(row[3])
    result = raw if raw else None
    assert result == 'AA(TOYOTA)-AB(HILUX)-NA00-'
    assert len(result) < 100


def test_detalle_mayor_100_chars_se_preserva_completo():
    """DETALLE > 100 chars: NO se trunca (bug previo: [:100]).

    Caso real: 26008ECR1007715D/0003-0001 (julio 2026, zR9).
    Detalle = 115 chars. El truncado a 100 cortaba en 'AD(E8U7)-AM('
    haciendo que AM y CA00 desaparecieran del regex.
    """
    proc = make_proc()
    detalle_completo = (
        'ZA(002026)-ZB(002755)-ZC(003180)-AA( TOYOTA)-AB(HILUX)'
        '-AC(HILUX CD DSL 4X4 SRX PLUS AT)-AD(E8U7)-AM(8AJBA3CD)-CA00-'
    )
    assert len(detalle_completo) == 115, f"Expected 115, got {len(detalle_completo)}"

    row = ['"26008ECR1007715D"', '"0003"', '"0001"',
           f'"{detalle_completo}"', '3.00', '103266.00']

    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert registro['detalle_completo'] == detalle_completo

    # Verificar que AM y CA00 son parseables del string almacenado
    RE = re.compile(r'([A-Z]{2})(?:\(([^)]*)\)|(\d{2}))-')
    codes = [m.group(1) for m in RE.finditer(registro['detalle_completo'])]
    assert 'AM' in codes, f"AM debe estar en detalle_completo. Codes: {codes}"
    assert 'CA' in codes, f"CA debe estar en detalle_completo. Codes: {codes}"
    assert codes == ['ZA', 'ZB', 'ZC', 'AA', 'AB', 'AC', 'AD', 'AM', 'CA']


def test_detalle_200_chars_se_preserva_completo():
    """DETALLE de 200 chars (caso extremo pero posible): ningún truncado."""
    proc = make_proc()
    # Construir detalle largo con muchos sufijos
    detalle = '-'.join(f'Z{chr(65+i)}(00{i:04d})' for i in range(15)) + '-'
    assert len(detalle) > 100

    row = ['"26008ECR1007715D"', '"0003"', '"0001"',
           f'"{detalle}"', '3.00', '100.00']

    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert registro['detalle_completo'] == detalle


def test_detalle_vacio_devuelve_string_vacio():
    """DETALLE vacío → detalle_completo = '' (no None)."""
    proc = make_proc()
    row = ['"26008ECR1007715D"', '"0001"', '"0001"', '""', '1.00', '100.00']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert registro['detalle_completo'] == ''


def test_detalle_exactamente_100_chars_no_truncado():
    """DETALLE de exactamente 100 chars: se almacena íntegro (no hay error de borde)."""
    proc = make_proc()
    detalle = 'A' * 95 + 'BCDE-'   # 100 chars exactos
    assert len(detalle) == 100
    row = ['"26008ECR1007715D"', '"0001"', '"0001"', f'"{detalle}"', '1.00', '100.00']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert len(registro['detalle_completo']) == 100


def test_campo_anterior_no_alterado_por_detalle_largo():
    """Campos numéricos (cantidad, fob) se parsean correctamente incluso con detalle largo."""
    proc = make_proc()
    detalle = (
        'ZA(002026)-ZB(002755)-ZC(003180)-AA( TOYOTA)-AB(HILUX)'
        '-AC(HILUX CD DSL 4X4 SRX PLUS AT)-AD(E8U7)-AM(8AJBA3CD)-CA00-'
    )
    row = ['"26008ECR1007715D"', '"0003"', '"0001"',
           f'"{detalle}"', '3.00', '103266.00']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert registro['cantidad_unidades_subitem'] == '3.00'
    assert registro['fob_dolar_subitem'] == '103266.00'


def test_detalle_con_pipe_embebido_dentro_de_comillas():
    """DETALLE con '|' embebido dentro de un campo entre comillas: el csv.reader
    (delimiter='|', quoting por defecto) NO debe partir el campo en columnas
    adicionales — el '|' debe preservarse íntegro en detalle_completo.

    Caso real posible: nombre de modelo con '|' u otro separador incrustado
    por el sistema origen dentro de un valor entre comillas del zR9.
    """
    proc = make_proc()
    linea_zr9 = (
        '"26008ECR1007715D"|"0003"|"0001"|'
        '"AA(TOYOTA)-AB(HILUX|SPECIAL)-NA00-"|3.00|103266.00\n'
    )
    row = next(csv.reader(io.StringIO(linea_zr9), delimiter='|'))
    assert len(row) == 6, f"El '|' embebido partió la fila en columnas extra: {row}"
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert registro['detalle_completo'] == 'AA(TOYOTA)-AB(HILUX|SPECIAL)-NA00-'
    assert '|' in registro['detalle_completo']


def test_fila_con_menos_de_6_campos_retorna_none():
    """Fila malformada con menos columnas que las esperadas: se descarta
    (retorna None) en vez de lanzar excepción o guardar datos corruptos.
    """
    proc = make_proc()
    row = ['"26008ECR1007715D"', '"0003"', '"0001"']  # faltan 3 campos
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is None
    assert len(proc.errores) == 1
    assert 'Numero incorrecto de campos' in proc.errores[0]


def test_fila_con_despacho_id_invalido_retorna_none():
    """DESTINACION con longitud incorrecta (no 16 chars): fila descartada,
    no se propaga una excepción.
    """
    proc = make_proc()
    row = ['"CORTO"', '"0003"', '"0001"', '"AA(TOYOTA)-"', '3.00', '103266.00']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is None
    assert any('despacho_id invalido' in e for e in proc.errores)


def test_fila_con_cantidad_no_numerica_no_rompe_el_parseo():
    """Campo numérico corrupto (no decimal válido): se guarda como None
    (via convertir_decimal) en vez de abortar el registro completo — el
    detalle_completo sigue siendo válido aunque el numérico esté corrupto.
    """
    proc = make_proc()
    row = ['"26008ECR1007715D"', '"0003"', '"0001"',
           '"AA(TOYOTA)-AB(HILUX)-"', '"no-es-un-numero"', '103266.00']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert registro['detalle_completo'] == 'AA(TOYOTA)-AB(HILUX)-'
    assert registro['cantidad_unidades_subitem'] is None


if __name__ == '__main__':
    tests = [
        test_detalle_corto_sin_truncado,
        test_detalle_mayor_100_chars_se_preserva_completo,
        test_detalle_200_chars_se_preserva_completo,
        test_detalle_vacio_devuelve_string_vacio,
        test_detalle_exactamente_100_chars_no_truncado,
        test_campo_anterior_no_alterado_por_detalle_largo,
        test_detalle_con_pipe_embebido_dentro_de_comillas,
        test_fila_con_menos_de_6_campos_retorna_none,
        test_fila_con_despacho_id_invalido_retorna_none,
        test_fila_con_cantidad_no_numerica_no_rompe_el_parseo,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
