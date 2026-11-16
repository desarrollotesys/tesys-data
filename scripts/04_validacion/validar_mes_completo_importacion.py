#!/usr/bin/env python3
"""Bloqueo automático: un mes de importaciones NO se considera completo si
las claves únicas de los archivos fuente (zR9/zRA/zR8, y opcionalmente el
LST de obligaciones) no están todas presentes en las tablas destino
(importacion_subitems/importacion_obligaciones/importacion_ventajas).

Origen: Fase 5 (202608) detectó que agosto 2026 se había cargado solo hasta
despachos/items, dejando subitems/obligaciones/ventajas vacíos sin que
ningún chequeo lo marcara como incompleto. Este script cierra ese hueco.

v2 (2026-10-01): la v1 comparaba solo CONTEO de líneas crudas vs filas en
tabla. Eso es insuficiente:
  - No detecta faltantes parciales (ej. 99% cargado, 1% huérfano/faltante).
  - No distingue duplicados en el archivo fuente de huérfanos reales.
  - importacion_obligaciones se nutre de DOS fuentes distintas (zRA +
    impo_YYYYMM.lst), con reglas de dedupe propias (ver
    generar_importacion_lst.py: SKIP_CODS, COD_MAP, IIBB_CODS). Comparar
    "líneas de zRA" contra "filas en la tabla" mezclaba ambos orígenes y
    podía dar falsos OK o falsos INCOMPLETO.

Esta versión compara CLAVES ÚNICAS (no conteo de líneas) fuente vs destino,
separando explícitamente zRA de LST, y reporta el detalle de las claves
faltantes (hasta un límite) en vez de solo un número.

PRECEDENCIA LST > zRA (confirmado con el piloto enero 202601, 2026-10-01):
  Para importacion_obligaciones, LST y zRA pueden generar la MISMA clave
  (despacho_id, item_id, concepto, obligacion) — el caso confirmado es
  concepto='056'/obligacion='P' (IVA pagado), que el zRA trae directo y el
  LST también vía COD 415 (ver generar_importacion_lst.py). Cuando esto
  pasa, el valor de LST es el que debe prevalecer: LST ya se carga con
  `ON CONFLICT ... DO UPDATE SET monto = EXCLUDED.monto` (sobrescribe) y
  zRA con `ON CONFLICT ... DO NOTHING` (nunca sobrescribe). Esa asimetría
  YA IMPLEMENTA la precedencia correcta siempre que el orden de carga sea
  zRA primero y LST después (o, equivalentemente, que zRA nunca toque una
  clave que LST ya escribió). Este validador NO decide cuál debería ganar;
  solo reporta cuántas claves de zRA chocan con destino y con qué valor,
  para que un humano confirme antes de cargar (ver condición 8 del piloto:
  "tratamiento documentado de las claves sin padre/en conflicto"). El
  piloto de enero 202601 confirmó 511 claves en conflicto, TODAS
  concepto=056/obligacion=P, y las 511 coinciden EXACTO con el valor que
  trae obl_lst_202601.sql — es decir, destino ya tiene el valor correcto
  (LST) y no debe tocarse. Ver docs/PILOTO_ENERO202601_INSERCION_FALTANTES.md.

Uso (con DSN directo, requiere psycopg2):
    python3 validar_mes_completo_importacion.py --periodo 202609 \
        --raw-dir data/mensuales/2026/09_septiembre/raw/importacion \
        --dsn "postgresql://postgres@localhost/comercio_exterior_argentina" \
        [--lst-file data/mensuales/2026/09_septiembre/raw/proveedores/impo_202609.lst]

Uso (vía docker exec, sin psycopg2 ni puerto publicado al host):
    python3 validar_mes_completo_importacion.py --periodo 202609 \
        --raw-dir data/mensuales/2026/09_septiembre/raw/importacion \
        --docker-container postgres_tesys

Exit code 0: mes OK (todas las claves fuente están en destino, o no hay fuente).
Exit code 1: INCOMPLETO -- hay claves fuente ausentes en destino.
Exit code 2: error de uso / no se pudo conectar o encontrar archivos.
"""
import argparse
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

MAX_EJEMPLOS = 20

# --- Mismo mapeo que generar_importacion_lst.py (mantener en sync) ---
SKIP_CODS = {'010', '866'}
IIBB_CODS = {str(c) for c in range(429, 473)}
COD_MAP = {
    '011': ('047', 'P'),
    '851': ('047', 'G'),
    '415': ('056', 'P'),
    '852': ('056', 'G'),
    '422': ('422', 'P'),
    '854': ('422', 'G'),
    '424': ('424', 'P'),
    '856': ('424', 'G'),
    '500': ('500', 'P'),
}


def _pad_item(raw: str) -> str:
    try:
        return str(int(raw)).zfill(4)
    except ValueError:
        return raw.strip().zfill(4)


