#!/usr/bin/env python3
"""
calcular_item_calculos.py
=========================
Replica la lógica de calculosimpo.sh + cargaimpo.sh para calcular
flete_dolar_item y seguro_dolar_item por ítem de importación.

Fórmula central (cargaimpo.sh):
    flete_dolar_item = (fletedolar / montofob) * sum_fobdivisa_item

Donde:
    fletedolar  = flete_monto * paseflete   (cabecera del despacho)
    montofob    = fob_monto (col 8 de zR1, en divisa del despacho)
    sum_fobdivisa_item = SUM(fob_divisa) de todos los subitems del ítem

Fuente de PASEFLETE:
    1. Lookup en tabla legacy cabi{YY} (data/catalogos/pase_legacy_cabi22_26.tsv.gz)
       — fuente autoritativa, refleja lo que AFIP proveyó en el r1 completo
    2. Fallback: tabla pase derivada de pasefob de mercado (para despachos
       no cubiertos por el lookup legacy)

Uso:
    python3 calcular_item_calculos.py DIR_MES [DIR_MES2 ...] [--validate] [--output resultados.csv]
    python3 calcular_item_calculos.py /path/to/202601ImpoQ1 /path/to/202601ImpoQ2 --validate

Los DIR_MES deben contener zR1.txt, zR5.txt y (opcionalmente) zR9.txt.

Lookup legacy:
    data/catalogos/pase_legacy_cabi22_26.tsv.gz
    Generado por: ssh root@te-sys.com.ar "mysql asisa -e SELECT DESTINACION,PASEFLETE,PASESEGURO FROM cabi26..."
    Cubre: cabi22-cabi26 (~2.6M filas, excluye DOL/DOL triviales)
"""

import sys
import csv
import gzip
import argparse
import logging
from pathlib import Path
from collections import defaultdict
from typing import Optional

# Ruta por defecto del lookup legacy (relativa al repo Tesys-data)
_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_LOOKUP = _SCRIPT_DIR.parent.parent / 'data' / 'catalogos' / 'pase_legacy_cabi22_26.tsv.gz'

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Casos de control para validación
# Formato: despacho_id → {item_id → flete_dolar esperado}
CASOS_CONTROL = {
    '26001IC04001395N': {'0001': 880.20},    # DOL/060, PASEFLETE=1.1736 en legacy ✓
    '26001IC04002643K': {'0001': 250.00},    # DOL/060, PASEFLETE=1.0 en legacy ⚠ (limitación)
    '26258ZFET000002P': {'0001': 15.39},     # DOL/PES, cruzado
    '26001IC04140334K': None,                # 060/060, target=200 total (2 ítems)
    '26001IC04134119Y': None,                # PES/PES, target ~6906.76 total
}


# ─────────────────────────────────────────────────────────────────────────────
# Lookup legacy (cabi22-cabi26)

def cargar_lookup_legacy(path: Optional[Path] = None) -> dict:
    """
    Carga el lookup de PASEFLETE/PASESEGURO desde la exportación de cabi{YY}.

    Formato TSV (tab-separated, sin header) generado por extraer_pase_legacy.sh:
        DESTINACION  PASEFLETE  PASESEGURO  MONEDAFOB  MONEDAFLETE  MONEDASEGURO

    Solo se leen las columnas 0-2; las columnas 3-5 (monedas) se ignoran.
    Retorna dict[despacho_id] = (paseflete, paseseguro).
    Si el archivo no existe, retorna {} y avisa.
    """
    lookup_path = path or _DEFAULT_LOOKUP
    if not lookup_path.exists():
        log.warning(f'Lookup legacy no encontrado: {lookup_path}')
        log.warning('  Generarlo con: scripts/00_catalogos/extraer_pase_legacy.sh')
        log.warning('  Sin lookup: usa tasas de mercado (menos preciso para algunos casos)')
        return {}

    opener = gzip.open if str(lookup_path).endswith('.gz') else open
    lookup = {}
    n = 0
    with opener(lookup_path, 'rt', encoding='utf-8') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            desp = parts[0].strip()
            try:
                pf = float(parts[1])
                ps = float(parts[2])
            except ValueError:
                continue
            lookup[desp] = (pf, ps)
            n += 1

    log.info(f'Lookup legacy cargado: {n:,} despachos desde {lookup_path.name}')
    return lookup


