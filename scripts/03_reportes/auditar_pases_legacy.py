#!/usr/bin/env python3
"""
auditar_pases_legacy.py
=======================
Audita la calidad de los datos de flete/seguro en el sistema legacy (MySQL).

Checks:
  1. Cabecera (cabi{YY}):
     - fletedolar ≈ MONTOFLETE * PASEFLETE  (tolerancia configurable)
     - PASEFLETE no nulo ni cero si MONTOFLETE > 0
     - PASESEGURO no nulo ni cero si MONTOSEGURO > 0
     - Importes no negativos

  2. Items (r5{YY}):
     - Fleteendolares no nulo/negativo
     - Montofleteendivisa no nulo/negativo
     - FOBendolares / FOBendivisa no negativos
     - Detecta filas duplicadas por (Aduanaofic,Tipodestinacion,Numerodesp,Digitocont,Numeroitem)

  3. Cierre cabecera vs items (por despacho):
     - SUM(r5.Fleteendolares)/100  vs  cabi.fletedolar
     - Tolerancia: ±0.10 USD

  4. Status final por despacho:
     - ok_exacto        (diff == 0)
     - ok_redondeo      (diff ≤ tolerancia)
     - sospecha_dup     (tiene items duplicados en r5)
     - sospecha_pase    (PASEFLETE=0 con MONTOFLETE>0)
     - items_invalidos  (Fleteendolares null o negativo)
     - diff_real        (diff > tolerancia, sin las sospechas anteriores)
     - sin_items        (despacho sin filas en r5)
     - cabecera_negativa

Credenciales (todas por variable de entorno):
  TESYS_SSH_HOST      (default: root@te-sys.com.ar)
  TESYS_MYSQL_USER    (default: tesys_readonly)
  MYSQL_PWD           (requerida; sin default)
  TESYS_MYSQL_DB      (default: asisa)

Uso:
    export MYSQL_PWD=<password>
    python3 auditar_pases_legacy.py [--anios 26] [--output audit_26.csv]
    python3 auditar_pases_legacy.py --anios 22,23,24,25,26 --output audit_completo.csv

Opciones útiles:
    --resumen          Solo imprime resumen por status, no genera CSV
    --solo-problemas   Excluye ok_exacto del CSV (para análisis rápido)
    --tolerancia 0.05  Cambia la tolerancia de cierre (default: 0.10 USD)
"""

import csv
import gzip
import os
import subprocess
import argparse
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Tolerancia (en USD) para el cierre cabi.fletedolar vs SUM(r5.Fleteendolares)/100
TOLERANCIA_USD_DEFAULT = 0.10


# ─────────────────────────────────────────────────────────────────────────────
# Credenciales desde entorno

def get_creds() -> tuple[str, str, str, str]:
    """
    Lee credenciales del entorno. Falla explícitamente si MYSQL_PWD no está.
    Retorna (ssh_host, mysql_user, mysql_pwd, mysql_db).
    """
    ssh_host   = os.environ.get('TESYS_SSH_HOST',  'root@te-sys.com.ar')
    mysql_user = os.environ.get('TESYS_MYSQL_USER', 'tesys_readonly')
    mysql_db   = os.environ.get('TESYS_MYSQL_DB',   'asisa')
    mysql_pwd  = os.environ.get('MYSQL_PWD', '')
    if not mysql_pwd:
        raise SystemExit(
            'ERROR: MYSQL_PWD no está definida en el entorno.\n'
            '  export MYSQL_PWD=<password> y volvé a ejecutar.'
        )
    return ssh_host, mysql_user, mysql_pwd, mysql_db


# ─────────────────────────────────────────────────────────────────────────────
# Ejecución de queries via SSH

