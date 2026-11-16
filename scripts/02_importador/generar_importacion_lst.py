#!/usr/bin/env python3
"""
ETL para archivos impo_YYYYMM.lst (AFIP OneDrive).

Formato fuente: apostrophe-separated, 16 campos por línea.
Campos: ADU|DESPACHO|NUM_ITEM|FECHA|NOMBRE|M|UN|CANT|FOB_DLR|FOB_TOT|DIV|PAI|PAI|POS_NCM|COD|MONTO

Tabla destino: importacion_obligaciones (concepto + obligacion mapeados desde COD).
Conceptos ya cargados desde zRA (010/P, 010/G, 010/F, 010/X, 056/G parcial):
se omiten CODs 010 y 866 para no duplicar.

Mapeo COD → (concepto, obligacion):
  011 → (047, P)   estadística pagada
  851 → (047, G)   estadística garantía
  415 → (056, P)   IVA pagado
  852 → (056, G)   IVA garantía
  422 → (422, P)   IVA adicional inscripto
  854 → (422, G)   IVA adicional garantía
  424 → (424, P)   ganancias
  856 → (424, G)   ganancias garantía
  500 → (500, P)   arancel SIM
  429-472 → (IIBB, P)  IIBB todas provincias, AGREGADO por item

Uso:
  python3 generar_importacion_lst.py -i impo_202501.lst -o obligaciones_lst_202501.sql -m 202501
"""

import sys
import argparse
from pathlib import Path
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime

# CODs que ya están en DB desde zRA — se saltan
SKIP_CODS = {'010', '866'}

# CODs IIBB por provincia (429 Buenos Aires ... 472 Tucumán)
IIBB_CODS = {str(c) for c in range(429, 473)}

# Mapeo directo COD → (concepto, obligacion)
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


def pad_item(raw: str) -> str:
    """Convierte "3" → "0003" (4 dígitos, cero-padded)."""
    try:
        return str(int(raw)).zfill(4)
    except ValueError:
        return raw.strip().zfill(4)


def to_decimal(s: str) -> Decimal | None:
    try:
        return Decimal(s.strip())
    except (InvalidOperation, ValueError):
        return None


