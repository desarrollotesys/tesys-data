#!/usr/bin/env python3
"""Bloqueo automático: un mes de EXPORTACIONES no se considera completo si
las claves únicas de los archivos fuente (zR9/zR8) no están todas presentes
en las tablas destino (exportacion_subitems/exportacion_ventajas).

Hermano de validar_mes_completo_importacion.py — mismo motivo de existir
(Fase 5 agosto 202608 detectó que un mes podía quedar cargado solo hasta
despachos/items sin que nada lo marcara como incompleto), aplicado a
exportaciones. A diferencia de importación:
  - exportación no tiene capa LST (no hay precedencia que verificar);
  - las tablas de exportación usan la columna `mes_archivo` (el lote AFIP,
    ej. '202609') para filtrar, NO fecha_oficializacion — un lote puede
    traer despachos oficializados en el mes anterior o siguiente (ver
    docs/SEPTIEMBRE202609_CARGA_PRODUCCION_REPORTE.md), así que filtrar por
    fecha daría falsos incompletos.

Uso (con DSN directo, requiere psycopg2):
    python3 validar_mes_completo_exportacion.py --periodo 202609 \
        --raw-dir data/mensuales/2026/09_septiembre/raw/exportacion/202609Expo \
        --dsn "postgresql://postgres@localhost/comercio_exterior_argentina"

Uso (vía docker exec, sin psycopg2 ni puerto publicado al host):
    python3 validar_mes_completo_exportacion.py --periodo 202609 \
        --raw-dir data/mensuales/2026/09_septiembre/raw/exportacion/202609Expo \
        --docker-container postgres_tesys

Exit code 0: mes OK (todas las claves fuente están en destino, o no hay fuente).
Exit code 1: INCOMPLETO -- hay claves fuente ausentes en destino.
Exit code 2: error de uso / no se pudo conectar o encontrar archivos.
"""
import argparse
import sys
from pathlib import Path

MAX_EJEMPLOS = 20


def _parse_pipe_quoted(linea: str):
    import csv
    import io

    linea = linea.rstrip("\n").rstrip("\r")
    if not linea:
        return None
    try:
        row = next(csv.reader(io.StringIO(linea), delimiter="|"))
    except StopIteration:
        return None
    return [c.strip().strip('"') for c in row]


def claves_zr9(raw_dir: Path) -> set:
    """Claves únicas (despacho_id, item_id, subitem_id) del archivo zR9 (subitems)."""
    claves = set()
    for f in raw_dir.rglob("zR9*"):
        with open(f, "r", encoding="latin-1", errors="replace") as fh:
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
    """Claves únicas (despacho_id, item_id, ventaja) del archivo zR8 (ventajas)."""
    claves = set()
    for f in raw_dir.rglob("zR8*"):
        with open(f, "r", encoding="latin-1", errors="replace") as fh:
            for linea in fh:
                row = _parse_pipe_quoted(linea)
                if not row or len(row) < 3:
                    continue
                despacho_id, item_id, ventaja = row[0], row[1], row[2]
                if not despacho_id or not item_id or not ventaja:
                    continue
                claves.add((despacho_id, item_id, ventaja))
    return claves


def _destino(conexion, periodo: str, tabla: str, columnas: str) -> set:
    query = f"SELECT {columnas} FROM {tabla} WHERE mes_archivo = '{periodo}'"

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


def destino_subitems(conexion, periodo: str) -> set:
    return _destino(conexion, periodo, "exportacion_subitems", "despacho_id, item_id, subitem_id")


def destino_ventajas(conexion, periodo: str) -> set:
    return _destino(conexion, periodo, "exportacion_ventajas", "despacho_id, item_id, ventaja")


def reportar(nombre: str, fuente: set, destino: set) -> bool:
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
    ap.add_argument("--raw-dir", required=True, help="Directorio con los archivos zR9/zR8 crudos del período (ej. .../202609Expo)")
    ap.add_argument("--dsn", default=None, help="DSN de PostgreSQL (solo lectura). Alternativa a --docker-container")
    ap.add_argument("--docker-container", default=None,
                     help="Nombre del contenedor Postgres (ej. postgres_tesys). Alternativa a --dsn")
    ap.add_argument("--docker-db", default="comercio_exterior_argentina",
                     help="Base de datos dentro del contenedor (con --docker-container)")
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

    print(f"=== Validación mes completo (claves únicas): exportaciones {args.periodo} ===")

    try:
        fuente_subitems = claves_zr9(raw_dir)
        fuente_ventajas = claves_zr8(raw_dir)
    except Exception as e:
        print(f"ERROR leyendo archivos fuente: {e}", file=sys.stderr)
        return 2

    try:
        dest_subitems = destino_subitems(conexion, args.periodo)
        dest_ventajas = destino_ventajas(conexion, args.periodo)
    except Exception as e:
        print(f"ERROR consultando base de datos: {e}", file=sys.stderr)
        return 2

    incompleto = False
    incompleto |= reportar("zR9 -> exportacion_subitems", fuente_subitems, dest_subitems)
    incompleto |= reportar("zR8 -> exportacion_ventajas", fuente_ventajas, dest_ventajas)

    print()
    if incompleto:
        print(f"RESULTADO: el período {args.periodo} NO debe marcarse como completo.")
        print("Hay clave(s) fuente ausentes en la(s) tabla(s) destino (ver detalle arriba).")
        return 1

    print(f"RESULTADO: el período {args.periodo} pasa la validación de completitud.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