# ─────────────────────────────────────────────────────────────────────────────
# Parseo de archivos

def parse_pipe_line(line: str) -> list[str]:
    """Parsea una línea delimitada por | removiendo comillas."""
    campos = line.rstrip('\n').split('|')
    return [c.strip().strip('"') for c in campos]


def convertir_fecha(s: str) -> Optional[str]:
    """DD/MM/YY → YYYY-MM-DD"""
    if not s:
        return None
    parts = s.split('/')
    if len(parts) != 3:
        return None
    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
    y += 2000 if y <= 30 else 1900
    return f'{y:04d}-{m:02d}-{d:02d}'


def to_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s) if s else default
    except ValueError:
        return default


def parse_zR1(path: Path) -> dict:
    """
    Parsea zR1.txt → dict[despacho_id] = cabeitmp row.

    Columnas (índice 0-based):
      0  despacho_id
      1  fecha_oficializacion (DD/MM/YY)
      2  cuit_importador
      3  estado_declaracion
      4  condicion_venta
      5  fob_divisa
      6  flete_divisa
      7  seguro_divisa
      8  fob_monto         (en fob_divisa)
      9  flete_monto       (en flete_divisa)
      10 seguro_monto      (en seguro_divisa)
      11 medio
      12 cantidad_bultos
      13 peso_bruto
      14 matricula
      15 titulo_transporte
    """
    cabe = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            c = parse_pipe_line(linea)
            if len(c) < 14:
                continue
            desp = c[0]
            if not desp or len(desp) != 16:
                continue
            cabe[desp] = {
                'despacho_id':        desp,
                'fecha':              convertir_fecha(c[1]),
                'fob_divisa':         c[5],
                'flete_divisa':       c[6],
                'seguro_divisa':      c[7],
                'fob_monto':          to_float(c[8]),
                'flete_monto':        to_float(c[9]),
                'seguro_monto':       to_float(c[10]),
            }
    return cabe


def parse_zR5(path: Path) -> dict:
    """
    Parsea zR5.txt → dict[(despacho_id, item_id)] = item row.

    Columnas:
      0  despacho_id
      1  item_id
      2  fecha_oficializacion
      3  posicion_sim
      4  cod_procedencia
      5  cod_origen
      6  cod_unidad
      7  cantidad_unidades
      8  kg_netos
      9  fob_dolar   (en USD)
      10 fob_divisa  (en moneda del despacho)
      11 estado_mercaderia
    """
    items = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            c = parse_pipe_line(linea)
            if len(c) < 11:
                continue
            desp, item = c[0], c[1]
            if not desp or len(desp) != 16:
                continue
            key = (desp, item)
            items[key] = {
                'despacho_id':      desp,
                'item_id':          item,
                'fob_dolar':        to_float(c[9]),
                'fob_divisa_item':  to_float(c[10]),
            }
    return items


def parse_zR9(path: Path) -> dict:
    """
    Parsea zR9.txt → dict[(despacho_id, item_id, subitem_id)] = subitem row.

    Columnas:
      0   despacho_id
      1   item_id
      2   subitem_id
      3   sufijos  ← puede contener '|' embebidos que rompen el split simple
      -2  cantidad_subitem   (siempre penúltima columna)
      -1  fob_divisa_subitem (siempre última columna, en moneda del despacho)

    Se usan índices desde el final para evitar el desplazamiento por '|' en sufijos.
    """
    subitems = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            c = parse_pipe_line(linea)
            if len(c) < 6:
                continue
            desp, item, sub = c[0], c[1], c[2]
            if not desp or len(desp) != 16:
                continue
            key = (desp, item, sub)
            subitems[key] = {
                'despacho_id':        desp,
                'item_id':            item,
                'subitem_id':         sub,
                'cantidad':           to_float(c[-2]),   # penúltima siempre
                'fob_divisa_subitem': to_float(c[-1]),   # última siempre
            }
    return subitems