def procesar(archivo_entrada: Path, archivo_salida: Path, mes: str | None) -> None:
    print(f"Leyendo: {archivo_entrada}")

    # key: (despacho_id, item_id) → monto acumulado IIBB
    iibb: defaultdict[tuple[str, str], Decimal] = defaultdict(Decimal)

    # registros para conceptos directos
    # key: (despacho_id, item_id, concepto, obligacion) → monto
    directos: dict[tuple[str, str, str, str], Decimal] = {}

    errores = 0
    total = 0

    with open(archivo_entrada, 'r', encoding='latin-1', errors='replace') as f:
        for lineno, linea in enumerate(f, 1):
            linea = linea.rstrip('\n')
            if not linea or "'" not in linea:
                continue

            partes = linea.split("'")
            if len(partes) < 16:
                continue

            total += 1
            cod = partes[14].strip()

            if cod in SKIP_CODS:
                continue

            if cod not in COD_MAP and cod not in IIBB_CODS:
                continue

            despacho_id = partes[1].strip()
            item_raw    = partes[2].strip()
            monto_str   = partes[15].strip()

            if not despacho_id or not item_raw:
                errores += 1
                continue

            monto = to_decimal(monto_str)
            if monto is None:
                errores += 1
                continue

            item_id = pad_item(item_raw)

            if cod in IIBB_CODS:
                iibb[(despacho_id, item_id)] += monto
            else:
                concepto, obligacion = COD_MAP[cod]
                key = (despacho_id, item_id, concepto, obligacion)
                # Si hay duplicado en el mismo archivo, sumar (no debería ocurrir)
                directos[key] = directos.get(key, Decimal(0)) + monto

    # Combinar directos + IIBB en una lista unificada
    # row: (despacho_id, item_id, concepto, obligacion, monto)
    filas: list[tuple[str, str, str, str, Decimal]] = []

    for (despacho_id, item_id, concepto, obligacion), monto in directos.items():
        filas.append((despacho_id, item_id, concepto, obligacion, monto))

    for (despacho_id, item_id), monto in iibb.items():
        filas.append((despacho_id, item_id, 'IIBB', 'P', monto))

    validos = len(filas)
    print(f"  Líneas leídas: {total:,} | registros a insertar: {validos:,} | errores: {errores:,}")

    with open(archivo_salida, 'w', encoding='utf-8') as f:
        f.write("-- =====================================================\n")
        f.write("-- IMPORTACION OBLIGACIONES LST — CARGA DESDE impo_*.lst\n")
        f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if mes:
            f.write(f"-- Periodo: {mes}\n")
        f.write(f"-- Registros: {validos:,}\n")
        f.write("-- Conceptos: 047(estadística), 056(IVA), 422(IVA adic), 424(ganancias), IIBB, 500(arancel SIM)\n")
        f.write("-- CODs omitidos: 010, 866 (ya cargados desde zRA)\n")
        f.write("-- =====================================================\n\n")

        f.write("CREATE TEMPORARY TABLE staging_obl_lst (\n")
        f.write("    despacho_id  VARCHAR(16),\n")
        f.write("    item_id      VARCHAR(10),\n")
        f.write("    concepto     VARCHAR(10),\n")
        f.write("    obligacion   VARCHAR(10),\n")
        f.write("    monto        DECIMAL(18,2)\n")
        f.write(");\n\n")

        f.write("COPY staging_obl_lst (despacho_id, item_id, concepto, obligacion, monto)\n")
        f.write("FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N');\n")

        for despacho_id, item_id, concepto, obligacion, monto in filas:
            f.write(f"{despacho_id}\t{item_id}\t{concepto}\t{obligacion}\t{monto}\n")

        f.write("\\.\n\n")

        # Fechas de inicio/fin para partition pruning (el mes cubre todo el mes YYYYMM)
        if mes and len(mes) == 6:
            yyyy, mm = mes[:4], mes[4:]
            mm_next = str(int(mm) % 12 + 1).zfill(2)
            yyyy_next = yyyy if int(mm) < 12 else str(int(yyyy) + 1)
            fecha_desde = f"{yyyy}-{mm}-01"
            fecha_hasta = f"{yyyy_next}-{mm_next}-01"
        else:
            fecha_desde = "1900-01-01"
            fecha_hasta = "2100-01-01"

        f.write("-- Insertar con JOIN acotado por mes (partition pruning en importacion_items)\n")
        f.write("-- ON CONFLICT DO UPDATE para idempotencia\n")
        f.write("INSERT INTO importacion_obligaciones\n")
        f.write("    (despacho_id, fecha_oficializacion, item_id, concepto, obligacion, monto)\n")
        f.write("SELECT\n")
        f.write("    s.despacho_id,\n")
        f.write("    i.fecha_oficializacion,\n")
        f.write("    s.item_id,\n")
        f.write("    s.concepto,\n")
        f.write("    s.obligacion,\n")
        f.write("    s.monto\n")
        f.write("FROM staging_obl_lst s\n")
        f.write("INNER JOIN importacion_items i\n")
        f.write("    ON i.despacho_id = s.despacho_id\n")
        f.write("   AND i.item_id     = s.item_id\n")
        f.write(f"   AND i.fecha_oficializacion >= '{fecha_desde}'\n")
        f.write(f"   AND i.fecha_oficializacion <  '{fecha_hasta}'\n")
        f.write("ON CONFLICT (despacho_id, fecha_oficializacion, item_id, concepto, obligacion)\n")
        f.write("    DO UPDATE SET monto = EXCLUDED.monto;\n\n")


    print(f"  SQL generado: {archivo_salida}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Genera SQL desde impo_YYYYMM.lst (AFIP OneDrive)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 generar_importacion_lst.py -i impo_202501.lst -o sql/obl_lst_202501.sql -m 202501
        """,
    )
    parser.add_argument('-i', '--input',  required=True, type=Path)
    parser.add_argument('-o', '--output', required=True, type=Path)
    parser.add_argument('-m', '--mes',    type=str, help='YYYYMM (para documentación)')
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: no se encuentra {args.input}", file=sys.stderr)
        sys.exit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    procesar(args.input, args.output, args.mes)


if __name__ == '__main__':
    main()
