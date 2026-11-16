#!/usr/bin/env python3
"""Genera el SQL de un "piloto de inserción de faltantes" para un período:
toma los SQL ya generados por generar_importacion_subitems.py /
generar_importacion_ventajas.py / generar_importacion_obligaciones.py
(formato staging + INSERT ... ON CONFLICT DO NOTHING) e inyecta, ANTES de
cada INSERT, una auditoría que reporta:

  1. cuántos candidatos hay en staging,
  2. cuántos ya existen en destino (conflictos de clave),
  3. de esos, cuántos tienen VALORES distintos a lo ya cargado,
  4. una muestra de esas diferencias,
  5. cuántos son realmente faltantes (se van a insertar).

El INSERT original (ON CONFLICT DO NOTHING) ya garantiza que nunca se borra
ni sobrescribe un registro existente — este script solo agrega visibilidad
sobre qué va a pasar ANTES de que pase.

PRECEDENCIA LST > zRA para importacion_obligaciones (confirmado 2026-10-01
con el piloto enero 202601): cuando zRA y LST generan la misma clave
(despacho_id, item_id, concepto, obligacion) — el caso confirmado es
concepto='056'/obligacion='P' — el valor de LST debe prevalecer. Por eso
el INSERT de zRA usa DO NOTHING (nunca pisa lo que ya está) mientras que
el de LST (generar_importacion_lst.py) usa DO UPDATE SET monto=EXCLUDED.monto
(si corre después, corrige/confirma el valor). Este generador NO decide
cuál valor es correcto: solo reporta los conflictos para que un humano los
revise antes de cargar. Ver docs/PILOTO_ENERO202601_INSERCION_FALTANTES.md
para el caso real (511 claves, las 511 coincidían exacto con el LST).

Origen: pedido explícito del usuario tras Fase 5 (202608), para un piloto de
enero 2026 (202601) que inserte únicamente subitems/ventajas/obligaciones(zRA)
faltantes sin tocar lo ya cargado. Pensado para correr primero contra una
base local/staging (nunca directo a producción).

Uso:
    python3 generar_piloto_insercion_faltantes.py \
        --sql-dir data/mensuales/2026/01_enero/sql_PILOT \
        --periodo 202601 \
        --cuartos q1 q2 \
        -o /tmp/piloto_202601_combinado.sql

El archivo de salida NO incluye BEGIN/COMMIT/ROLLBACK — agregalos vos para
controlar explícitamente el modo dry-run (ROLLBACK) vs real (COMMIT).
"""
import argparse
from pathlib import Path

ENTIDADES = {
    "subitems": {
        "staging": "staging_subitems",
        "destino": "importacion_subitems",
        "keycols": ["despacho_id", "item_id", "subitem_id"],
        "valcols": ["detalle_completo", "cantidad_unidades_subitem", "fob_dolar_subitem"],
        "marker": "-- Insertar en tabla final con JOIN a importacion_items",
        "prefijo_archivo": "subitems",
    },
    "ventajas": {
        "staging": "staging_ventajas",
        "destino": "importacion_ventajas",
        "keycols": ["despacho_id", "item_id", "ventaja"],
        "valcols": [],
        "marker": "-- Insertar en tabla final (con fecha_oficializacion via JOIN)",
        "prefijo_archivo": "ventajas",
    },
    "obligaciones": {
        "staging": "staging_obligaciones",
        "destino": "importacion_obligaciones",
        "keycols": ["despacho_id", "item_id", "concepto", "obligacion"],
        "valcols": ["monto"],
        "marker": "-- Insertar en tabla final (con fecha_oficializacion via JOIN)",
        "prefijo_archivo": "obligaciones",
    },
}


def audit_sql(entidad: str, etiqueta: str, cfg: dict) -> str:
    st, dest, keycols = cfg["staging"], cfg["destino"], cfg["keycols"]
    join_cond = " AND ".join(f"s.{k} = d.{k}" for k in keycols)
    select_keys = ", ".join(f"s.{k}" for k in keycols)
    sql = [f"\n-- ===== AUDITORIA pre-INSERT: {entidad} {etiqueta} =====\n"]
    sql.append(f"\\echo '--- {entidad} {etiqueta}: candidatos en staging ---'\n")
    sql.append(f"SELECT COUNT(*) AS candidatos_staging FROM {st} s;\n")
    sql.append(f"\\echo '--- {entidad} {etiqueta}: conflictos de clave (ya existen en destino) ---'\n")
    sql.append(f"SELECT COUNT(*) AS conflictos_clave FROM {st} s JOIN {dest} d ON {join_cond};\n")
    if cfg["valcols"]:
        diffcond = " OR ".join(f"s.{v} IS DISTINCT FROM d.{v}" for v in cfg["valcols"])
        sql.append(f"\\echo '--- {entidad} {etiqueta}: de esos conflictos, con VALORES distintos ---'\n")
        sql.append(
            f"SELECT COUNT(*) AS conflictos_valor_distinto FROM {st} s "
            f"JOIN {dest} d ON {join_cond} WHERE {diffcond};\n"
        )
        sql.append(f"\\echo '--- {entidad} {etiqueta}: muestra de diferencias de valor (hasta 10) ---'\n")
        valsel = ", ".join(f"s.{v} AS staging_{v}, d.{v} AS destino_{v}" for v in cfg["valcols"])
        sql.append(
            f"SELECT {select_keys}, {valsel} FROM {st} s "
            f"JOIN {dest} d ON {join_cond} WHERE {diffcond} LIMIT 10;\n"
        )
    sql.append(f"\\echo '--- {entidad} {etiqueta}: faltantes reales (se van a insertar) ---'\n")
    sql.append(
        f"SELECT COUNT(*) AS a_insertar FROM {st} s "
        f"WHERE NOT EXISTS (SELECT 1 FROM {dest} d WHERE {join_cond});\n"
    )
    return "".join(sql)


def split_and_build(sql_dir: Path, entidad: str, periodo: str, etiqueta: str) -> str:
    cfg = ENTIDADES[entidad]
    fname = sql_dir / f"{cfg['prefijo_archivo']}_{periodo}_{etiqueta}.sql"
    content = fname.read_text()
    idx = content.index(cfg["marker"])
    staging_part, insert_part = content[:idx], content[idx:]
    return staging_part + audit_sql(entidad, etiqueta, cfg) + "\n" + insert_part


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sql-dir", required=True, type=Path,
                     help="Directorio con los SQL ya generados por los generadores existentes")
    ap.add_argument("--periodo", required=True, help="AAAAMM, ej. 202601")
    ap.add_argument("--cuartos", nargs="+", default=["q1", "q2"], help="Sufijos de archivo a procesar en orden")
    ap.add_argument("--entidades", nargs="+", default=["subitems", "ventajas", "obligaciones"],
                     choices=list(ENTIDADES))
    ap.add_argument("-o", "--output", required=True, type=Path)
    args = ap.parse_args()

    partes = []
    for entidad in args.entidades:
        for etiqueta in args.cuartos:
            partes.append(f"\n-- ================= {entidad} {etiqueta} =================\n")
            partes.append(split_and_build(args.sql_dir, entidad, args.periodo, etiqueta))

    args.output.write_text("".join(partes))
    print(f"Generado: {args.output} ({args.output.stat().st_size:,} bytes)")
    print("Recordatorio: agregar BEGIN; al inicio y ROLLBACK;/COMMIT; al final "
          "segun si es un dry-run o la ejecucion real. NUNCA apuntar esto "
          "directo a produccion sin antes correrlo contra una base local/staging.")


if __name__ == "__main__":
    main()