def cargar_directorio(directorio: Path) -> tuple[dict, dict, dict]:
    """Carga zR1, zR5 y zR9 de un directorio. Retorna (cabe, items, subitems)."""
    zR1 = directorio / 'zR1.txt'
    zR5 = directorio / 'zR5.txt'
    zR9 = directorio / 'zR9.txt'

    if not zR1.exists():
        log.error(f'No se encontró zR1.txt en {directorio}')
        return {}, {}, {}
    if not zR5.exists():
        log.error(f'No se encontró zR5.txt en {directorio}')
        return {}, {}, {}

    cabe = parse_zR1(zR1)
    items = parse_zR5(zR5)
    subitems = parse_zR9(zR9) if zR9.exists() else {}
    log.info(f'{directorio.name}: {len(cabe)} despachos, {len(items)} ítems, {len(subitems)} subitems')
    return cabe, items, subitems


# ─────────────────────────────────────────────────────────────────────────────
# Cálculos

def calcular_artitmp(items_r5: dict, subitems_r9: dict) -> dict:
    """
    Construye artitmp equivalente.
    Para cada (despacho, item): fob_dolar y fob_divisa_sum provienen de:
      - Si hay subitems reales (subitem_id != '0000' y fob_divisa > 0): los subitems
      - Si no: los datos del ítem de zR5 directamente

    Retorna dict[(despacho_id, item_id)] = {fob_dolar, fob_divisa_item, fuente}
    """
    # Agrupar subitems por (despacho, item)
    subs_por_item = defaultdict(list)
    for (desp, item, sub), row in subitems_r9.items():
        if sub != '0000' and row['fob_divisa_subitem'] > 0:
            subs_por_item[(desp, item)].append(row)

    artitmp = {}
    for (desp, item), r5 in items_r5.items():
        subs = subs_por_item.get((desp, item), [])
        if subs:
            # Subitem real: fob_divisa = SUM(fob_divisa_subitem), fob_dolar se calculará después
            fob_divisa_sum = sum(s['fob_divisa_subitem'] for s in subs)
            artitmp[(desp, item)] = {
                'despacho_id':   desp,
                'item_id':       item,
                'fob_dolar':     r5['fob_dolar'],   # del item zR5 (USD)
                'fob_divisa':    fob_divisa_sum,     # suma subitems (en divisa despacho)
                'fuente':        'zR9',
            }
        else:
            artitmp[(desp, item)] = {
                'despacho_id':   desp,
                'item_id':       item,
                'fob_dolar':     r5['fob_dolar'],
                'fob_divisa':    r5['fob_divisa_item'],
                'fuente':        'zR5',
            }
    return artitmp


def calcular_cabeitmp(cabeitmp_base: dict, artitmp: dict) -> dict:
    """
    Agrega a cabeitmp:
    - depositario = MAX(item_id como entero) por despacho
    - pasefob     = SUM(fob_dolar) / SUM(fob_divisa), o 1 si fob_divisa='DOL'
    - sum_fob_dolar
    - sum_fob_divisa
    """
    # Agrupar artitmp por despacho
    por_despacho = defaultdict(list)
    for (desp, item), row in artitmp.items():
        por_despacho[desp].append(row)

    cabe = {}
    for desp, base in cabeitmp_base.items():
        rows = por_despacho.get(desp, [])
        # depositario = MAX item_id numérico
        if rows:
            try:
                depositario = max(int(r['item_id']) for r in rows)
            except (ValueError, TypeError):
                depositario = len(rows)
        else:
            depositario = 1

        sum_fob_dolar = sum(r['fob_dolar'] for r in rows)
        sum_fob_divisa = sum(r['fob_divisa'] for r in rows)

        if base['fob_divisa'] == 'DOL' or sum_fob_divisa == 0:
            pasefob = 1.0
        else:
            pasefob = sum_fob_dolar / sum_fob_divisa

        cabe[desp] = {
            **base,
            'depositario':    depositario,
            'sum_fob_dolar':  sum_fob_dolar,
            'sum_fob_divisa': sum_fob_divisa,
            'pasefob':        pasefob,
            'paseflete':      0.0,          # se calcula después
            'paseseguro':     0.0,
            'paseflete_fuente':  'pending',
            'paseseguro_fuente': 'pending',
            'fletedolar':     0.0,
            'segurodolar':    0.0,
        }
    return cabe


