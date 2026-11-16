#!/usr/bin/env python3
"""
cargar_item_calculos.py
=======================
Carga flete_dolar_item / seguro_dolar_item en importacion_item_calculos
replicando la fórmula legacy (calculosimpo.sh + cargaimpo.sh).

Fuente autoritativa: pase_legacy_cabi22_26.tsv.gz (PASEFLETE/PASESEGURO de cabi{YY}).
Audit_status: desde CSV generado por auditar_pases_legacy.py (opcional; si no se
              provee, usa 'no_audit').

Uso:
    # Cargar un año completo (todos los batches Q1/Q2)
    python3 cargar_item_calculos.py --anio 2026

    # Cargar un mes específico
    python3 cargar_item_calculos.py --anio 2026 --mes 7

    # Dry-run (no escribe en DB, solo muestra resumen)
    python3 cargar_item_calculos.py --anio 2026 --dry-run

    # Con CSV de auditoría para poblar audit_status
    python3 cargar_item_calculos.py --anio 2026 --audit-csv data/TMP/auditoria_pases_26_completa.csv

Variables de entorno (DB):
    DATABASE_URL   postgresql://user:pass@host/db
    o bien:
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
"""

import argparse
import csv
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Agregar el directorio raíz al path para importar calcular_item_calculos
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts' / '02_importador'))

import calcular_item_calculos as calc

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Detección de backend de DB disponible

def _tiene_psycopg2() -> bool:
    try:
        import psycopg2  # noqa: F401
        return True
    except ImportError:
        return False


def _psql_cmd() -> list[str]:
    """
    Retorna el prefijo de comando psql con parámetros de conexión.
    Prioridad:
      1. psql en PATH (instalación local del cliente PostgreSQL)
      2. docker exec <container> psql  (si TESYS_DOCKER_CONTAINER está definida
         o si el contenedor postgres_tesys está corriendo)
    Falla explícitamente si ninguno está disponible.
    """
    import shutil

    def _conn_args() -> list[str]:
        """Parámetros -h -p -d -U para la conexión."""
        url = os.environ.get('DATABASE_URL', '').replace('postgresql+asyncpg://', 'postgresql://')
        if url:
            return [url]
        args = []
        for flag, var, default in [
            ('-h', 'PGHOST',     'localhost'),
            ('-p', 'PGPORT',     '5432'),
            ('-d', 'PGDATABASE', 'tesys'),
            ('-U', 'PGUSER',     'tesys_user'),
        ]:
            args += [flag, os.environ.get(var, default)]
        return args

    # 1. psql en PATH
    if shutil.which('psql'):
        return ['psql'] + _conn_args()

    # 2. docker exec
    container = os.environ.get('TESYS_DOCKER_CONTAINER', 'postgres_tesys')
    if shutil.which('docker'):
        import subprocess
        check = subprocess.run(
            ['docker', 'inspect', '--format={{.State.Running}}', container],
            capture_output=True, text=True,
        )
        if check.returncode == 0 and 'true' in check.stdout.lower():
            log.info(f'psql no encontrado en PATH — usando docker exec {container}')
            # Para docker exec, la conexión es local dentro del contenedor;
            # usamos -U y -d sin -h (socket Unix interno).
            db   = os.environ.get('PGDATABASE', 'comercio_exterior_argentina')
            user = os.environ.get('PGUSER',     'postgres')
            return ['docker', 'exec', '-i', container, 'psql', '-U', user, '-d', db]

    raise SystemExit(
        'ERROR: ni psycopg2 ni psql están disponibles, y docker no encontró '
        f'el contenedor "{container}".\n'
        '  Opciones:\n'
        '    pip install psycopg2-binary\n'
        '    apt install postgresql-client\n'
        f'    docker start {container}  (si el contenedor existe pero está detenido)\n'
        '    export TESYS_DOCKER_CONTAINER=<nombre-del-contenedor>'
    )


def get_conn():
    """
    Conecta a PostgreSQL usando psycopg2 si está disponible.
    Retorna None si solo hay psql (el loader usa COPY en ese caso).
    """
    if not _tiene_psycopg2():
        return None

    import psycopg2
    url = os.environ.get('DATABASE_URL', '').replace('postgresql+asyncpg://', 'postgresql://')
    if url:
        return psycopg2.connect(url)

    return psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        port=int(os.environ.get('PGPORT', '5432')),
        dbname=os.environ.get('PGDATABASE', 'tesys'),
        user=os.environ.get('PGUSER', 'tesys_user'),
        password=os.environ.get('PGPASSWORD', ''),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Carga del audit CSV