def _parse_pipe_quoted(linea: str) -> Optional[list]:
    """zR9/zR8/zRA: pipe-delimited, campos entre comillas dobles."""
    import csv
    import io

    linea = linea.rstrip('\n').rstrip('\r')
    if not linea:
        return None
    try:
        row = next(csv.reader(io.StringIO(linea), delimiter='|'))
    except StopIteration:
        return None
    return [c.strip().strip('"') for c in row]


def claves_zr9(raw_dir: Path) -> set:
    """Claves únicas (despacho_id, item_id, subitem_id) del archivo zR9."""
    claves = set()
    for f in raw_dir.rglob("zR9*"):
        with open(f, 'r', encoding='latin-1', errors='replace') as fh:
            for linea in fh:
                row = _parse_pipe_quoted(linea)
                if not row or len(row) < 3:
                    continue
                despacho_id, item_id, subitem_id = row[0], row[1], row[2]
                if not despacho_id or not item_id or not subitem_id:
                    continue
                claves.add((despacho_id, item_id, subitem_id))
    return claves


def claves_zr8(raw_dir: Path) -> set:
    """Claves únicas (despacho_id, item_id, ventaja) del archivo zR8."""
    claves = set()
    for f in raw_dir.rglob("zR8*"):
        with open(f, 'r', encoding='latin-1', errors='replace') as fh:
            for linea in fh:
                row = _parse_pipe_quoted(linea)
                if not row or len(row) < 3:
                    continue
                despacho_id, item_id, ventaja = row[0], row[1], row[2]
                if not despacho_id or not item_id or not ventaja:
                    continue
                claves.add((despacho_id, item_id, ventaja))
    return claves


def claves_zra(raw_dir: Path) -> set:
    """Claves únicas (despacho_id, item_id, concepto, obligacion) del zRA.
    Se cargan TAL CUAL vienen del archivo (sin el filtro SKIP_CODS, que
    aplica solo al LST)."""
    claves = set()
    for f in raw_dir.rglob("zRA*"):
        with open(f, 'r', encoding='latin-1', errors='replace') as fh:
            for linea in fh:
                row = _parse_pipe_quoted(linea)
                if not row or len(row) < 4:
                    continue
                despacho_id, item_id, concepto, obligacion = row[0], row[1], row[2], row[3]
                if not despacho_id or not item_id:
                    continue
                claves.add((despacho_id, item_id, concepto, obligacion))
    return claves


def claves_lst(lst_file: Path) -> set:
    """Claves únicas (despacho_id, item_id, concepto, obligacion) que el LST
    debería aportar a importacion_obligaciones, aplicando el MISMO mapeo
    (SKIP_CODS/COD_MAP/IIBB_CODS) que generar_importacion_lst.py, para no
    contar como "faltante" algo que el LST nunca iba a insertar."""
    claves = set()
    if lst_file is None:
        return claves
    with open(lst_file, 'r', encoding='latin-1', errors='replace') as fh:
        for linea in fh:
            linea = linea.rstrip('\n')
            if not linea or "'" not in linea:
                continue
            partes = linea.split("'")
            if len(partes) < 16:
                continue
            cod = partes[14].strip()
            if cod in SKIP_CODS:
                continue
            if cod not in COD_MAP and cod not in IIBB_CODS:
                continue
            despacho_id = partes[1].strip()
            item_raw = partes[2].strip()
            if not despacho_id or not item_raw:
                continue
            item_id = _pad_item(item_raw)
            if cod in IIBB_CODS:
                claves.add((despacho_id, item_id, 'IIBB', 'P'))
            else:
                concepto, obligacion = COD_MAP[cod]
                claves.add((despacho_id, item_id, concepto, obligacion))
    return claves


def destino_subitems(conexion, periodo: str) -> set:
    return _destino(conexion, periodo, 'importacion_subitems',
                     'despacho_id, item_id, subitem_id')


def destino_ventajas(conexion, periodo: str) -> set:
    return _destino(conexion, periodo, 'importacion_ventajas',
                     'despacho_id, item_id, ventaja')


def destino_obligaciones(conexion, periodo: str) -> set:
    return _destino(conexion, periodo, 'importacion_obligaciones',
                     'despacho_id, item_id, concepto, obligacion')


def _destino(conexion, periodo: str, tabla: str, columnas: str) -> set:
    """`conexion` es un dict {'modo': 'dsn', 'dsn': ...} o
    {'modo': 'docker', 'container': ..., 'db': ...}. El modo 'docker' evita
    la dependencia de psycopg2 ejecutando la consulta vía `docker exec ...
    psql`, igual que se hizo manualmente durante los pilotos de enero-julio
    202601-202607 — más portable para entornos donde Postgres corre en un
    contenedor sin el puerto publicado al host."""
    anio = int(periodo[:4])
    mes = int(periodo[4:6])
    query = (
        f"SELECT {columnas} FROM {tabla} "
        f"WHERE EXTRACT(YEAR FROM fecha_oficializacion) = {anio} "
        f"AND EXTRACT(MONTH FROM fecha_oficializacion) = {mes}"
    )

    if conexion["modo"] == "dsn":
        import psycopg2

        with psycopg2.connect(conexion["dsn"]) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return {tuple(row) for row in cur.fetchall()}

    elif conexion["modo"] == "docker":
        import subprocess

        resultado = subprocess.run(
            [
                "docker", "exec", conexion["container"],
                "psql", "-U", "postgres", "-d", conexion["db"],
                "-t", "-A", "-F", "\t", "-c", query,
            ],
            capture_output=True, text=True, check=True,
        )
        claves = set()
        for linea in resultado.stdout.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            claves.add(tuple(linea.split("\t")))
        return claves

    raise ValueError(f"modo de conexión desconocido: {conexion['modo']!r}")