def construir_pase(cabe: dict) -> dict:
    """
    Tabla pase: {(fecha, moneda) → pasefob_rate}
    = SUM(fob_dolar) / SUM(fob_divisa) agrupado por (fecha_oficializacion, fob_divisa)
    donde fob_divisa != 'DOL'.

    Replica la tabla `pase` del sistema legacy que se usa para resolver paseflete.
    """
    acum = defaultdict(lambda: {'sum_dolar': 0.0, 'sum_divisa': 0.0})
    for row in cabe.values():
        if row['fob_divisa'] == 'DOL':
            continue
        if row['sum_fob_divisa'] == 0:
            continue
        key = (row['fecha'], row['fob_divisa'])
        acum[key]['sum_dolar'] += row['sum_fob_dolar']
        acum[key]['sum_divisa'] += row['sum_fob_divisa']

    pase = {}
    for key, v in acum.items():
        if v['sum_divisa'] > 0:
            pase[key] = v['sum_dolar'] / v['sum_divisa']
    return pase


def asignar_paseflete(cabe: dict, pase: dict, lookup: dict) -> None:
    """
    Asigna paseflete y paseseguro a cada despacho en cabe (in place).

    Regla de prioridad:
    1. Lookup legacy (cabi{YY}.PASEFLETE) — fuente autoritativa del sistema viejo.
       Refleja el valor pre-calculado por AFIP en el archivo r1 completo.
    2. Pase table por (fecha, monedaflete) — tasa de mercado derivada de FOB.
    3. Si monedaflete = 'DOL' → 1.
    4. Si monedaflete = monedafob → usar pasefob del despacho.
    5. Sin dato → usar pasefob como mejor aproximación.
    """
    n_lookup = 0
    n_pase = 0
    n_dol = 0
    n_fallback = 0

    for row in cabe.values():
        desp = row['despacho_id']

        # ── Paso 1: lookup legacy ───────────────────────────────────────────
        if desp in lookup:
            pf, ps = lookup[desp]
            row['paseflete']  = pf
            row['paseseguro'] = ps
            row['paseflete_fuente']  = 'legacy'
            row['paseseguro_fuente'] = 'legacy'
            n_lookup += 1
        else:
            # ── Paso 2-5: derivar de datos propios ─────────────────────────
            for campo_divisa, campo_pase, campo_fuente in [
                ('flete_divisa',  'paseflete',  'paseflete_fuente'),
                ('seguro_divisa', 'paseseguro', 'paseseguro_fuente'),
            ]:
                divisa = row[campo_divisa]
                pase_key = (row['fecha'], divisa)

                if divisa == 'DOL':
                    row[campo_pase]   = 1.0
                    row[campo_fuente] = 'dol_trivial'
                    n_dol += 1
                elif pase_key in pase:
                    row[campo_pase]   = pase[pase_key]
                    row[campo_fuente] = 'pase_mercado'
                    n_pase += 1
                elif divisa == row['fob_divisa']:
                    row[campo_pase]   = row['pasefob']
                    row[campo_fuente] = 'pasefob_fallback'
                    n_fallback += 1
                else:
                    row[campo_pase]   = row['pasefob']
                    row[campo_fuente] = 'pasefob_approx'
                    n_fallback += 1
                    log.debug(f"Sin tasa: {desp} {campo_divisa}={divisa}, approx={row['pasefob']:.6f}")

        row['fletedolar'] = row['flete_monto'] * row['paseflete']
        row['segurodolar'] = row['seguro_monto'] * row['paseseguro']

    total = len(cabe)
    log.info(f'paseflete asignado: {n_lookup:,} legacy + {n_pase:,} mercado + '
             f'{n_dol:,} DOL + {n_fallback:,} fallback (de {total:,} despachos)')