def ssh_query_gz(host: str, user: str, password: str, db: str, sql: str) -> list[list[str]]:
    """
    Ejecuta SQL en MySQL remoto via SSH, con compresión gzip en tránsito.
    Usa MYSQL_PWD como variable de entorno en el lado remoto (no aparece en ps).
    """
    cmd = (
        f"MYSQL_PWD='{password}' "
        f"mysql -u {user} {db} "
        f"--batch --skip-column-names "
        f"-e \"{sql}\" | gzip"
    )
    result = subprocess.run(
        ['ssh', '-o', 'StrictHostKeyChecking=no', host, cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace')
        log.error(f'SSH/MySQL error (rc={result.returncode}): {stderr[:300]}')
        return []
    text = gzip.decompress(result.stdout).decode('utf-8', errors='replace')
    rows = []
    for line in text.splitlines():
        if line.strip():
            rows.append(line.split('\t'))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Helpers

def to_f(s: str, default: float = 0.0) -> float:
    try:
        return float(s) if s and s not in ('NULL', '\\N', '') else default
    except ValueError:
        return default


def tipo_destinacion(despacho_id: str) -> str:
    """
    Extrae el código de tipo de destinación del despacho_id legacy.
    Formato: {anio2}{aduana3}{tipo4}{nro6}{digito1}
    Ej: '26001IC04001395N' -> 'IC04'
    """
    # anio2(0:2) + aduana(2:5) + tipo(5:9) + nro(9:15) + digito(15)
    if len(despacho_id) >= 9:
        return despacho_id[5:9]
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Extracción de datos

def extraer_cabi(host: str, user: str, password: str, db: str, anio: str) -> dict:
    """
    Extrae cabeceras de cabi{YY}.
    Retorna dict[DESTINACION] = row_dict.
    """
    tabla = f'cabi{anio}'
    log.info(f'Extrayendo {tabla}...')

    sql = (
        f"SELECT DESTINACION, DATE_FORMAT(OFICIALIZACION,'%Y-%m-%d'), "
        f"MONEDAFOB, MONEDAFLETE, MONEDASEGURO, "
        f"MONTOFLETE, MONTOSEGURO, MONTOFOB, "
        f"ROUND(PASEFLETE,8), ROUND(PASESEGURO,8), ROUND(fletedolar,6) "
        f"FROM {tabla}"
    )
    rows = ssh_query_gz(host, user, password, db, sql)
    log.info(f'  {len(rows):,} filas cabi')

    cabi = {}
    n_neg = 0
    for r in rows:
        if len(r) < 11:
            continue
        desp = r[0].strip()
        d = {
            'despacho_id':    desp,
            'fecha':          r[1].strip(),
            'monedafob':      r[2].strip(),
            'monedaflete':    r[3].strip(),
            'monedaseguro':   r[4].strip(),
            'montoflete':     to_f(r[5]),
            'montoseguro':    to_f(r[6]),
            'montofob':       to_f(r[7]),
            'paseflete':      to_f(r[8]),
            'paseseguro':     to_f(r[9]),
            'fletedolar':     to_f(r[10]),
            'tipo_dest':      tipo_destinacion(r[0].strip()),
        }
        d['cabe_negativa'] = (
            d['montoflete'] < 0 or d['montoseguro'] < 0 or d['montofob'] < 0
        )
        if d['cabe_negativa']:
            n_neg += 1
        d['pase_flete_nulo'] = (d['montoflete'] > 0 and d['paseflete'] == 0)
        d['pase_seguro_nulo'] = (d['montoseguro'] > 0 and d['paseseguro'] == 0)
        esperado = d['montoflete'] * d['paseflete']
        d['diff_cabe_flete'] = abs(d['fletedolar'] - esperado)
        cabi[desp] = d

    log.info(f'  {n_neg:,} cabeceras con importes negativos')
    return cabi


def extraer_r5_agregado(host: str, user: str, password: str, db: str, anio: str) -> dict:
    """
    Extrae de r5{YY} los datos agregados por despacho.
    Retorna dict[despacho_id_construido] = {n_rows, n_distinct, sumas, checks}.
    Nota: r5{YY}.destinacion está vacío — se construye la clave desde los
    campos componentes para que coincida con cabi{YY}.DESTINACION.
    """
    # r5 usa año completo (r52022..r52026); anio puede ser '22' o '2022'
    anio4 = anio if len(anio) == 4 else f'20{anio}'
    anio2 = anio4[-2:]
    tabla = f'r5{anio4}'
    log.info(f'Extrayendo {tabla} (agregado por despacho)...')

    sql = (
        f"SELECT "
        f"  CONCAT('{anio2}', Aduanaofic, Tipodestinacion, Numerodesp, Digitocont) AS despacho_id, "
        f"  COUNT(*) as n_rows, "
        f"  COUNT(DISTINCT CONCAT(Aduanaofic,Tipodestinacion,Numerodesp,Digitocont,Numeroitem)) as n_distinct, "
        f"  SUM(CASE WHEN Fleteendolares IS NULL THEN 1 ELSE 0 END) as n_flete_null, "
        f"  SUM(CASE WHEN Fleteendolares < 0 THEN 1 ELSE 0 END) as n_flete_neg, "
        f"  SUM(CASE WHEN Montofleteendivisa IS NULL THEN 1 ELSE 0 END) as n_mfd_null, "
        f"  SUM(CASE WHEN Montofleteendivisa < 0 THEN 1 ELSE 0 END) as n_mfd_neg, "
        f"  SUM(CASE WHEN MontoFOBendolares < 0 THEN 1 ELSE 0 END) as n_fob_neg, "
        f"  ROUND(SUM(COALESCE(Fleteendolares,0))/100.0, 6) as sum_flete_usd, "
        f"  ROUND(SUM(COALESCE(Montofleteendivisa,0))/100.0, 6) as sum_flete_div, "
        f"  ROUND(SUM(COALESCE(Montoseguroendivisa,0))/100.0, 6) as sum_seguro_div, "
        f"  ROUND(SUM(COALESCE(MontoFOBendolares,0))/100.0, 6) as sum_fob_usd, "
        f"  ROUND(SUM(COALESCE(MontoFOBendivisa,0))/100.0, 6) as sum_fob_div, "
        f"  COUNT(DISTINCT Numeroitem) as n_items "
        f"FROM {tabla} "
        f"GROUP BY despacho_id"
    )
    rows = ssh_query_gz(host, user, password, db, sql)
    log.info(f'  {len(rows):,} despachos en {tabla}')

    r5 = {}
    for r in rows:
        if len(r) < 14:
            continue
        desp = r[0].strip()
        n_rows     = int(r[1]) if r[1] not in ('NULL', '') else 0
        n_distinct = int(r[2]) if r[2] not in ('NULL', '') else 0
        r5[desp] = {
            'n_rows':          n_rows,
            'n_distinct':      n_distinct,
            'n_flete_null':    int(r[3]),
            'n_flete_neg':     int(r[4]),
            'n_mfd_null':      int(r[5]),
            'n_mfd_neg':       int(r[6]),
            'n_fob_neg':       int(r[7]),
            'sum_flete_usd':   to_f(r[8]),
            'sum_flete_div':   to_f(r[9]),
            'sum_seguro_div':  to_f(r[10]),
            'sum_fob_usd':     to_f(r[11]),
            'sum_fob_div':     to_f(r[12]),
            'n_items':         int(r[13]) if r[13] not in ('NULL', '') else 0,
            'tiene_duplicados': n_rows > n_distinct,
        }
    return r5


# ─────────────────────────────────────────────────────────────────────────────
# Clasificación y cierre

def clasificar(cabe: dict, r5_row: Optional[dict], tolerancia: float) -> dict:
    """
    Clasifica un despacho y calcula el cierre cabe vs items.
    """
    resultado = {
        'despacho_id':         cabe['despacho_id'],
        'tipo_dest':           cabe['tipo_dest'],
        'fecha':               cabe['fecha'],
        'monedafob':           cabe['monedafob'],
        'monedaflete':         cabe['monedaflete'],
        'monedaseguro':        cabe['monedaseguro'],
        'montoflete':          cabe['montoflete'],
        'montoseguro':         cabe['montoseguro'],
        'paseflete':           cabe['paseflete'],
        'paseseguro':          cabe['paseseguro'],
        'fletedolar_cabi':     cabe['fletedolar'],
        'diff_cabe_interna':   round(cabe['diff_cabe_flete'], 6),

        'n_filas_r5':          r5_row['n_rows']       if r5_row else 0,
        'n_items_dist':        r5_row['n_distinct']    if r5_row else 0,
        'n_flete_null':        r5_row['n_flete_null']  if r5_row else 0,
        'n_flete_neg':         r5_row['n_flete_neg']   if r5_row else 0,
        'n_fob_neg':           r5_row['n_fob_neg']     if r5_row else 0,
        'sum_flete_items_usd': r5_row['sum_flete_usd'] if r5_row else None,

        'diff_cabe_vs_items':  None,
        'tiene_duplicados':    r5_row['tiene_duplicados'] if r5_row else False,

        'cabe_negativa':       cabe['cabe_negativa'],
        'pase_flete_nulo':     cabe['pase_flete_nulo'],
        'pase_seguro_nulo':    cabe['pase_seguro_nulo'],

        'status': '',
    }

    diff: Optional[float] = None
    if r5_row is not None:
        diff = abs(cabe['fletedolar'] - r5_row['sum_flete_usd'])
        resultado['diff_cabe_vs_items'] = round(diff, 6)

    # Prioridad de clasificación (de más grave a menos)
    if cabe['cabe_negativa']:
        resultado['status'] = 'cabecera_negativa'
    elif cabe['pase_flete_nulo']:
        resultado['status'] = 'sospecha_pase'
    elif r5_row is None:
        resultado['status'] = 'sin_items'
    elif r5_row['tiene_duplicados']:
        resultado['status'] = 'sospecha_dup'
    elif r5_row['n_flete_null'] > 0 or r5_row['n_flete_neg'] > 0:
        resultado['status'] = 'items_invalidos'
    elif diff is None:
        resultado['status'] = 'sin_items'
    elif diff == 0.0:
        resultado['status'] = 'ok_exacto'
    elif diff <= tolerancia:
        resultado['status'] = 'ok_redondeo'
    else:
        resultado['status'] = 'diff_real'

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# Main

CAMPOS_CSV = [
    'despacho_id', 'tipo_dest', 'fecha', 'monedafob', 'monedaflete', 'monedaseguro',
    'montoflete', 'montoseguro', 'paseflete', 'paseseguro', 'fletedolar_cabi',
    'diff_cabe_interna',
    'sum_flete_items_usd', 'diff_cabe_vs_items',
    'n_filas_r5', 'n_items_dist', 'n_flete_null', 'n_flete_neg', 'n_fob_neg',
    'tiene_duplicados', 'cabe_negativa', 'pase_flete_nulo', 'pase_seguro_nulo',
    'status',
]


def imprimir_resumen(todas_filas: list[dict], tolerancia: float) -> None:
    conteo = Counter(f['status'] for f in todas_filas)
    total = len(todas_filas)

    log.info('\n' + '='*65)
    log.info('RESUMEN DE AUDITORÍA')
    log.info('='*65)
    log.info(f'Total despachos auditados: {total:,}')
    log.info(f'Tolerancia cierre:         {tolerancia} USD')
    for status, n in sorted(conteo.items(), key=lambda x: -x[1]):
        pct = n / total * 100 if total else 0
        log.info(f'  {status:<22}: {n:>8,}  ({pct:.1f}%)')
    log.info('='*65)

    # Breakdown de diff_real por tipo de destinación
    diff_reales = [f for f in todas_filas if f['status'] == 'diff_real']
    if diff_reales:
        por_tipo = Counter(f['tipo_dest'] for f in diff_reales)
        log.info(f'\ndiff_real ({len(diff_reales):,}) por tipo de destinación:')
        for tipo, n in sorted(por_tipo.items(), key=lambda x: -x[1]):
            log.info(f'  {tipo or "(vacío)":<8}: {n:,}')

        log.info(f'\nTop 10 diferencias reales (|diff| > {tolerancia} USD):')
        for f in sorted(diff_reales, key=lambda x: -(x['diff_cabe_vs_items'] or 0))[:10]:
            log.info(
                f"  {f['despacho_id']} tipo={f['tipo_dest']} "
                f"fob={f['monedafob']} flt={f['monedaflete']} seg={f['monedaseguro']} "
                f"flete={f['montoflete']:.2f} pase={f['paseflete']:.6f} "
                f"cabi={f['fletedolar_cabi']:.4f} items={f['sum_flete_items_usd']:.4f} "
                f"diff={f['diff_cabe_vs_items']:.4f}"
            )

    # Verificación casos de control conocidos.
    # Compara cabi.fletedolar (fuente autoritativa del legacy) contra el valor
    # esperado por nuestro ETL. No usa items_usd porque r52026 puede tener
    # inconsistencias propias (ej. 134119Y con DEPOSITARIO=2 almacena la mitad).
    CASOS_CONTROL = {
        '26001IC04001395N': 880.20,
        '26001IC04002643K': 250.00,
        '26001IC04134119Y': 6906.76,
        '26001IC04140334K': 200.00,
        '26258ZFET000002P': 15.39,
    }
    encontrados = {f['despacho_id']: f for f in todas_filas if f['despacho_id'] in CASOS_CONTROL}
    if encontrados:
        log.info('\nCasos de control (ETL esperado vs cabi.fletedolar):')
        for desp, esperado in sorted(CASOS_CONTROL.items()):
            f = encontrados.get(desp)
            if f:
                diff_ctrl = abs(f['fletedolar_cabi'] - esperado)
                marca = '✅' if diff_ctrl < 0.10 else '⚠️'
                log.info(
                    f'  {marca} {desp}: ETL_esperado={esperado:.2f}  '
                    f'cabi_flete={f["fletedolar_cabi"]:.4f}  '
                    f'diff={diff_ctrl:.4f}  '
                    f'r5_items={f["sum_flete_items_usd"]:.4f}  '
                    f'status={f["status"]}'
                )
            else:
                log.info(f'  -- {desp}: no encontrado en años auditados')

    # Casos FOB=DOL/FLETE=DOL pero SEGURO en moneda no-DOL y con seguro declarado.
    # Estos necesitan PASESEGURO real del lookup (no se puede asumir 1.0).
    # Se excluyen: monedaseguro vacío (sin seguro declarado), MONTOSEGURO=0.
    casos_seg_nondol = [
        f for f in todas_filas
        if f['monedafob'] == 'DOL'
        and f['monedaflete'] == 'DOL'
        and f.get('monedaseguro', '').strip() not in ('', 'DOL')
        and f['montoseguro'] > 0
    ]
    if casos_seg_nondol:
        log.info(
            f'\nCasos FOB=DOL/FLETE=DOL SEGURO≠DOL con monto>0: {len(casos_seg_nondol):,} '
            f'(requieren PASESEGURO del lookup; antes se omitían del extractor)'
        )
        for f in casos_seg_nondol[:5]:
            log.info(
                f"  {f['despacho_id']}  seg={f['monedaseguro']}  montoseguro={f['montoseguro']:.2f}  "
                f"paseseguro={f['paseseguro']:.6f}  pase_seg_nulo={f['pase_seguro_nulo']}"
            )
    else:
        log.info('\nCasos FOB=DOL/FLETE=DOL SEGURO≠DOL con monto>0: 0 (ninguno requiere corrección)')


def main():
    parser = argparse.ArgumentParser(
        description='Auditor de calidad flete/pases legacy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--anios', default='26',
        help='Años a auditar, separados por coma. Ej: 22,23,24,25,26 (default: 26)',
    )
    parser.add_argument(
        '--output', '-o', type=Path, default=Path('audit_pases.csv'),
        help='Archivo CSV de salida (default: audit_pases.csv)',
    )
    parser.add_argument(
        '--solo-problemas', action='store_true',
        help='Excluir ok_exacto del CSV (ahorra espacio; no recomendado para auditoría completa)',
    )
    parser.add_argument(
        '--resumen', action='store_true',
        help='Solo imprimir resumen por status, no generar CSV',
    )
    parser.add_argument(
        '--tolerancia', type=float, default=TOLERANCIA_USD_DEFAULT,
        help=f'Tolerancia en USD para cierre cabe vs items (default: {TOLERANCIA_USD_DEFAULT})',
    )
    args = parser.parse_args()

    host, user, pwd, db = get_creds()
    tolerancia = args.tolerancia

    anios = [a.strip().zfill(2) for a in args.anios.split(',')]
    log.info(f'Auditando años: {anios}  |  SSH: {host}  |  DB: {db}')

    todas_filas: list[dict] = []

    for anio in anios:
        log.info(f'\n── Año 20{anio} ──')
        cabi_all = extraer_cabi(host, user, pwd, db, anio)
        r5_all   = extraer_r5_agregado(host, user, pwd, db, anio)

        sin_items = set(cabi_all.keys()) - set(r5_all.keys())
        sin_cabi  = set(r5_all.keys())  - set(cabi_all.keys())
        log.info(f'  Despachos cabi sin items en r5: {len(sin_items):,}')
        log.info(f'  Items en r5 sin cabecera cabi:  {len(sin_cabi):,}')

        for desp, cabe in cabi_all.items():
            fila = clasificar(cabe, r5_all.get(desp), tolerancia)
            todas_filas.append(fila)

        log.info(f'  Total clasificadas: {len(cabi_all):,}')

    imprimir_resumen(todas_filas, tolerancia)

    if args.resumen:
        return

    filas_a_guardar = todas_filas
    if args.solo_problemas:
        filas_a_guardar = [f for f in todas_filas if f['status'] != 'ok_exacto']
        log.info(f'\nModo --solo-problemas: {len(filas_a_guardar):,} filas (excluye ok_exacto)')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS_CSV, extrasaction='ignore')
        w.writeheader()
        w.writerows(filas_a_guardar)

    log.info(f'CSV guardado: {args.output}  ({len(filas_a_guardar):,} filas)')


if __name__ == '__main__':
    main()
