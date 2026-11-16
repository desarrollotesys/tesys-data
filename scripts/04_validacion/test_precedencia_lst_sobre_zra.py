#!/usr/bin/env python3
"""Test de precedencia LST > zRA para importacion_obligaciones.

Confirma, con una base real (sqlite en memoria, misma semántica SQL que el
ON CONFLICT DO NOTHING de PostgreSQL usado en producción), que:

  1. Si LST carga una clave (despacho_id, item_id, concepto, obligacion)
     primero, y zRA intenta cargar la MISMA clave con un valor distinto
     después, el valor de zRA NO reemplaza al de LST (queda el de LST).
  2. Si zRA carga una clave que LST todavía no tiene, SÍ se inserta
     (zRA completa claves faltantes, no reemplaza existentes).
  3. Si LST carga DESPUÉS de zRA (orden real de producción: zRA primero,
     LST al final con DO UPDATE), el valor final es el de LST — porque
     LST usa DO UPDATE SET monto=EXCLUDED.monto, no DO NOTHING.

Caso real que originó este test: piloto enero 202601 (2026-10-01), 511
claves concepto='056'/obligacion='P' en conflicto entre zRA y LST; las 511
coincidían exacto con el valor de LST en destino. Ver
docs/PILOTO_ENERO202601_INSERCION_FALTANTES.md.

Ejecutar: python3 test_precedencia_lst_sobre_zra.py
"""
import sqlite3
import sys


def nueva_tabla(conn):
    conn.execute("""
        CREATE TABLE importacion_obligaciones (
            despacho_id TEXT,
            item_id TEXT,
            concepto TEXT,
            obligacion TEXT,
            monto REAL,
            PRIMARY KEY (despacho_id, item_id, concepto, obligacion)
        )
    """)


def insertar_zra_do_nothing(conn, filas):
    """Replica el patrón real de generar_importacion_obligaciones.py:
    ON CONFLICT (...) DO NOTHING."""
    conn.executemany(
        """
        INSERT INTO importacion_obligaciones (despacho_id, item_id, concepto, obligacion, monto)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (despacho_id, item_id, concepto, obligacion) DO NOTHING
        """,
        filas,
    )


def insertar_lst_do_update(conn, filas):
    """Replica el patrón real de generar_importacion_lst.py:
    ON CONFLICT (...) DO UPDATE SET monto = EXCLUDED.monto."""
    conn.executemany(
        """
        INSERT INTO importacion_obligaciones (despacho_id, item_id, concepto, obligacion, monto)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (despacho_id, item_id, concepto, obligacion)
        DO UPDATE SET monto = excluded.monto
        """,
        filas,
    )


def monto_de(conn, clave):
    row = conn.execute(
        "SELECT monto FROM importacion_obligaciones WHERE despacho_id=? AND item_id=? AND concepto=? AND obligacion=?",
        clave,
    ).fetchone()
    return row[0] if row else None


CLAVE_056P = ("26001IC01000001Z", "0001", "056", "P")
CLAVE_FALTANTE = ("26001IC01000099X", "0001", "056", "P")


def test_lst_primero_zra_despues_no_reemplaza():
    """Caso real del piloto enero 202601: LST ya cargó 661.91 para esta
    clave; zRA (corrido después, con DO NOTHING) intenta cargar 1268.83.
    El valor debe seguir siendo el de LST."""
    conn = sqlite3.connect(":memory:")
    nueva_tabla(conn)
    insertar_lst_do_update(conn, [(*CLAVE_056P, 661.91)])
    insertar_zra_do_nothing(conn, [(*CLAVE_056P, 1268.83)])
    assert monto_de(conn, CLAVE_056P) == 661.91, "zRA NO debe reemplazar un valor ya cargado por LST"


def test_zra_completa_clave_faltante():
    """zRA SÍ debe insertar una clave que LST no trajo (ventaja de
    'solo completar faltantes', no de 'nunca insertar nada')."""
    conn = sqlite3.connect(":memory:")
    nueva_tabla(conn)
    insertar_lst_do_update(conn, [(*CLAVE_056P, 661.91)])
    insertar_zra_do_nothing(conn, [(*CLAVE_056P, 1268.83), (*CLAVE_FALTANTE, 50.00)])
    assert monto_de(conn, CLAVE_056P) == 661.91, "clave existente sigue sin tocarse"
    assert monto_de(conn, CLAVE_FALTANTE) == 50.00, "clave faltante SÍ debe insertarse"


def test_orden_real_produccion_zra_luego_lst():
    """Orden real en producción: zRA se carga primero (carga masiva
    mensual), LST se carga después (llega más tarde, por archivo aparte).
    Con DO UPDATE, LST corrige/confirma el valor final — consistente con
    la precedencia LST > zRA independientemente del orden de carga."""
    conn = sqlite3.connect(":memory:")
    nueva_tabla(conn)
    insertar_zra_do_nothing(conn, [(*CLAVE_056P, 1268.83)])
    insertar_lst_do_update(conn, [(*CLAVE_056P, 661.91)])
    assert monto_de(conn, CLAVE_056P) == 661.91, "LST debe prevalecer sin importar el orden de carga"


if __name__ == "__main__":
    tests = [
        test_lst_primero_zra_despues_no_reemplaza,
        test_zra_completa_clave_faltante,
        test_orden_real_produccion_zra_luego_lst,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
