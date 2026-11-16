#!/usr/bin/env python3
"""Análisis PARAMETRIZADO de un piloto mensual de inserción de faltantes
(subitems/ventajas/obligaciones-zRA), sin ningún conteo hardcodeado.

Generaliza lo hecho manualmente para enero 202601 (ver
docs/PILOTO_ENERO202601_INSERCION_FALTANTES.md y
docs/ENERO202601_CARGA_PRODUCCION_REPORTE.md): dado un período y los SQL ya
generados por los generadores existentes (generar_importacion_subitems.py /
generar_importacion_ventajas.py / generar_importacion_obligaciones.py), más
el estado actual de destino (CSV exportado solo-lectura, o consulta directa),
calcula automáticamente:

  - filas candidatas y claves únicas por tabla (zR9/zR8/zRA),
  - filas faltantes por tabla (candidatas que no existen en destino),
  - conflictos de clave zRA vs destino (clave ya existe) y, de esos,
    cuántos tienen valor distinto,
  - qué pares (concepto, obligacion) están involucrados en esos conflictos,
  - si hay un LST para el período: si las claves en conflicto coinciden
    EXACTO (numérico) con el valor que trae el LST,
  - conteos finales esperados por tabla tras insertar solo lo faltante.

No ejecuta nada contra ninguna base — es puramente analítico, sobre archivos
locales (SQL candidato + CSV de snapshot de destino). Pensado para correr
ANTES de armar la transacción SQL real (ver generar_piloto_insercion_faltantes.py
para la parte de staging+auditoría dentro de la transacción).

Uso:
    python3 analizar_piloto_mensual.py \
        --periodo 202602 \
        --sql-dir data/mensuales/2026/02_febrero/sql_PILOT \
        --destino-subitems /tmp/subitems_202602_actual.csv \
        --destino-obligaciones /tmp/obligaciones_202602_actual.csv \
        --destino-ventajas /tmp/ventajas_202602_actual.csv \
        [--lst-file data/mensuales/lst_2026/obl_lst_202602.sql] \
        --cuartos q1 q2
"""
import argparse
import csv
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional


def _unescape_copy_text(valor: str) -> str:
    """Des-escapa el formato COPY ... FORMAT text (el que usan los .sql
    generados): '\\\\' -> '\\', '\\t' -> tab, '\\n' -> newline, '\\N' -> NULL
    (se maneja aparte). Necesario para comparar contra el destino, que se
    exporta en FORMAT csv (reglas de escape distintas) — sin esto, un
    detalle_completo con '\\' literal (ej. "AB(\\)") se ve como string
    distinto aunque el valor real sea idéntico."""
    if valor == "\\N":
        return None
    return (
        valor.replace("\\\\", "\x00")  # backslash literal, protegido temporalmente
        .replace("\\t", "\t")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\x00", "\\")
    )


def parse_staging_block(path: Path, ncols: int) -> dict:
    """Parsea el bloque COPY ... FROM STDIN de un SQL generado por los
    generadores existentes (ambos formatos: 'FROM stdin;' en la misma línea
    que el cierre de paréntesis, o 'FROM STDIN WITH (...)' en línea propia)."""
    data = {}
    in_copy = False
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("FROM STDIN") or line.rstrip().endswith("FROM stdin;"):
                in_copy = True
                continue
            if in_copy:
                if line.strip() == "\\.":
                    in_copy = False
                    continue
                parts = [_unescape_copy_text(p) for p in line.rstrip("\n").split("\t")]
                if len(parts) < ncols:
                    continue
                key = tuple(parts[: ncols - 1])
                # val se guarda como tupla de 1 elemento (no escalar) para que
                # coincida con el formato de cargar_destino_csv (valcols=[...])
                # y valores_iguales() compare longitudes correctamente — un
                # escalar vs una tupla de 1 siempre "difiere" por len(), dando
                # falsos conflictos de valor (bug real, visto en marzo 202603
                # con concepto=010: candidato==destino pero se reportaba como
                # distinto).
                val = (parts[ncols - 1],) if ncols > 1 else None
                data[key] = val
    return data


