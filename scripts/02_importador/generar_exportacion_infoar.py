#!/usr/bin/env python3
"""
Script para generar SQL de exportación desde archivos formato INFOAR.

El formato INFOAR se usa en datos de 2023 (Oct-Dic) y 2024 (Feb en adelante) con 4 archivos:
  - CABECERA-EXPO-*.txt   → exportacion_despachos
  - ARTICULO-EXPO-*.txt   → exportacion_items + exportacion_subitems
  - VENTAJAS-EXPO-*.txt   → exportacion_ventajas
  - LIQUIDACION-EXPO-*.txt → ignorado (no hay tabla destino)

Diferencias clave respecto al formato zR*:
  - Fechas en formato YYYY-MM-DD (no DD/MM/YY)
  - ARTICULO combina items y subitems (campo SUBITEM: 0=item, >0=subitem)
  - ARTICULO no trae FECHAOFICIALIZACION → se obtiene del CABECERA
  - Archivos 2023: tienen cabecera (primera línea = nombres de campo) y la repiten cada ~2000 filas
  - Archivos 2024: SIN cabecera (primera línea ya es dato). Auto-detectado por longitud del primer campo.

Uso con 1 directorio:
  python3 generar_exportacion_infoar.py INFOAR10-2023/ -m 202310 -o output/sql/2023/

Uso con 2 directorios (merge de 2 fuentes, ej: noviembre 2023):
  python3 generar_exportacion_infoar.py INFOAR11-2023/ INFOAR112023/ -m 202311 -o output/sql/2023/

Campos CABECERA (30 campos, separador |):
  0  DESTINACION       → despacho_id
  1  CUIT              → cuit_exportador
  2  FECHA_OFIC        → fecha_oficializacion (YYYY-MM-DD)
  3  COD_ADUANA        → codigo_aduana
  4  ESTADO            → estado_declaracion
  5  INCOTERM          → condicion_venta
  6  DIV_FOB           → fob_montoisa
  7  FOB_DIV           → fob_monto
  8  DIV_FLETE         → flete_montoisa
  9  FLETE_DIV         → flete_monto
  10 DIV_SEGURO        → seguro_montoisa
  11 SEGURO_DIV        → seguro_monto
  12 FECHAARRIBO       → ignorado
  13 VIA_TRANSPORTE    → via_medio_transporte
  14 CANT_BULTOS       → cantidad_bultos
  15 PESO_BULTOS       → peso_bultos
  16-26 fechas varias  → ignoradas (discontinuadas según Gaby)
  27 COTIZACIONDOL     → ignorado
  28 PASEFOB           → ignorado (discontinuado)
  29 PASEFLETE         → ignorado (discontinuado)
  30 PASESEGURO        → ignorado (discontinuado)

Campos ARTICULO (14 campos, separador |):
  0  DESTINACION       → despacho_id
  1  ITEM              → item_id
  2  SUBITEM           → subitem_id (0 = nivel item, >0 = subitem)
  3  POSICION_SIM      → posicion_sim
  4  CANTIDAD          → cantidad_unidades (item) / cantidad_unidades_subitem (subitem)
  5  COD_UNIDAD        → codigo_unidad
  6  DESC_UNIDAD       → ignorado
  7  PRECIO_UNIT       → ignorado
  8  MONTO_FOB_DOLAR   → monto_fob_dolar (item) / fob_dolar_subitem (subitem)
  9  KGS_NETOS         → kgs_netos
  10 ESTADO_MERC       → estado_mercaderia
  11 COD_ORIGEN        → cod_pais_origen (jurisdicción argentina: BA, SF, JU, etc.)
  12 COD_PAIS_DESTINO  → cod_pais_destino (país destino real, código numérico)
  13 DETALLE_SUFIJOS   → detalle_completo (subitems)

Campos VENTAJAS (3 campos, separador |):
  0  DESTINACION       → despacho_id
  1  ITEM              → item_id
  2  CODIGO_VENTAJA    → ventaja
"""

import sys
import csv
import argparse

csv.field_size_limit(10_000_000)  # Algunos campos ARTICULO pueden ser muy largos
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation
from collections import defaultdict


