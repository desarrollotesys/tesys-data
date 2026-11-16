#!/usr/bin/env python3
"""Tests para generar_importacion_subitems.py

Cubre el bugfix 2026-10-01: DETALLE="" se descartaba igual que un campo
ausente (None), perdiendo filas de subitems REALES (con cantidad/FOB
propios) cuyo único problema era no tener sufijos codificados.

Caso real verificado: 26001IC04160560N/0005/0001 y /0002 (zR9 agosto 2026),
DETALLE="", cantidad=1440.00/1440.00, fob=1440.00/2304.00.

Ejecutar: python3 test_importacion_subitems.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generar_importacion_subitems import ImportacionSubitemsProcessor


def make_proc():
    return ImportacionSubitemsProcessor()


def test_detalle_vacio_con_cantidad_fob_reales_se_preserva():
    """Caso real: DETALLE="" pero cantidad/FOB != 0 — antes se descartaba
    la fila entera, perdiendo datos reales de cantidad y FOB."""
    proc = make_proc()
    row = ['"26001IC04160560N"', '"0005"', '"0001"', '""', '1440.00', '1440.00']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None, "La fila NO debe descartarse: DETALLE vacío es un valor real"
    assert registro['detalle_completo'] == ''
    assert registro['cantidad_unidades_subitem'] == '1440.00'
    assert registro['fob_dolar_subitem'] == '1440.00'


def test_detalle_ausente_sigue_siendo_none_y_se_descarta():
    """Si el campo DETALLE viene realmente vacío/ausente de forma anómala
    (ej. menos columnas de las esperadas), la fila se sigue descartando.
    Este test verifica que el cambio no afloja la validación de campos
    obligatorios (despacho_id/item_id/subitem_id)."""
    proc = make_proc()
    row = ['"26001IC04160560N"', '"0005"', '""', '""', '1440.00', '1440.00']  # subitem_id vacío
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is None
    assert any('subitem_id faltante' in e for e in proc.errores)


def test_detalle_con_sufijos_normal_sigue_funcionando():
    """Caso no-vacío (regla general, no debe romperse por el fix)."""
    proc = make_proc()
    row = ['"26073IC04088221C"', '"0005"', '"0001"', '"AA(SKF)-AB(CR 99149)-CA00-"', '5.00', '42.55']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert registro['detalle_completo'] == 'AA(SKF)-AB(CR 99149)-CA00-'


def test_pseudo_subitem_0000_con_detalle_no_vacio_se_preserva():
    """Pseudo-subitem 0000 con AA/AB reales (marca/modelo) — debe
    preservarse igual que antes; el fix no afecta este caso."""
    proc = make_proc()
    row = ['"26073IC04088221C"', '"0001"', '"0000"', '"AA(SKF)-AB(6006 2RS2/C4GJN)-CA00-"', '0.00', '0.00']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert registro['detalle_completo'] == 'AA(SKF)-AB(6006 2RS2/C4GJN)-CA00-'


def test_despacho_id_invalido_sigue_descartando():
    """despacho_id con longitud incorrecta: fila descartada (sin cambios)."""
    proc = make_proc()
    row = ['"CORTO"', '"0001"', '"0000"', '""', '0.00', '0.00']
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is None
    assert any('despacho_id invalido' in e for e in proc.errores)


def test_formatear_valor_copy_detalle_vacio_no_es_null():
    """COPY debe escribir cadena vacía real para detalle_completo='',
    no '\\N' (que lo convertiría en NULL y violaría NOT NULL / perdería
    el valor real)."""
    proc = make_proc()
    assert proc.formatear_valor_copy('', allow_empty_string=True) == ''
    assert proc.formatear_valor_copy(None, allow_empty_string=True) == '\\N'


def test_formatear_valor_copy_otros_campos_sin_allow_empty_siguen_null():
    """Campos que NO son detalle_completo (ej. cantidad/fob ausentes)
    deben seguir mapeando '' y None a \\N — el fix es específico de
    detalle_completo, no un cambio global de comportamiento."""
    proc = make_proc()
    assert proc.formatear_valor_copy(None) == '\\N'
    assert proc.formatear_valor_copy('') == '\\N'
    assert proc.formatear_valor_copy('1440.00') == '1440.00'


def test_detalle_con_pipe_embebido_dentro_de_comillas():
    """DETALLE con '|' embebido dentro de comillas: csv.reader no debe
    partir el campo en columnas extra (mismo caso ya cubierto para
    exportaciones)."""
    import csv
    import io
    linea_zr9 = '"26073IC04088221C"|"0005"|"0001"|"AA(SKF)-AB(CR|99149)-CA00-"|5.00|42.55\n'
    row = next(csv.reader(io.StringIO(linea_zr9), delimiter='|'))
    assert len(row) == 6, f"El '|' embebido partió la fila en columnas extra: {row}"
    proc = make_proc()
    registro = proc.procesar_registro(row, linea_num=1)
    assert registro is not None
    assert '|' in registro['detalle_completo']


if __name__ == '__main__':
    tests = [
        test_detalle_vacio_con_cantidad_fob_reales_se_preserva,
        test_detalle_ausente_sigue_siendo_none_y_se_descarta,
        test_detalle_con_sufijos_normal_sigue_funcionando,
        test_pseudo_subitem_0000_con_detalle_no_vacio_se_preserva,
        test_despacho_id_invalido_sigue_descartando,
        test_formatear_valor_copy_detalle_vacio_no_es_null,
        test_formatear_valor_copy_otros_campos_sin_allow_empty_siguen_null,
        test_detalle_con_pipe_embebido_dentro_de_comillas,
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