def parse_staging_multivalor(path: Path, nkey: int, nval: int) -> dict:
    """Para subitems: clave de nkey columnas + nval columnas de valor."""
    data = {}
    in_copy = False
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("FROM STDIN") or line.rstrip().endswith("FROM stdin;"):
                in_copy = True
                continue
            if in_copy:
                if line.strip() == "\\.":
                    in_copy = False
                    continue
                parts = [_unescape_copy_text(p) for p in line.rstrip("\n").split("\t")]
                if len(parts) < nkey + nval:
                    continue
                key = tuple(parts[:nkey])
                val = tuple(parts[nkey : nkey + nval])
                data[key] = val
    return data


def cargar_candidatos_subitems(sql_dir: Path, periodo: str, cuartos: list) -> dict:
    out = {}
    for q in cuartos:
        f = sql_dir / f"subitems_{periodo}_{q}.sql"
        out.update(parse_staging_multivalor(f, nkey=3, nval=3))
    return out


def cargar_candidatos_ventajas(sql_dir: Path, periodo: str, cuartos: list) -> dict:
    """Las 3 columnas (despacho_id, item_id, ventaja) son TODAS la clave —
    no hay un campo de "valor" separado (a diferencia de subitems/obligaciones).
    Usar parse_staging_block (que separa ncols-1 clave + 1 valor) acá sería
    incorrecto: colapsaría distintas ventajas del mismo item en una sola
    clave (despacho_id, item_id), subcontando candidatos reales."""
    out = {}
    for q in cuartos:
        f = sql_dir / f"ventajas_{periodo}_{q}.sql"
        parsed = parse_staging_multivalor(f, nkey=3, nval=0)
        out.update({k: None for k in parsed})
    return out


def cargar_candidatos_obligaciones(sql_dir: Path, periodo: str, cuartos: list) -> dict:
    out = {}
    for q in cuartos:
        f = sql_dir / f"obligaciones_{periodo}_{q}.sql"
        out.update(parse_staging_block(f, ncols=5))
    return out


def cargar_lst(lst_file: Optional[Path]) -> dict:
    if lst_file is None or not lst_file.exists():
        return {}
    return parse_staging_block(lst_file, ncols=5)


def cargar_destino_csv(path: Optional[Path], keycols: list, valcols: list) -> dict:
    """CSV con header (como el que genera COPY ... WITH (FORMAT csv, HEADER true))."""
    data = {}
    if path is None or not path.exists():
        return data
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            key = tuple(row[k] for k in keycols)
            val = tuple(row[v] for v in valcols) if valcols else None
            data[key] = val
    return data


def to_decimal(s) -> Optional[Decimal]:
    if s is None:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def valores_iguales(a, b) -> bool:
    """Compara tuplas de strings numéricamente cuando se puede (evita falsos
    positivos tipo '70.90' != '70.9'), y como texto si no son numéricos."""
    if a is None or b is None:
        return a == b
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        dx, dy = to_decimal(x), to_decimal(y)
        if dx is not None and dy is not None:
            if dx != dy:
                return False
        elif x != y:
            return False
    return True