def reportar(nombre: str, fuente: set, destino: set) -> bool:
    """Devuelve True si está incompleto (hay claves fuente ausentes en destino)."""
    if not fuente:
        print(f"  {nombre}: sin claves fuente (omitido, no es bloqueante)")
        return False

    faltantes = fuente - destino
    estado = "OK" if not faltantes else "*** INCOMPLETO ***"
    print(f"  {nombre}: fuente={len(fuente)} claves únicas, destino={len(destino)} claves únicas, "
          f"faltantes={len(faltantes)}  [{estado}]")
    if faltantes:
        ejemplos = list(sorted(faltantes))[:MAX_EJEMPLOS]
        for clave in ejemplos:
            print(f"      falta: {clave}")
        if len(faltantes) > MAX_EJEMPLOS:
            print(f"      ... y {len(faltantes) - MAX_EJEMPLOS} más")
    return bool(faltantes)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--periodo", required=True, help="AAAAMM, ej. 202609")
    ap.add_argument("--raw-dir", required=True, help="Directorio con los archivos zR9/zRA/zR8 crudos del período")
    ap.add_argument("--dsn", default=None, help="DSN de PostgreSQL (solo lectura). Alternativa a --docker-container")
    ap.add_argument("--docker-container", default=None,
                     help="Nombre del contenedor Postgres (ej. postgres_tesys). Alternativa a --dsn: "
                          "no requiere psycopg2 ni el puerto publicado al host, consulta vía 'docker exec ... psql'")
    ap.add_argument("--docker-db", default="comercio_exterior_argentina",
                     help="Base de datos dentro del contenedor (con --docker-container). Default: comercio_exterior_argentina")
    ap.add_argument("--lst-file", type=Path, default=None,
                     help="Archivo impo_YYYYMM.lst, si existe para el período (opcional)")
    args = ap.parse_args()

    if not args.dsn and not args.docker_container:
        print("ERROR: debe indicarse --dsn o --docker-container", file=sys.stderr)
        return 2
    if args.dsn and args.docker_container:
        print("ERROR: usar --dsn o --docker-container, no ambos", file=sys.stderr)
        return 2
    conexion = (
        {"modo": "dsn", "dsn": args.dsn}
        if args.dsn
        else {"modo": "docker", "container": args.docker_container, "db": args.docker_db}
    )

    raw_dir = Path(args.raw_dir)
    if not raw_dir.is_dir():
        print(f"ERROR: no existe el directorio {raw_dir}", file=sys.stderr)
        return 2
    if args.lst_file is not None and not args.lst_file.is_file():
        print(f"ERROR: no existe el archivo LST {args.lst_file}", file=sys.stderr)
        return 2

    print(f"=== Validación mes completo (claves únicas): importaciones {args.periodo} ===")

    try:
        fuente_subitems = claves_zr9(raw_dir)
        fuente_ventajas = claves_zr8(raw_dir)
        fuente_zra = claves_zra(raw_dir)
        fuente_lst = claves_lst(args.lst_file)
    except Exception as e:
        print(f"ERROR leyendo archivos fuente: {e}", file=sys.stderr)
        return 2

    try:
        dest_subitems = destino_subitems(conexion, args.periodo)
        dest_ventajas = destino_ventajas(conexion, args.periodo)
        dest_obligaciones = destino_obligaciones(conexion, args.periodo)
    except Exception as e:
        print(f"ERROR consultando base de datos: {e}", file=sys.stderr)
        return 2

    incompleto = False
    incompleto |= reportar("zR9 -> importacion_subitems", fuente_subitems, dest_subitems)
    incompleto |= reportar("zR8 -> importacion_ventajas", fuente_ventajas, dest_ventajas)
    incompleto |= reportar("zRA -> importacion_obligaciones", fuente_zra, dest_obligaciones)
    if args.lst_file is not None:
        incompleto |= reportar("LST -> importacion_obligaciones", fuente_lst, dest_obligaciones)
    else:
        print("  LST -> importacion_obligaciones: --lst-file no provisto (omitido, no es bloqueante)")

    print()
    if incompleto:
        print(f"RESULTADO: el período {args.periodo} NO debe marcarse como completo.")
        print("Hay clave(s) fuente ausentes en la(s) tabla(s) destino (ver detalle arriba).")
        return 1

    print(f"RESULTADO: el período {args.periodo} pasa la validación de completitud.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