class InfoarExportacionProcessor:

    def __init__(self, mes_archivo: str, directorios: List[Path]):
        if not mes_archivo or len(mes_archivo) != 6 or not mes_archivo.isdigit():
            raise ValueError(f"mes_archivo debe ser formato YYYYMM, recibido: {mes_archivo}")
        self.mes_archivo = mes_archivo
        self.directorios = directorios

        # {despacho_id: fecha_oficializacion} - se construye al leer CABECERA
        self.despacho_fechas: Dict[str, str] = {}

        self.stats = {
            'despachos': 0,
            'items': 0,
            'subitems': 0,
            'ventajas': 0,
            'errores': []
        }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def limpiar(self, valor: str) -> Optional[str]:
        if not valor:
            return None
        v = valor.strip().strip('"')
        return v if v else None

    def decimal(self, valor: str) -> Optional[str]:
        try:
            v = valor.strip().strip('"')
            if not v:
                return None
            return str(Decimal(v))
        except (InvalidOperation, ValueError):
            return None

    def fmt(self, valor: Any) -> str:
        if valor is None or valor == '':
            return '\\N'
        # Escapar caracteres especiales de COPY text format
        v = str(valor)
        v = v.replace('\\', '\\\\')  # backslash → \\
        v = v.replace('\t', '\\t')    # tab → \t
        v = v.replace('\n', '\\n')    # newline → \n
        v = v.replace('\r', '\\r')    # carriage return → \r
        return v

    def fecha_valida(self, fecha_str: str) -> Optional[str]:
        """Acepta YYYY-MM-DD. Devuelve None si es 0000-00-00 o inválida."""
        f = fecha_str.strip().strip('"')
        if not f or f.startswith('0000'):
            return None
        try:
            datetime.strptime(f, '%Y-%m-%d')
            return f
        except ValueError:
            return None

    def encontrar_archivo(self, directorio: Path, patron: str) -> Optional[Path]:
        """Busca archivo cuyo nombre contiene el patrón (case-insensitive)."""
        for archivo in directorio.iterdir():
            if patron.lower() in archivo.name.lower() and archivo.is_file():
                return archivo
        return None

    def leer_csv(self, archivo: Path) -> Tuple[List[str], List[List[str]]]:
        """Lee archivo, auto-detectando si tiene cabecera.
        Si el primer campo de la primera fila tiene 16 caracteres (despacho_id),
        no hay cabecera y se incluye esa fila como dato.
        Devuelve (headers, filas)."""
        encoding = 'utf-8'
        try:
            with open(archivo, 'r', encoding=encoding) as f:
                f.read(1024)
        except UnicodeDecodeError:
            encoding = 'latin-1'

        with open(archivo, 'r', encoding=encoding, errors='replace') as f:
            reader = csv.reader(f, delimiter='|', quoting=csv.QUOTE_NONE, escapechar='\\')
            filas = list(reader)

        if not filas:
            return [], []

        primer_campo = filas[0][0].strip() if filas[0] else ''
        tiene_cabecera = len(primer_campo) != 16

        if tiene_cabecera:
            headers = [h.strip() for h in filas[0]]
            datos = [row for row in filas[1:] if any(c.strip() for c in row)]
        else:
            headers = []
            datos = [row for row in filas if any(c.strip() for c in row)]
        return headers, datos

    # -------------------------------------------------------------------------
    # Procesamiento CABECERA → exportacion_despachos
    # -------------------------------------------------------------------------

    def procesar_cabecera(self, directorio: Path) -> List[Dict]:
        archivo = self.encontrar_archivo(directorio, 'CABECERA')
        if not archivo:
            print(f"  ADVERTENCIA: No se encontró CABECERA en {directorio}")
            return []

        print(f"  Leyendo: {archivo.name}")
        _, filas = self.leer_csv(archivo)
        registros = []

        for i, row in enumerate(filas, 2):
            if len(row) < 16:
                self.stats['errores'].append(f"CABECERA linea {i}: solo {len(row)} campos")
                continue

            despacho_id = self.limpiar(row[0])
            if not despacho_id or len(despacho_id) != 16:
                self.stats['errores'].append(f"CABECERA linea {i}: despacho_id inválido: {row[0]}")
                continue

            fecha = self.fecha_valida(row[2])
            if not fecha:
                self.stats['errores'].append(f"CABECERA linea {i}: fecha inválida: {row[2]}")
                continue

            # Guardar para uso en ARTICULO
            self.despacho_fechas[despacho_id] = fecha

            cuit = self.limpiar(row[1])
            cod_aduana = self.limpiar(row[3])
            estado = self.limpiar(row[4])
            condicion_venta = self.limpiar(row[5])
            fob_montoisa = self.limpiar(row[6])
            fob_monto = self.decimal(row[7])
            flete_montoisa = self.limpiar(row[8])
            flete_monto = self.decimal(row[9])
            seguro_montoisa = self.limpiar(row[10])
            seguro_monto = self.decimal(row[11])
            via = self.limpiar(row[13])
            cant_bultos = self.limpiar(row[14])
            peso_bultos = self.decimal(row[15])

            registros.append({
                'despacho_id': despacho_id,
                'fecha_oficializacion': fecha,
                'cuit_exportador': cuit,
                'codigo_aduana': cod_aduana,
                'estado_declaracion': estado,
                'condicion_venta': condicion_venta,
                'fob_montoisa': fob_montoisa,
                'fob_monto': fob_monto,
                'flete_montoisa': flete_montoisa if flete_montoisa else None,
                'flete_monto': flete_monto,
                'seguro_montoisa': seguro_montoisa if seguro_montoisa else None,
                'seguro_monto': seguro_monto,
                'via_medio_transporte': via,
                'cantidad_bultos': cant_bultos,
                'peso_bultos': peso_bultos,
            })

        print(f"    → {len(registros)} despachos")
        self.stats['despachos'] += len(registros)
        return registros

    # -------------------------------------------------------------------------
    # Procesamiento ARTICULO → exportacion_items + exportacion_subitems
    # -------------------------------------------------------------------------

    def procesar_articulo(self, directorio: Path) -> Tuple[List[Dict], List[Dict]]:
        archivo = self.encontrar_archivo(directorio, 'ARTICULO')
        if not archivo:
            print(f"  ADVERTENCIA: No se encontró ARTICULO en {directorio}")
            return [], []

        print(f"  Leyendo: {archivo.name}")
        _, filas = self.leer_csv(archivo)

        items_dict: Dict[Tuple, Dict] = {}   # (despacho_id, item_id) → item
        subitems: List[Dict] = []

        for i, row in enumerate(filas, 2):
            if len(row) < 14:
                self.stats['errores'].append(f"ARTICULO linea {i}: solo {len(row)} campos")
                continue

            despacho_id = self.limpiar(row[0])
            item_id = self.limpiar(row[1])
            subitem_raw = self.limpiar(row[2])

            if not despacho_id or not item_id:
                continue

            # Normalizar item_id a 4 dígitos
            try:
                item_id_norm = str(int(item_id)).zfill(4)
            except ValueError:
                item_id_norm = item_id

            subitem_num = 0
            try:
                subitem_num = int(subitem_raw) if subitem_raw else 0
            except ValueError:
                pass

            posicion_sim = self.limpiar(row[3])
            cantidad = self.decimal(row[4])
            cod_unidad = self.limpiar(row[5])
            monto_fob = self.decimal(row[8])
            kgs_netos = self.decimal(row[9])
            estado_merc = self.limpiar(row[10])
            cod_origen = self.limpiar(row[11])    # jurisdicción argentina
            cod_pais_destino = self.limpiar(row[12])  # país destino real
            detalle = self.limpiar(row[13])

            if not estado_merc:
                estado_merc = '1'

            fecha = self.despacho_fechas.get(despacho_id)
            if not fecha:
                self.stats['errores'].append(
                    f"ARTICULO linea {i}: despacho {despacho_id} no encontrado en CABECERA"
                )
                continue

            key = (despacho_id, item_id_norm)

            if subitem_num == 0:
                # Registro a nivel item
                if key not in items_dict:
                    items_dict[key] = {
                        'despacho_id': despacho_id,
                        'fecha_oficializacion': fecha,
                        'item_id': item_id_norm,
                        'posicion_sim': posicion_sim,
                        'cod_pais_destino': cod_pais_destino,
                        'cod_pais_origen': cod_origen,
                        'codigo_unidad': cod_unidad,
                        'cantidad_unidades': cantidad,
                        'kgs_netos': kgs_netos,
                        'monto_fob_dolar': monto_fob,
                        'monto_fob_montoisa': monto_fob,
                        'estado_mercaderia': estado_merc,
                    }
            else:
                # Registro a nivel subitem
                # Si aún no tenemos el item padre, lo creamos acumulando
                if key not in items_dict:
                    items_dict[key] = {
                        'despacho_id': despacho_id,
                        'fecha_oficializacion': fecha,
                        'item_id': item_id_norm,
                        'posicion_sim': posicion_sim,
                        'cod_pais_destino': cod_pais_destino,
                        'cod_pais_origen': cod_origen,
                        'codigo_unidad': cod_unidad,
                        'cantidad_unidades': '0',
                        'kgs_netos': '0',
                        'monto_fob_dolar': '0',
                        'monto_fob_montoisa': '0',
                        'estado_mercaderia': estado_merc,
                        '_acumulado': True,
                    }

                # Acumular totales en el item padre
                item = items_dict[key]
                try:
                    item['kgs_netos'] = str(Decimal(item['kgs_netos'] or '0') + Decimal(kgs_netos or '0'))
                    item['monto_fob_dolar'] = str(Decimal(item['monto_fob_dolar'] or '0') + Decimal(monto_fob or '0'))
                    item['monto_fob_montoisa'] = item['monto_fob_dolar']
                    item['cantidad_unidades'] = str(Decimal(item['cantidad_unidades'] or '0') + Decimal(cantidad or '0'))
                except (InvalidOperation, TypeError):
                    pass

                # Subitem
                subitem_id = str(subitem_num).zfill(4)
                subitems.append({
                    'despacho_id': despacho_id,
                    'fecha_oficializacion': fecha,
                    'item_id': item_id_norm,
                    'subitem_id': subitem_id,
                    'detalle_completo': detalle or '',
                    'cantidad_unidades_subitem': cantidad,
                    'fob_dolar_subitem': monto_fob,
                })

        items = list(items_dict.values())
        print(f"    → {len(items)} items, {len(subitems)} subitems")
        self.stats['items'] += len(items)
        self.stats['subitems'] += len(subitems)
        return items, subitems

    # -------------------------------------------------------------------------
    # Procesamiento VENTAJAS → exportacion_ventajas
    # -------------------------------------------------------------------------

    def procesar_ventajas(self, directorio: Path) -> List[Dict]:
        archivo = self.encontrar_archivo(directorio, 'VENTAJAS')
        if not archivo:
            return []

        print(f"  Leyendo: {archivo.name}")
        _, filas = self.leer_csv(archivo)
        registros = []

        for i, row in enumerate(filas, 2):
            if len(row) < 3:
                continue

            despacho_id = self.limpiar(row[0])
            item_id_raw = self.limpiar(row[1])
            ventaja = self.limpiar(row[2])

            if not despacho_id or not ventaja:
                continue

            try:
                item_id = str(int(item_id_raw)).zfill(4) if item_id_raw else None
            except ValueError:
                item_id = item_id_raw

            fecha = self.despacho_fechas.get(despacho_id)
            if not fecha:
                continue

            registros.append({
                'despacho_id': despacho_id,
                'fecha_oficializacion': fecha,
                'item_id': item_id,
                'ventaja': ventaja,
            })

        print(f"    → {len(registros)} ventajas")
        self.stats['ventajas'] += len(registros)
        return registros

    # -------------------------------------------------------------------------
    # Generación de SQL
    # -------------------------------------------------------------------------

    def generar_sql_despachos(self, registros: List[Dict], output_file: Path):
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("-- =====================================================\n")
            f.write("-- EXPORTACION DESPACHOS (INFOAR) - CARGA VIA STAGING\n")
            f.write(f"-- Mes archivo: {self.mes_archivo}\n")
            f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Registros: {len(registros)}\n")
            f.write("-- =====================================================\n\n")

            f.write("DROP TABLE IF EXISTS staging_infoar_despachos;\n\n")
            f.write("CREATE TEMPORARY TABLE staging_infoar_despachos (\n")
            f.write("    despacho_id VARCHAR(16),\n")
            f.write("    fecha_oficializacion DATE,\n")
            f.write("    mes_archivo CHAR(6),\n")
            f.write("    cuit_exportador VARCHAR(12),\n")
            f.write("    codigo_aduana CHAR(3),\n")
            f.write("    estado_declaracion VARCHAR(10),\n")
            f.write("    condicion_venta VARCHAR(10),\n")
            f.write("    fob_montoisa VARCHAR(5),\n")
            f.write("    fob_monto DECIMAL(15,2),\n")
            f.write("    flete_montoisa VARCHAR(5),\n")
            f.write("    flete_monto DECIMAL(15,2),\n")
            f.write("    seguro_montoisa VARCHAR(5),\n")
            f.write("    seguro_monto DECIMAL(15,2),\n")
            f.write("    via_medio_transporte VARCHAR(10),\n")
            f.write("    cantidad_bultos NUMERIC(15,3),\n")  # puede venir como "60.000000"
            f.write("    peso_bultos DECIMAL(15,3)\n")
            f.write(");\n\n")

            f.write("COPY staging_infoar_despachos (\n")
            f.write("    despacho_id, fecha_oficializacion, mes_archivo,\n")
            f.write("    cuit_exportador, codigo_aduana, estado_declaracion, condicion_venta,\n")
            f.write("    fob_montoisa, fob_monto, flete_montoisa, flete_monto, seguro_montoisa, seguro_monto,\n")
            f.write("    via_medio_transporte, cantidad_bultos, peso_bultos\n")
            f.write(") FROM stdin;\n")

            for r in registros:
                f.write('\t'.join([
                    self.fmt(r['despacho_id']),
                    self.fmt(r['fecha_oficializacion']),
                    self.mes_archivo,
                    self.fmt(r['cuit_exportador']),
                    self.fmt(r['codigo_aduana']),
                    self.fmt(r['estado_declaracion']),
                    self.fmt(r['condicion_venta']),
                    self.fmt(r['fob_montoisa']),
                    self.fmt(r['fob_monto']),
                    self.fmt(r['flete_montoisa']),
                    self.fmt(r['flete_monto']),
                    self.fmt(r['seguro_montoisa']),
                    self.fmt(r['seguro_monto']),
                    self.fmt(r['via_medio_transporte']),
                    self.fmt(r['cantidad_bultos']),
                    self.fmt(r['peso_bultos']),
                ]) + '\n')
            f.write("\\.\n\n")

            # Auto-insertar padron faltantes
            f.write("-- Auto-insertar CUITs faltantes en padrón\n")
            # Usar LEFT JOIN en lugar de NOT IN para evitar full scan de 6.4M filas del padrón
            f.write("INSERT INTO padron (cuit, razon_social)\n")
            f.write("SELECT DISTINCT s.cuit_exportador, 'SIN DATOS - PENDIENTE ACTUALIZAR'\n")
            f.write("FROM staging_infoar_despachos s\n")
            f.write("LEFT JOIN padron p ON s.cuit_exportador = p.cuit\n")
            f.write("WHERE s.cuit_exportador IS NOT NULL AND p.cuit IS NULL\n")
            f.write("ON CONFLICT (cuit) DO NOTHING;\n\n")

            # Auto-insertar aduanas faltantes
            f.write("-- Auto-insertar aduanas faltantes\n")
            f.write("INSERT INTO aduanas (codigo, nombre)\n")
            f.write("SELECT DISTINCT codigo_aduana, 'Aduana ' || codigo_aduana || ' - Por determinar'\n")
            f.write("FROM staging_infoar_despachos\n")
            f.write("WHERE codigo_aduana IS NOT NULL\n")
            f.write("  AND codigo_aduana NOT IN (SELECT codigo FROM aduanas)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            # Auto-insertar divisas faltantes
            f.write("-- Auto-insertar divisas faltantes\n")
            f.write("INSERT INTO divisas (codigo, nombre)\n")
            f.write("SELECT DISTINCT codigo, 'Divisa ' || codigo || ' - Por determinar'\n")
            f.write("FROM (\n")
            f.write("    SELECT fob_montoisa AS codigo FROM staging_infoar_despachos WHERE fob_montoisa IS NOT NULL\n")
            f.write("    UNION SELECT flete_montoisa FROM staging_infoar_despachos WHERE flete_montoisa IS NOT NULL\n")
            f.write("    UNION SELECT seguro_montoisa FROM staging_infoar_despachos WHERE seguro_montoisa IS NOT NULL\n")
            f.write(") d WHERE codigo NOT IN (SELECT codigo FROM divisas)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            # Auto-insertar destinaciones faltantes
            f.write("-- Auto-insertar tipos de destinación faltantes\n")
            f.write("INSERT INTO destinaciones (codigo, descripcion)\n")
            f.write("SELECT DISTINCT\n")
            f.write("    SUBSTRING(despacho_id, 6, 4),\n")
            f.write("    'Destinacion ' || SUBSTRING(despacho_id, 6, 4) || ' - Por determinar'\n")
            f.write("FROM staging_infoar_despachos\n")
            f.write("WHERE SUBSTRING(despacho_id, 6, 4) NOT IN (SELECT codigo FROM destinaciones)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            f.write("-- Insertar en tabla final\n")
            f.write("INSERT INTO exportacion_despachos (\n")
            f.write("    despacho_id, fecha_oficializacion, mes_archivo,\n")
            f.write("    cuit_exportador, estado_declaracion, condicion_venta,\n")
            f.write("    fob_montoisa, fob_monto, flete_montoisa, flete_monto, seguro_montoisa, seguro_monto,\n")
            f.write("    via_medio_transporte, cantidad_bultos, peso_bultos\n")
            f.write(")\n")
            f.write("SELECT\n")
            f.write("    despacho_id, fecha_oficializacion, mes_archivo,\n")
            f.write("    cuit_exportador, estado_declaracion, condicion_venta,\n")
            f.write("    fob_montoisa, fob_monto, flete_montoisa, flete_monto, seguro_montoisa, seguro_monto,\n")
            f.write("    via_medio_transporte, cantidad_bultos::INTEGER, peso_bultos\n")
            f.write("FROM staging_infoar_despachos\n")
            f.write("ON CONFLICT (despacho_id, fecha_oficializacion, mes_archivo) DO NOTHING;\n\n")

            f.write("DROP TABLE staging_infoar_despachos;\n")

    def generar_sql_items(self, items: List[Dict], subitems: List[Dict], output_file: Path):
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("-- =====================================================\n")
            f.write("-- EXPORTACION ITEMS + SUBITEMS (INFOAR) - CARGA VIA STAGING\n")
            f.write(f"-- Mes archivo: {self.mes_archivo}\n")
            f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Items: {len(items)} | Subitems: {len(subitems)}\n")
            f.write("-- =====================================================\n\n")

            # Staging items
            f.write("DROP TABLE IF EXISTS staging_infoar_items;\n\n")
            f.write("CREATE TEMPORARY TABLE staging_infoar_items (\n")
            f.write("    despacho_id VARCHAR(16),\n")
            f.write("    fecha_oficializacion DATE,\n")
            f.write("    mes_archivo CHAR(6),\n")
            f.write("    item_id VARCHAR(10),\n")
            f.write("    posicion_sim VARCHAR(20),\n")
            f.write("    cod_pais_destino VARCHAR(10),\n")
            f.write("    cod_pais_origen VARCHAR(10),\n")
            f.write("    codigo_unidad VARCHAR(10),\n")
            f.write("    cantidad_unidades DECIMAL(15,3),\n")
            f.write("    kgs_netos DECIMAL(12,3),\n")
            f.write("    monto_fob_dolar DECIMAL(15,2),\n")
            f.write("    monto_fob_montoisa DECIMAL(15,2),\n")
            f.write("    estado_mercaderia VARCHAR(5)\n")
            f.write(");\n\n")

            f.write("COPY staging_infoar_items (\n")
            f.write("    despacho_id, fecha_oficializacion, mes_archivo, item_id,\n")
            f.write("    posicion_sim, cod_pais_destino, cod_pais_origen, codigo_unidad,\n")
            f.write("    cantidad_unidades, kgs_netos, monto_fob_dolar, monto_fob_montoisa, estado_mercaderia\n")
            f.write(") FROM stdin;\n")

            for r in items:
                f.write('\t'.join([
                    self.fmt(r['despacho_id']),
                    self.fmt(r['fecha_oficializacion']),
                    self.mes_archivo,
                    self.fmt(r['item_id']),
                    self.fmt(r['posicion_sim']),
                    self.fmt(r['cod_pais_destino']),
                    self.fmt(r['cod_pais_origen']),
                    self.fmt(r['codigo_unidad']),
                    self.fmt(r['cantidad_unidades']),
                    self.fmt(r['kgs_netos']),
                    self.fmt(r['monto_fob_dolar']),
                    self.fmt(r['monto_fob_montoisa']),
                    self.fmt(r['estado_mercaderia']),
                ]) + '\n')
            f.write("\\.\n\n")

            # Auto-inserts para items
            f.write("-- Auto-insertar unidades faltantes\n")
            f.write("INSERT INTO unidades (codigo, descripcion, activo)\n")
            f.write("SELECT DISTINCT codigo_unidad, 'Unidad ' || codigo_unidad || ' - Por determinar', TRUE\n")
            f.write("FROM staging_infoar_items WHERE codigo_unidad IS NOT NULL\n")
            f.write("  AND codigo_unidad NOT IN (SELECT codigo FROM unidades)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            f.write("-- Auto-insertar países faltantes\n")
            f.write("INSERT INTO paises (codigo, nombre)\n")
            f.write("SELECT DISTINCT codigo, 'Pais ' || codigo || ' - Por determinar'\n")
            f.write("FROM (\n")
            f.write("    SELECT cod_pais_destino AS codigo FROM staging_infoar_items WHERE cod_pais_destino IS NOT NULL\n")
            f.write(") d WHERE codigo NOT IN (SELECT codigo FROM paises)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            f.write("-- Auto-insertar estados faltantes\n")
            f.write("INSERT INTO estados (codigo, descripcion)\n")
            f.write("SELECT DISTINCT estado_mercaderia, 'Estado ' || estado_mercaderia || ' - Por determinar'\n")
            f.write("FROM staging_infoar_items WHERE estado_mercaderia IS NOT NULL\n")
            f.write("  AND estado_mercaderia NOT IN (SELECT codigo FROM estados)\n")
            f.write("ON CONFLICT (codigo) DO NOTHING;\n\n")

            f.write("-- Auto-insertar posiciones NCM faltantes\n")
            f.write("INSERT INTO nomenclador (posicion_sim, descripcion, codigo_unidad)\n")
            f.write("SELECT DISTINCT posicion_sim, 'PARTIDA NUEVA - EN PROCESO DE CLASIFICACION', NULL\n")
            f.write("FROM staging_infoar_items\n")
            f.write("WHERE posicion_sim NOT IN (SELECT posicion_sim FROM nomenclador)\n")
            f.write("ON CONFLICT (posicion_sim) DO NOTHING;\n\n")

            f.write("-- Insertar items en tabla final\n")
            f.write("INSERT INTO exportacion_items (\n")
            f.write("    despacho_id, fecha_oficializacion, mes_archivo, item_id,\n")
            f.write("    posicion_sim, cod_pais_destino, cod_pais_origen, codigo_unidad,\n")
            f.write("    cantidad_unidades, kgs_netos, monto_fob_dolar, monto_fob_montoisa, estado_mercaderia\n")
            f.write(")\n")
            f.write("SELECT\n")
            f.write("    despacho_id, fecha_oficializacion, mes_archivo, item_id,\n")
            f.write("    posicion_sim, cod_pais_destino, cod_pais_origen, codigo_unidad,\n")
            f.write("    cantidad_unidades, kgs_netos, monto_fob_dolar, monto_fob_montoisa, estado_mercaderia\n")
            f.write("FROM staging_infoar_items\n")
            f.write("ON CONFLICT (despacho_id, fecha_oficializacion, mes_archivo, item_id) DO NOTHING;\n\n")

            f.write("DROP TABLE staging_infoar_items;\n\n")

            # Subitems (si hay)
            if subitems:
                f.write("-- =====================================================\n")
                f.write(f"-- SUBITEMS: {len(subitems)}\n")
                f.write("-- =====================================================\n\n")

                f.write("DROP TABLE IF EXISTS staging_infoar_subitems;\n\n")
                f.write("CREATE TEMPORARY TABLE staging_infoar_subitems (\n")
                f.write("    despacho_id VARCHAR(16),\n")
                f.write("    fecha_oficializacion DATE,\n")
                f.write("    mes_archivo CHAR(6),\n")
                f.write("    item_id VARCHAR(10),\n")
                f.write("    subitem_id VARCHAR(10),\n")
                f.write("    detalle_completo TEXT,\n")
                f.write("    cantidad_unidades_subitem DECIMAL(15,3),\n")
                f.write("    fob_dolar_subitem DECIMAL(15,2)\n")
                f.write(");\n\n")

                f.write("COPY staging_infoar_subitems (\n")
                f.write("    despacho_id, fecha_oficializacion, mes_archivo, item_id, subitem_id,\n")
                f.write("    detalle_completo, cantidad_unidades_subitem, fob_dolar_subitem\n")
                f.write(") FROM stdin;\n")

                for r in subitems:
                    f.write('\t'.join([
                        self.fmt(r['despacho_id']),
                        self.fmt(r['fecha_oficializacion']),
                        self.mes_archivo,
                        self.fmt(r['item_id']),
                        self.fmt(r['subitem_id']),
                        self.fmt(r['detalle_completo']),
                        self.fmt(r['cantidad_unidades_subitem']),
                        self.fmt(r['fob_dolar_subitem']),
                    ]) + '\n')
                f.write("\\.\n\n")

                f.write("INSERT INTO exportacion_subitems (\n")
                f.write("    despacho_id, fecha_oficializacion, mes_archivo, item_id, subitem_id,\n")
                f.write("    detalle_completo, cantidad_unidades_subitem, fob_dolar_subitem\n")
                f.write(")\n")
                f.write("SELECT\n")
                f.write("    despacho_id, fecha_oficializacion, mes_archivo, item_id, subitem_id,\n")
                f.write("    COALESCE(detalle_completo, ''), cantidad_unidades_subitem, fob_dolar_subitem\n")
                f.write("FROM staging_infoar_subitems\n")
                f.write("ON CONFLICT (despacho_id, fecha_oficializacion, mes_archivo, item_id, subitem_id) DO NOTHING;\n\n")

                f.write("DROP TABLE staging_infoar_subitems;\n")

    def generar_sql_ventajas(self, registros: List[Dict], output_file: Path):
        if not registros:
            return

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("-- =====================================================\n")
            f.write("-- EXPORTACION VENTAJAS (INFOAR) - CARGA VIA STAGING\n")
            f.write(f"-- Mes archivo: {self.mes_archivo}\n")
            f.write(f"-- Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Registros: {len(registros)}\n")
            f.write("-- =====================================================\n\n")

            f.write("DROP TABLE IF EXISTS staging_infoar_ventajas;\n\n")
            f.write("CREATE TEMPORARY TABLE staging_infoar_ventajas (\n")
            f.write("    despacho_id VARCHAR(16),\n")
            f.write("    fecha_oficializacion DATE,\n")
            f.write("    mes_archivo CHAR(6),\n")
            f.write("    item_id VARCHAR(10),\n")
            f.write("    ventaja VARCHAR(30)\n")
            f.write(");\n\n")

            f.write("COPY staging_infoar_ventajas (\n")
            f.write("    despacho_id, fecha_oficializacion, mes_archivo, item_id, ventaja\n")
            f.write(") FROM stdin;\n")

            for r in registros:
                f.write('\t'.join([
                    self.fmt(r['despacho_id']),
                    self.fmt(r['fecha_oficializacion']),
                    self.mes_archivo,
                    self.fmt(r['item_id']),
                    self.fmt(r['ventaja']),
                ]) + '\n')
            f.write("\\.\n\n")

            # Filtrar por items existentes (VENTAJAS incluye despachos de otros meses)
            f.write("INSERT INTO exportacion_ventajas (\n")
            f.write("    despacho_id, fecha_oficializacion, mes_archivo, item_id, ventaja\n")
            f.write(")\n")
            f.write("SELECT v.despacho_id, v.fecha_oficializacion, v.mes_archivo, v.item_id, v.ventaja\n")
            f.write("FROM staging_infoar_ventajas v\n")
            f.write("WHERE EXISTS (\n")
            f.write("    SELECT 1 FROM exportacion_items i\n")
            f.write("    WHERE i.despacho_id = v.despacho_id\n")
            f.write("      AND i.mes_archivo = v.mes_archivo\n")
            f.write("      AND i.item_id = v.item_id\n")
            f.write(")\n")
            f.write("ON CONFLICT (despacho_id, fecha_oficializacion, mes_archivo, item_id, ventaja) DO NOTHING;\n\n")

            f.write("DROP TABLE staging_infoar_ventajas;\n")

    # -------------------------------------------------------------------------
    # Orquestador principal
    # -------------------------------------------------------------------------

    def procesar(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)

        todos_despachos = []
        todos_items = []
        todos_subitems = []
        todos_ventajas = []

        for directorio in self.directorios:
            print(f"\nProcesando directorio: {directorio.name}")
            despachos = self.procesar_cabecera(directorio)
            todos_despachos.extend(despachos)

        for directorio in self.directorios:
            print(f"\nProcesando artículos: {directorio.name}")
            items, subitems = self.procesar_articulo(directorio)
            todos_items.extend(items)
            todos_subitems.extend(subitems)

        for directorio in self.directorios:
            print(f"\nProcesando ventajas: {directorio.name}")
            ventajas = self.procesar_ventajas(directorio)
            todos_ventajas.extend(ventajas)

        # Generar SQLs
        f_desp = output_dir / f"exportacion_despachos_{self.mes_archivo}.sql"
        f_items = output_dir / f"exportacion_items_{self.mes_archivo}.sql"
        f_vent = output_dir / f"exportacion_ventajas_{self.mes_archivo}.sql"

        print(f"\nGenerando SQL despachos → {f_desp.name}")
        self.generar_sql_despachos(todos_despachos, f_desp)

        print(f"Generando SQL items → {f_items.name}")
        self.generar_sql_items(todos_items, todos_subitems, f_items)

        if todos_ventajas:
            print(f"Generando SQL ventajas → {f_vent.name}")
            self.generar_sql_ventajas(todos_ventajas, f_vent)

        self.mostrar_resumen()

    def mostrar_resumen(self):
        print("\n" + "="*60)
        print("RESUMEN")
        print("="*60)
        print(f"Despachos:  {self.stats['despachos']}")
        print(f"Items:      {self.stats['items']}")
        print(f"Subitems:   {self.stats['subitems']}")
        print(f"Ventajas:   {self.stats['ventajas']}")
        if self.stats['errores']:
            print(f"\nErrores ({len(self.stats['errores'])}):")
            for e in self.stats['errores'][:10]:
                print(f"  {e}")
            if len(self.stats['errores']) > 10:
                print(f"  ... y {len(self.stats['errores']) - 10} más")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Genera SQL para exportación desde archivos formato INFOAR',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Un solo directorio (Oct 2023 - fuente 1):
  python3 generar_exportacion_infoar.py \\
      data/mensuales/2023/10_octubre/raw/exportacion/INFOAR10-2023/ \\
      -m 202310 -o output/sql/2023/

  # Dos directorios mergeados (Nov 2023 - 2 fuentes):
  python3 generar_exportacion_infoar.py \\
      data/mensuales/2023/11_noviembre/raw/exportacion/INFOAR11-2023/ \\
      data/mensuales/2023/11_noviembre/raw/exportacion/INFOAR112023/ \\
      -m 202311 -o output/sql/2023/
        """
    )
    parser.add_argument('directorios', nargs='+', help='Uno o más directorios INFOAR')
    parser.add_argument('-m', '--mes', dest='mes_archivo', required=True,
                        help='Mes en formato YYYYMM (ej: 202310)')
    parser.add_argument('-o', '--output', required=True, help='Directorio de salida SQL')

    args = parser.parse_args()

    directorios = []
    for d in args.directorios:
        p = Path(d)
        if not p.exists() or not p.is_dir():
            print(f"Error: directorio no encontrado: {p}")
            sys.exit(1)
        directorios.append(p)

    output_dir = Path(args.output)
    processor = InfoarExportacionProcessor(args.mes_archivo, directorios)
    processor.procesar(output_dir)


if __name__ == '__main__':
    main()