def analizar(nombre: str, candidatos: dict, destino: dict) -> dict:
    claves_candidatas = set(candidatos)
    claves_destino = set(destino)
    faltantes = claves_candidatas - claves_destino
    conflictos = claves_candidatas & claves_destino
    conflictos_valor_distinto = {
        k for k in conflictos if not valores_iguales(candidatos[k], destino[k])
    }
    return {
        "nombre": nombre,
        "candidatos": len(claves_candidatas),
        "destino_actual": len(claves_destino),
        "faltantes": len(faltantes),
        "conflictos_clave": len(conflictos),
        "conflictos_valor_distinto": len(conflictos_valor_distinto),
        "conteo_final_esperado": len(claves_destino) + len(faltantes),
        "_claves_conflicto_valor_distinto": conflictos_valor_distinto,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--periodo", required=True)
    ap.add_argument("--sql-dir", required=True, type=Path)
    ap.add_argument("--destino-subitems", type=Path, default=None)
    ap.add_argument("--destino-obligaciones", type=Path, default=None)
    ap.add_argument("--destino-ventajas", type=Path, default=None)
    ap.add_argument("--lst-file", type=Path, default=None)
    ap.add_argument("--cuartos", nargs="+", default=["q1", "q2"])
    args = ap.parse_args()

    print(f"=== Análisis piloto {args.periodo} (parametrizado, sin conteos hardcodeados) ===\n")

    # --- subitems ---
    cand_sub = cargar_candidatos_subitems(args.sql_dir, args.periodo, args.cuartos)
    dest_sub = cargar_destino_csv(
        args.destino_subitems,
        keycols=["despacho_id", "item_id", "subitem_id"],
        valcols=["detalle_completo", "cantidad_unidades_subitem", "fob_dolar_subitem"],
    )
    r_sub = analizar("subitems", cand_sub, dest_sub)
    print(f"[subitems] candidatos={r_sub['candidatos']:,} destino_actual={r_sub['destino_actual']:,} "
          f"faltantes={r_sub['faltantes']:,} conflictos_clave={r_sub['conflictos_clave']:,} "
          f"conflictos_valor_distinto={r_sub['conflictos_valor_distinto']:,} "
          f"-> final_esperado={r_sub['conteo_final_esperado']:,}")

    # --- ventajas ---
    cand_ven = cargar_candidatos_ventajas(args.sql_dir, args.periodo, args.cuartos)
    dest_ven = cargar_destino_csv(
        args.destino_ventajas, keycols=["despacho_id", "item_id", "ventaja"], valcols=[]
    )
    r_ven = analizar("ventajas", cand_ven, dest_ven)
    print(f"[ventajas] candidatos={r_ven['candidatos']:,} destino_actual={r_ven['destino_actual']:,} "
          f"faltantes={r_ven['faltantes']:,} conflictos_clave={r_ven['conflictos_clave']:,} "
          f"-> final_esperado={r_ven['conteo_final_esperado']:,}")

    # --- obligaciones (zRA) ---
    cand_obl = cargar_candidatos_obligaciones(args.sql_dir, args.periodo, args.cuartos)
    dest_obl = cargar_destino_csv(
        args.destino_obligaciones,
        keycols=["despacho_id", "item_id", "concepto", "obligacion"],
        valcols=["monto"],
    )
    r_obl = analizar("obligaciones", cand_obl, dest_obl)
    print(f"[obligaciones] candidatos={r_obl['candidatos']:,} destino_actual={r_obl['destino_actual']:,} "
          f"faltantes={r_obl['faltantes']:,} conflictos_clave={r_obl['conflictos_clave']:,} "
          f"conflictos_valor_distinto={r_obl['conflictos_valor_distinto']:,} "
          f"-> final_esperado={r_obl['conteo_final_esperado']:,}")

    conflictos_valor = r_obl["_claves_conflicto_valor_distinto"]
    conceptos = Counter((k[2], k[3]) for k in conflictos_valor)
    print(f"\n--- Conceptos/obligacion involucrados en los {len(conflictos_valor):,} "
          f"conflictos de VALOR de obligaciones ---")
    for (concepto, obligacion), n in sorted(conceptos.items(), key=lambda kv: -kv[1]):
        print(f"    concepto={concepto} obligacion={obligacion}: {n:,} claves")

    # --- comparación contra LST, si está disponible ---
    lst = cargar_lst(args.lst_file)
    if lst:
        coincide = sum(
            1 for k in conflictos_valor if k in lst and valores_iguales(dest_obl[k], lst[k])
        )
        no_en_lst = sum(1 for k in conflictos_valor if k not in lst)
        difiere_lst = len(conflictos_valor) - coincide - no_en_lst
        print(f"\n--- Comparación contra LST ({args.lst_file.name}) ---")
        print(f"    De los {len(conflictos_valor):,} conflictos de valor:")
        print(f"      destino == LST (exacto, numérico): {coincide:,}")
        print(f"      destino != LST (requiere revisión manual): {difiere_lst:,}")
        print(f"      clave ausente en LST (requiere revisión manual): {no_en_lst:,}")
        if difiere_lst or no_en_lst:
            print("    *** ATENCIÓN: no todos los conflictos se explican por LST. "
                  "NO asumir automáticamente la precedencia LST>zRA sin revisión. ***")
    else:
        print(f"\n--- Sin archivo LST provisto para {args.periodo}: no se puede confirmar "
              f"automáticamente el origen de los {len(conflictos_valor):,} conflictos de valor. ---")

    print("\n=== RESUMEN CONTEOS FINALES ESPERADOS (tras insertar solo lo faltante) ===")
    print(f"  subitems:     {r_sub['conteo_final_esperado']:,}")
    print(f"  ventajas:     {r_ven['conteo_final_esperado']:,}")
    print(f"  obligaciones: {r_obl['conteo_final_esperado']:,}")
    print(f"  conflictos obligaciones preservados (no tocar): {r_obl['conflictos_valor_distinto']:,}")


if __name__ == "__main__":
    main()