def cargar_audit_csv(path: Optional[Path]) -> dict:
    """
    Carga CSV generado por auditar_pases_legacy.py.
    Retorna dict[despacho_id] = audit_status.
    """
    if path is None or not path.exists():
        if path is not None:
            log.warning(f'Audit CSV no encontrado: {path} — se usará audit_status=no_audit')
        return {}

    audit = {}
    with open(path, newline='', encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            desp   = row.get('despacho_id', '').strip()
            status = row.get('status', 'no_audit').strip()
            if desp:
                audit[desp] = status
    log.info(f'Audit CSV cargado: {len(audit):,} despachos desde {path.name}')
    return audit


# ─────────────────────────────────────────────────────────────────────────────
# Descubrimiento de batches

def descubrir_batches(data_dir: Path, anio: int, mes: Optional[int]) -> list[tuple[str, Path]]:
    """
    Busca todos los directorios de batch para el año (y mes opcional) dado.
    Retorna lista de (batch_nombre, directorio_batch).
    """
    meses_dir = data_dir / 'mensuales' / str(anio)
    if not meses_dir.exists():
        raise SystemExit(f'ERROR: directorio no existe: {meses_dir}')

    batches = []
    for mes_dir in sorted(meses_dir.iterdir()):
        if not mes_dir.is_dir():
            continue
        # Filtrar por mes si se especificó
        if mes is not None:
            try:
                num_mes = int(mes_dir.name.split('_')[0])
            except ValueError:
                continue
            if num_mes != mes:
                continue

        raw_impo = mes_dir / 'raw' / 'importacion'
        if not raw_impo.exists():
            continue

        for batch_dir in sorted(raw_impo.iterdir()):
            if not batch_dir.is_dir():
                continue
            # Verificar que tenga los archivos requeridos
            if (batch_dir / 'zR1.txt').exists() and (batch_dir / 'zR5.txt').exists():
                batches.append((batch_dir.name, batch_dir))

    return batches


# ─────────────────────────────────────────────────────────────────────────────
# Procesamiento de un batch

def procesar_batch(
    batch_nombre: str,
    batch_dir: Path,
    lookup: dict,
    audit_map: dict,
) -> list[dict]:
    """
    Procesa un batch (Q1/Q2) y retorna lista de filas para insertar.
    Usa las funciones de calcular_item_calculos como módulo.
    """
    cabe_raw, items_r5, subitems_r9 = calc.cargar_directorio(batch_dir)
    if not cabe_raw:
        log.debug(f'  {batch_nombre}: sin datos en zR1')
        return []

    artitmp  = calc.calcular_artitmp(items_r5, subitems_r9)
    cabe     = calc.calcular_cabeitmp(cabe_raw, artitmp)
    pase     = calc.construir_pase(cabe)
    calc.asignar_paseflete(cabe, pase, lookup)
    resultados = calc.calcular_flete_item(artitmp, cabe)

    filas = []
    for r in resultados:
        desp = r['despacho_id']
        filas.append({
            'despacho_id':          desp,
            'fecha_oficializacion':  r['fecha'],
            'item_id':               r['item_id'],
            'flete_dolar_item':      r['flete_dolar_item'],
            'seguro_dolar_item':     r['seguro_dolar_item'],
            'fletedolar_despacho':   r['fletedolar'],
            'segurodolar_despacho':  r['segurodolar'],
            'fob_monto_despacho':    r['fob_monto'],
            'fob_divisa_item':       r['fob_divisa_item'],
            'depositario':           cabe[desp]['depositario'] if desp in cabe else None,
            'pasefob':               r['pasefob'],
            'paseflete':             r['paseflete'],
            'paseseguro':            r['paseseguro'],
            'paseflete_fuente':      r['fuente_pase'],
            'audit_status':          audit_map.get(desp, 'no_audit'),
            'batch_origen':          batch_nombre,
        })
    return filas


# ─────────────────────────────────────────────────────────────────────────────
# Carga en DB

INSERT_SQL = """
INSERT INTO importacion_item_calculos (
    despacho_id, fecha_oficializacion, item_id,
    flete_dolar_item, seguro_dolar_item,
    fletedolar_despacho, segurodolar_despacho,
    fob_monto_despacho, fob_divisa_item, depositario,
    pasefob, paseflete, paseseguro,
    paseflete_fuente, audit_status, batch_origen
) VALUES (
    %(despacho_id)s, %(fecha_oficializacion)s, %(item_id)s,
    %(flete_dolar_item)s, %(seguro_dolar_item)s,
    %(fletedolar_despacho)s, %(segurodolar_despacho)s,
    %(fob_monto_despacho)s, %(fob_divisa_item)s, %(depositario)s,
    %(pasefob)s, %(paseflete)s, %(paseseguro)s,
    %(paseflete_fuente)s, %(audit_status)s, %(batch_origen)s
)
ON CONFLICT (despacho_id, fecha_oficializacion, item_id)
DO UPDATE SET
    flete_dolar_item     = EXCLUDED.flete_dolar_item,
    seguro_dolar_item    = EXCLUDED.seguro_dolar_item,
    fletedolar_despacho  = EXCLUDED.fletedolar_despacho,
    segurodolar_despacho = EXCLUDED.segurodolar_despacho,
    fob_monto_despacho   = EXCLUDED.fob_monto_despacho,
    fob_divisa_item      = EXCLUDED.fob_divisa_item,
    depositario          = EXCLUDED.depositario,
    pasefob              = EXCLUDED.pasefob,
    paseflete            = EXCLUDED.paseflete,
    paseseguro           = EXCLUDED.paseseguro,
    paseflete_fuente     = EXCLUDED.paseflete_fuente,
    audit_status         = EXCLUDED.audit_status,
    batch_origen         = EXCLUDED.batch_origen,
    cargado_en           = NOW();
"""

BATCH_SIZE = 5000   # filas por execute_batch

# Columnas en el orden exacto de la tabla (debe coincidir con INSERT_SQL y COPY)
_COLUMNAS_COPY = [
    'despacho_id', 'fecha_oficializacion', 'item_id',
    'flete_dolar_item', 'seguro_dolar_item',
    'fletedolar_despacho', 'segurodolar_despacho',
    'fob_monto_despacho', 'fob_divisa_item', 'depositario',
    'pasefob', 'paseflete', 'paseseguro',
    'paseflete_fuente', 'audit_status', 'batch_origen',
]


def _cargar_via_psycopg2(conn, filas: list[dict]) -> int:
    from psycopg2.extras import execute_batch
    with conn.cursor() as cur:
        execute_batch(cur, INSERT_SQL, filas, page_size=BATCH_SIZE)
    conn.commit()
    return len(filas)


def _filas_a_csv_str(filas: list[dict]) -> str:
    """Serializa filas a string CSV con header. None → string vacío (NULL en COPY)."""
    import csv as csv_mod
    import io
    buf = io.StringIO()
    writer = csv_mod.DictWriter(buf, fieldnames=_COLUMNAS_COPY, extrasaction='ignore',
                                lineterminator='\n')
    writer.writeheader()
    for row in filas:
        writer.writerow({k: ('' if row.get(k) is None else row[k]) for k in _COLUMNAS_COPY})
    return buf.getvalue()


def _cargar_via_copy(filas: list[dict]) -> int:
    """
    Fallback cuando psycopg2 no está disponible.
    Envía todo a psql via stdin en una única sesión (`psql -f -`).

    Usa COPY FROM STDIN (SQL nativo, no \\copy) para que funcione tanto
    con psql local como con `docker exec -i contenedor psql`, donde los
    paths del filesystem del host no son accesibles.

    Protocolo COPY FROM STDIN en psql:
      COPY tabla FROM STDIN CSV HEADER NULL '';
      <datos CSV>
      \\.          ← fin del bloque COPY (backslash-dot en línea propia)
    """
    import subprocess

    if not filas:
        return 0

    cols     = ', '.join(_COLUMNAS_COPY)
    excluded = ',\n        '.join(
        f'{c} = EXCLUDED.{c}'
        for c in _COLUMNAS_COPY
        if c not in ('despacho_id', 'fecha_oficializacion', 'item_id')
    )
    csv_data = _filas_a_csv_str(filas)

    # Script SQL completo enviado por stdin.
    # COPY FROM STDIN termina con "\." en línea propia.
    # Todo en una sola sesión → la tabla TEMP vive hasta COMMIT.
    stdin_script = (
        "BEGIN;\n"
        f"CREATE TEMP TABLE _ict_tmp (LIKE importacion_item_calculos INCLUDING DEFAULTS);\n"
        f"COPY _ict_tmp ({cols}) FROM STDIN CSV HEADER NULL '';\n"
        f"{csv_data}"
        "\\.\n"
        f"INSERT INTO importacion_item_calculos ({cols})\n"
        f"SELECT {cols} FROM _ict_tmp\n"
        "ON CONFLICT (despacho_id, fecha_oficializacion, item_id) DO UPDATE SET\n"
        f"        {excluded},\n"
        "        cargado_en = NOW();\n"
        "DROP TABLE _ict_tmp;\n"
        "COMMIT;\n"
    )

    psql = _psql_cmd()
    env  = dict(os.environ)
    result = subprocess.run(
        psql + ['-f', '-'],          # -f - → leer de stdin
        input=stdin_script,
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'psql falló (rc={result.returncode}):\n{result.stderr[:400]}'
        )
    log.debug(f'psql output: {result.stdout.strip()[:200]}')
    return len(filas)


def cargar_en_db(conn, filas: list[dict], dry_run: bool) -> int:
    """
    Inserta filas en importacion_item_calculos.
    Usa psycopg2 si está disponible, psql COPY como fallback.
    Retorna cantidad de filas procesadas.
    """
    if dry_run or not filas:
        return len(filas)

    if conn is not None:
        return _cargar_via_psycopg2(conn, filas)
    else:
        return _cargar_via_copy(filas)


# ─────────────────────────────────────────────────────────────────────────────
# Validación de casos de control

# Casos que validan por item_id específico (despacho_id → (item_id, flete_esperado))
CASOS_CONTROL_ITEM = {
    '26001IC04001395N': ('0001', 880.20),
    '26001IC04002643K': ('0001', 250.00),
    '26258ZFET000002P': ('0001',  15.39),
}

# Casos que validan por total de despacho (despacho_id → flete_total_esperado)
# 140334K: item0001=177.858161, item0002=22.141839, total=200.00
# 134119Y: audit_status=diff_real en legacy (DEPOSITARIO=2); validamos total ETL vs cabi.fletedolar
CASOS_CONTROL_TOTAL = {
    '26001IC04140334K': 200.00,
}

def validar_casos_control(conn) -> None:
    """Lee desde la DB los casos de control y reporta diferencias."""
    try:
        import psycopg2.extras
    except ImportError:
        log.warning('psycopg2 no disponible, validación omitida')
        return

    todos_desps = list(CASOS_CONTROL_ITEM.keys()) + list(CASOS_CONTROL_TOTAL.keys())

    # Query por item
    sql_item = """
        SELECT despacho_id, item_id,
               flete_dolar_item, paseflete, paseflete_fuente, audit_status
        FROM importacion_item_calculos
        WHERE despacho_id = ANY(%s)
        ORDER BY despacho_id, item_id
    """
    # Query por total de despacho
    sql_total = """
        SELECT despacho_id,
               SUM(flete_dolar_item) AS flete_total,
               MIN(paseflete_fuente) AS paseflete_fuente,
               MIN(audit_status)     AS audit_status
        FROM importacion_item_calculos
        WHERE despacho_id = ANY(%s)
        GROUP BY despacho_id
    """
    log.info('\n── Validación casos de control ──')
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql_item,  (todos_desps,))
        rows_item = cur.fetchall()
        cur.execute(sql_total, (list(CASOS_CONTROL_TOTAL.keys()),))
        rows_total = cur.fetchall()

    encontrados_item  = {(r['despacho_id'], r['item_id']): r for r in rows_item}
    encontrados_total = {r['despacho_id']: r for r in rows_total}

    for desp, (item, esperado) in sorted(CASOS_CONTROL_ITEM.items()):
        r = encontrados_item.get((desp, item))
        if r is None:
            log.info(f'  -- {desp} item={item}: no encontrado en DB')
            continue
        real = float(r['flete_dolar_item'])
        diff = abs(real - esperado)
        marca = '✅' if diff < 0.10 else '⚠️'
        log.info(
            f'  {marca} {desp} item={item}: '
            f'esperado={esperado:.2f}  db={real:.4f}  diff={diff:.4f}  '
            f'pase={float(r["paseflete"]):.6f}  fuente={r["paseflete_fuente"]}  '
            f'audit={r["audit_status"]}'
        )

    for desp, esperado in sorted(CASOS_CONTROL_TOTAL.items()):
        r = encontrados_total.get(desp)
        if r is None:
            log.info(f'  -- {desp} (total): no encontrado en DB')
            continue
        real = float(r['flete_total'])
        diff = abs(real - esperado)
        marca = '✅' if diff < 0.10 else '⚠️'
        log.info(
            f'  {marca} {desp} (total {len([x for x in rows_item if x["despacho_id"]==desp])} items): '
            f'esperado={esperado:.2f}  db={real:.4f}  diff={diff:.4f}  '
            f'fuente={r["paseflete_fuente"]}  audit={r["audit_status"]}'
        )