def calcular_flete_item(artitmp: dict, cabe: dict) -> list[dict]:
    """
    Calcula flete_dolar_item y seguro_dolar_item por ítem.

    Fórmula (cargaimpo.sh):
        flete_dolar_item = (fletedolar / montofob) * sum_fobdivisa_item

    Donde montofob = fob_monto del despacho (en divisa del despacho).
    """
    resultados = []
    for (desp, item), row in sorted(artitmp.items()):
        cab = cabe.get(desp)
        if cab is None:
            continue

        fob_monto = cab['fob_monto']       # en divisa del despacho
        fletedolar = cab['fletedolar']
        segurodolar = cab['segurodolar']
        fob_div_item = row['fob_divisa']   # fob del ítem en divisa del despacho

        if fob_monto > 0:
            flete_item = (fletedolar / fob_monto) * fob_div_item
            seguro_item = (segurodolar / fob_monto) * fob_div_item
        else:
            flete_item = 0.0
            seguro_item = 0.0

        resultados.append({
            'despacho_id':     desp,
            'fecha':           cab['fecha'],
            'item_id':         item,
            'fob_divisa_desp': cab['fob_divisa'],
            'flete_divisa':    cab['flete_divisa'],
            'fob_monto':       fob_monto,
            'fob_dolar_item':  row['fob_dolar'],
            'fob_divisa_item': fob_div_item,
            'pasefob':         round(cab['pasefob'], 8),
            'paseflete':       round(cab['paseflete'], 8),
            'paseseguro':      round(cab['paseseguro'], 8),
            'fletedolar':      round(fletedolar, 6),
            'segurodolar':     round(segurodolar, 6),
            'flete_dolar_item':  round(flete_item, 6),
            'seguro_dolar_item': round(seguro_item, 6),
            'fuente_artitmp':  row['fuente'],
            'fuente_pase':     cab.get('paseflete_fuente', '?'),
        })
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Validación