def validar_casos_control_psql() -> None:
    """
    Variante de validar_casos_control que funciona sin psycopg2,
    ejecutando queries via psql -c y parseando la salida TSV.
    """
    import subprocess

    log.info('\n── Validación casos de control (via psql) ──')
    psql = _psql_cmd()
    env  = dict(os.environ)

    todos_desps = list(CASOS_CONTROL_ITEM.keys()) + list(CASOS_CONTROL_TOTAL.keys())
    lista_desps = "'" + "','".join(todos_desps) + "'"

    sql_item = (
        f"SELECT despacho_id, item_id, flete_dolar_item, paseflete, "
        f"paseflete_fuente, audit_status "
        f"FROM importacion_item_calculos "
        f"WHERE despacho_id IN ({lista_desps}) "
        f"ORDER BY despacho_id, item_id;"
    )
    sql_total = (
        f"SELECT despacho_id, SUM(flete_dolar_item), "
        f"MIN(paseflete_fuente), MIN(audit_status) "
        f"FROM importacion_item_calculos "
        f"WHERE despacho_id IN ({lista_desps}) "
        f"GROUP BY despacho_id;"
    )

    def run_query(sql: str) -> list[list[str]]:
        # Pasamos el SQL por stdin (psql -f -) con opciones de formato inline
        # para que funcione tanto con psql local como con docker exec -i.
        # Las opciones \t (tuples only) y \pset format unaligned/fieldsep van
        # como meta-comandos al inicio del script.
        script = f"\\t\n\\pset format unaligned\n\\pset fieldsep '\\t'\n{sql}\n"
        r = subprocess.run(
            psql + ['-f', '-'],
            input=script,
            capture_output=True, text=True, env=env,
        )
        if r.returncode != 0:
            log.warning(f'psql query falló: {r.stderr[:200]}')
            return []
        return [line.split('\t') for line in r.stdout.splitlines() if line.strip()]

    rows_item  = run_query(sql_item)
    rows_total = run_query(sql_total)

    # Casos por item
    encontrados_item = {(r[0].strip(), r[1].strip()): r for r in rows_item if len(r) >= 6}
    for desp, (item, esperado) in sorted(CASOS_CONTROL_ITEM.items()):
        r = encontrados_item.get((desp, item))
        if r is None:
            log.info(f'  -- {desp} item={item}: no encontrado en DB')
            continue
        real = float(r[2])
        diff = abs(real - esperado)
        marca = '✅' if diff < 0.10 else '⚠️'
        log.info(
            f'  {marca} {desp} item={item}: '
            f'esperado={esperado:.2f}  db={real:.4f}  diff={diff:.4f}  '
            f'pase={float(r[3]):.6f}  fuente={r[4].strip()}  audit={r[5].strip()}'
        )

    # Casos por total
    encontrados_total = {r[0].strip(): r for r in rows_total if len(r) >= 4}
    for desp, esperado in sorted(CASOS_CONTROL_TOTAL.items()):
        r = encontrados_total.get(desp)
        if r is None:
            log.info(f'  -- {desp} (total): no encontrado en DB')
            continue
        real = float(r[1])
        diff = abs(real - esperado)
        marca = '✅' if diff < 0.10 else '⚠️'
        log.info(
            f'  {marca} {desp} (total): '
            f'esperado={esperado:.2f}  db={real:.4f}  diff={diff:.4f}  '
            f'fuente={r[2].strip()}  audit={r[3].strip()}'
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main

def main():
    parser = argparse.ArgumentParser(
        description='Carga flete/seguro por ítem en importacion_item_calculos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--anio', type=int, required=True, help='Año a procesar (ej: 2026)')
    parser.add_argument('--mes', type=int, default=None,
                        help='Mes a procesar (1-12). Sin este arg, procesa el año completo.')
    parser.add_argument('--audit-csv', type=Path, default=None,
                        help='CSV de auditoría generado por auditar_pases_legacy.py')
    parser.add_argument('--data-dir', type=Path,
                        default=REPO_ROOT / 'data',
                        help='Directorio raíz de datos (default: <repo>/data)')
    parser.add_argument('--lookup', type=Path,
                        default=REPO_ROOT / 'data' / 'catalogos' / 'pase_legacy_cabi22_26.tsv.gz',
                        help='Archivo lookup pase_legacy_cabi22_26.tsv.gz')
    parser.add_argument('--dry-run', action='store_true',
                        help='No escribe en DB; muestra resumen y muestra')
    parser.add_argument('--validar', action='store_true',
                        help='Después de cargar, validar casos de control contra DB')
    args = parser.parse_args()

    # Lookup legacy
    log.info(f'Cargando lookup: {args.lookup}')
    lookup = calc.cargar_lookup_legacy(args.lookup)
    log.info(f'  {len(lookup):,} entradas en lookup')

    # Audit CSV
    audit_map = cargar_audit_csv(args.audit_csv)

    # Descubrir batches
    batches = descubrir_batches(args.data_dir, args.anio, args.mes)
    if not batches:
        log.warning(f'No se encontraron batches para anio={args.anio} mes={args.mes}')
        return

    log.info(f'Batches encontrados: {len(batches)}')
    for nombre, path in batches:
        log.info(f'  {nombre} → {path.relative_to(REPO_ROOT)}')

    # Conexión DB
    conn = None
    if not args.dry_run:
        conn = get_conn()
        if conn is not None:
            log.info('Conectado a PostgreSQL (psycopg2)')
        else:
            log.info('psycopg2 no disponible — se usará psql COPY como fallback')

    # Procesar y cargar
    total_filas = 0
    total_despachos = set()
    errores = []

    for batch_nombre, batch_dir in batches:
        log.info(f'\nProcesando {batch_nombre}...')
        try:
            filas = procesar_batch(batch_nombre, batch_dir, lookup, audit_map)
        except Exception as e:
            log.error(f'  ERROR en {batch_nombre}: {e}')
            errores.append((batch_nombre, str(e)))
            continue

        if not filas:
            log.info(f'  Sin filas para {batch_nombre}')
            continue

        desps = {f['despacho_id'] for f in filas}
        total_despachos |= desps

        n = cargar_en_db(conn, filas, args.dry_run)
        total_filas += n

        # Distribución de fuentes de pase
        from collections import Counter
        fuentes = Counter(f['paseflete_fuente'] for f in filas)
        statuses = Counter(f['audit_status'] for f in filas)
        log.info(f'  {n:,} items de {len(desps):,} despachos')
        log.info(f'  pase_fuente: { dict(fuentes) }')
        log.info(f'  audit:       { dict(statuses) }')

        if args.dry_run and filas:
            # Mostrar muestra de 3 filas en dry-run
            for f in filas[:3]:
                log.info(
                    f"  MUESTRA: {f['despacho_id']} item={f['item_id']} "
                    f"flete={f['flete_dolar_item']:.4f} pase={f['paseflete']:.6f} "
                    f"fuente={f['paseflete_fuente']} audit={f['audit_status']}"
                )

    # Resumen final
    log.info('\n' + '='*60)
    log.info('RESUMEN DE CARGA')
    log.info('='*60)
    log.info(f'Año/mes:          {args.anio}/{args.mes or "todos"}')
    log.info(f'Batches:          {len(batches)}')
    log.info(f'Despachos únicos: {len(total_despachos):,}')
    log.info(f'Items cargados:   {total_filas:,}')
    if errores:
        log.warning(f'Errores:          {len(errores)}')
        for nombre, msg in errores:
            log.warning(f'  {nombre}: {msg}')
    if args.dry_run:
        log.info('(DRY-RUN: ningún dato fue escrito en la DB)')
    log.info('='*60)

    # Validación post-carga (solo en carga real, no en dry-run)
    if args.validar:
        if args.dry_run:
            log.info('--validar omitido en dry-run (no hay datos en DB)')
        elif conn is not None:
            validar_casos_control(conn)
        else:
            validar_casos_control_psql()

    if conn:
        conn.close()


if __name__ == '__main__':
    main()