def validar(resultados: list[dict]) -> None:
    """Imprime tabla de validación contra casos de control."""
    por_desp_item = {(r['despacho_id'], r['item_id']): r for r in resultados}

    print('\n' + '=' * 80)
    print('VALIDACIÓN CONTRA SISTEMA LEGACY')
    print('=' * 80)
    print(f"{'Despacho':<22} {'Item':<6} {'Legacy':>9} {'ETL':>9} {'Diff':>9} {'Estado':<12} {'Nota'}")
    print('-' * 80)

    # Objetivos para totales de despacho (en lugar de item individual)
    totales_esperados = {
        '26001IC04134119Y': 6906.76,   # total aprox (4 ítems, PES/PES)
        '26001IC04140334K': 200.00,    # total despacho (060/060, 2 ítems)
    }

    for desp, items_esperados in sorted(CASOS_CONTROL.items()):
        if items_esperados is None:
            # Mostrar total del despacho
            total = sum(r['flete_dolar_item'] for r in resultados if r['despacho_id'] == desp)
            esperado = totales_esperados.get(desp, 0)
            if total > 0 and esperado > 0:
                diff = total - esperado
                pct = abs(diff)/esperado*100
                estado = '✅ OK' if pct < 1.0 else ('⚠ ~OK' if pct < 5.0 else '❌ DIFF')
                nota = f'{pct:.2f}% desp.total'
                print(f"{desp:<22} {'ALL':<6} {esperado:>9.3f} {total:>9.3f} {diff:>+9.3f} {estado:<12} {nota}")
            elif total > 0:
                print(f"{desp:<22} {'ALL':<6} {'aprox':>9} {total:>9.3f}")
            else:
                print(f"{desp:<22} {'ALL':<6} {'?':>9} {'NO DATA':>9}")
            continue

        for item_id, esperado in items_esperados.items():
            key = (desp, item_id)
            r = por_desp_item.get(key)
            if r is None:
                print(f"{desp:<22} {item_id:<6} {esperado:>9.2f} {'NO DATA':>9}")
                continue

            etl = r['flete_dolar_item']
            diff = etl - esperado
            pct = abs(diff) / esperado * 100 if esperado > 0 else 0

            if pct < 0.1:
                estado = '✅ OK'
                nota = ''
            elif desp == '26001IC04002643K':
                estado = '⚠ LIMITACIÓN'
                nota = 'AFIP Fleteendolares requerido'
            else:
                estado = '❌ DIFF'
                nota = f'{pct:.1f}%'

            print(f"{desp:<22} {item_id:<6} {esperado:>9.3f} {etl:>9.3f} {diff:>+9.3f} {estado:<12} {nota}")

    print('=' * 80)

    # Mostrar detalle de paseflete para casos clave
    print('\nDETALLE pase por despacho:')
    print(f"{'Despacho':<22} {'fob_div':<8} {'flt_div':<8} {'pasefob':>10} {'paseflete':>10} {'fletedolar':>12}")
    print('-' * 70)
    vistos = set()
    for r in resultados:
        d = r['despacho_id']
        if d in CASOS_CONTROL and d not in vistos:
            vistos.add(d)
            print(f"{d:<22} {r['fob_divisa_desp']:<8} {r['flete_divisa']:<8} "
                  f"{r['pasefob']:>10.6f} {r['paseflete']:>10.6f} {r['fletedolar']:>12.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# Main

def main():
    parser = argparse.ArgumentParser(
        description='Calcula flete_dolar_item replicando calculosimpo.sh + cargaimpo.sh')
    parser.add_argument('directorios', nargs='+', type=Path,
                        help='Directorios con zR1.txt, zR5.txt, zR9.txt')
    parser.add_argument('--validate', '-v', action='store_true',
                        help='Imprimir tabla de validación contra casos de control')
    parser.add_argument('--output', '-o', type=Path,
                        help='Guardar resultados en CSV (default: stdout resumido)')
    parser.add_argument('--debug', action='store_true',
                        help='Logging debug')
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Cargar todos los directorios
    cabe_total: dict = {}
    items_total: dict = {}
    subitems_total: dict = {}

    for d in args.directorios:
        if not d.is_dir():
            log.error(f'No es directorio: {d}')
            continue
        cabe_d, items_d, subs_d = cargar_directorio(d)
        cabe_total.update(cabe_d)
        items_total.update(items_d)
        subitems_total.update(subs_d)

    if not cabe_total:
        log.error('No se cargaron datos')
        sys.exit(1)

    log.info(f'Total: {len(cabe_total)} despachos, {len(items_total)} ítems, {len(subitems_total)} subitems')

    # Pipeline ETL
    log.info('Construyendo artitmp...')
    artitmp = calcular_artitmp(items_total, subitems_total)

    log.info('Calculando cabeitmp (depositario + pasefob)...')
    cabe = calcular_cabeitmp(cabe_total, artitmp)

    log.info('Construyendo tabla pase (tasa mercado por fecha+moneda)...')
    pase = construir_pase(cabe)
    log.info(f'  {len(pase)} entradas en tabla pase')

    log.info('Cargando lookup legacy (cabi22-26)...')
    lookup = cargar_lookup_legacy()

    log.info('Asignando paseflete/paseseguro...')
    asignar_paseflete(cabe, pase, lookup)

    log.info('Calculando flete_dolar_item por ítem...')
    resultados = calcular_flete_item(artitmp, cabe)
    log.info(f'  {len(resultados)} filas calculadas')

    # Salida
    if args.output:
        campos = [
            'despacho_id', 'fecha', 'item_id',
            'fob_divisa_desp', 'flete_divisa',
            'fob_monto', 'fob_dolar_item', 'fob_divisa_item',
            'pasefob', 'paseflete', 'paseseguro',
            'fletedolar', 'segurodolar',
            'flete_dolar_item', 'seguro_dolar_item',
            'fuente_artitmp', 'fuente_pase',
        ]
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            w.writerows(resultados)
        log.info(f'Resultados guardados en {args.output}')

    if args.validate:
        validar(resultados)
    elif not args.output:
        # Resumen breve
        print(f'\nProcesados: {len(cabe)} despachos, {len(resultados)} ítems')
        print('Usá --validate para ver tabla de validación o --output archivo.csv para exportar.')


if __name__ == '__main__':
    main()
