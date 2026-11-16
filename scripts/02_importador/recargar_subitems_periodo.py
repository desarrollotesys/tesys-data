#!/usr/bin/env python3
"""
recargar_subitems_periodo.py
=============================
Recarga (reemplaza) un único período de `exportacion_subitems` desde su
zR9 original, usando el parser corregido (sin truncado [:100]).

Uso:
    # Piloto en staging (default: localhost/docker local, NUNCA producción):
    python3 recargar_subitems_periodo.py --periodo 202607

    # Producción (requiere flag + confirmación interactiva explícita):
    python3 recargar_subitems_periodo.py --periodo 202607 --prod

    # Solo generar el SQL sin ejecutar nada (para revisión manual):
    python3 recargar_subitems_periodo.py --periodo 202607 --dry-run

Operación (transaccional, idempotente):
    1. Imprime el destino exacto (host, puerto, base, schema/contenedor) y
       ABORTA si el destino resuelve a producción sin --prod + confirmación.
    2. Respalda la partición del período (COPY a archivo .tsv.gz local,
       fuera de git).
    3. Regenera el SQL de carga desde el zR9 crudo con el parser corregido.
    4. Ejecuta en una única transacción:
           BEGIN;
           DELETE FROM exportacion_subitems WHERE mes_archivo = '<periodo>';
           <INSERT vía staging, igual que generar_exportacion_subitems.py>
           COMMIT;
       Con `\\set ON_ERROR_STOP on`: cualquier error aborta la ejecución de
       psql y dev la transacción sin COMMIT — postgres la revierte al
       cerrarse la sesión (rollback automático).
    5. Reemplazar el mismo período dos veces produce el mismo resultado
       final (idempotente): el DELETE limpia lo insertado en la corrida
       anterior antes de reinsertar.

Variables de entorno (mismas que cargar_item_calculos.py):
    PGHOST, PGPORT, PGDATABASE, PGUSER  (default: localhost/5432/comercio_exterior_argentina/tesys_user)
    TESYS_DOCKER_CONTAINER               (default: postgres_tesys, si no hay psql en PATH)

No requiere ni acepta contraseñas por línea de comando ni en el SQL generado.
"""

import argparse
import hashlib
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERADOR = Path(__file__).resolve().parent / 'generar_exportacion_subitems.py'

# Hosts que NUNCA deben tratarse como staging, incluso si alguien los pasa
# por PGHOST sin --prod. Lista blanca de "esto sí es local/staging":
STAGING_HOSTS = {'localhost', '127.0.0.1', ''}


def resolver_destino():
    """Determina cómo se va a conectar (psql local o docker exec) y con qué
    parámetros, sin abrir ninguna conexión todavía. Retorna un dict describiendo
    el destino para poder imprimirlo y auditarlo antes de ejecutar nada."""
    pghost = os.environ.get('PGHOST', 'localhost')
    pgport = os.environ.get('PGPORT', '5432')
    pgdb = os.environ.get('PGDATABASE', 'comercio_exterior_argentina')
    pguser = os.environ.get('PGUSER', 'tesys_user')
    container = os.environ.get('TESYS_DOCKER_CONTAINER', 'postgres_tesys')

    usa_psql = shutil.which('psql') is not None
    modo = 'psql local' if usa_psql else f'docker exec {container}'

    return {
        'host': pghost,
        'port': pgport,
        'db': pgdb,
        'user': pguser,
        'container': container if not usa_psql else None,
        'modo_conexion': modo,
        'usa_psql': usa_psql,
    }


def es_destino_staging(destino: dict) -> bool:
    """True si el destino es local/staging inequívoco.

    Regla: si se usa docker exec sobre un contenedor local (postgres_tesys u
    otro definido por TESYS_DOCKER_CONTAINER) SIN que PGHOST apunte a un host
    remoto explícito, se considera staging. Cualquier PGHOST que no esté en
    STAGING_HOSTS se trata como potencial producción.
    """
    if destino['host'] not in STAGING_HOSTS:
        return False
    if destino['usa_psql'] and destino['host'] not in STAGING_HOSTS:
        return False
    return True


def imprimir_destino(destino: dict, periodo: str):
    print('=' * 70)
    print('DESTINO DE CARGA')
    print('=' * 70)
    print(f'  Host:          {destino["host"] or "(vacío, asumido localhost)"}')
    print(f'  Puerto:        {destino["port"]}')
    print(f'  Base:          {destino["db"]}')
    print(f'  Usuario:       {destino["user"]}')
    print(f'  Conexión via:  {destino["modo_conexion"]}')
    print(f'  Schema:        public (exportacion_subitems, particionada por año)')
    print(f'  Período target:{periodo}  ->  partición exportacion_subitems_{periodo[:4]}')
    print('=' * 70)


def psql_cmd(destino: dict) -> list[str]:
    if destino['usa_psql']:
        return ['psql', '-h', destino['host'] or 'localhost', '-p', destino['port'],
                '-d', destino['db'], '-U', destino['user']]
    return ['docker', 'exec', '-i', destino['container'], 'psql',
            '-U', destino['user'], '-d', destino['db']]


def encontrar_zr9(periodo: str) -> Path:
    """Busca el zR9.txt de exportación para el período YYYYMM, evitando
    duplicados '(2)' (ya confirmados byte-idénticos en el inventario)."""
    candidatos = sorted(REPO_ROOT.glob(
        f'data/mensuales/*/*/raw/exportacion/**/zR9.txt'
    ))
    matches = [p for p in candidatos if f'{periodo}Expo' in str(p)]
    if not matches:
        raise SystemExit(f'ERROR: no se encontró zR9.txt para el período {periodo}')
    # Preferir la ruta sin "(2)" si hay duplicados
    matches.sort(key=lambda p: ' (2)' in str(p))
    elegido = matches[0]
    if len(matches) > 1:
        md5s = {hashlib.md5(p.read_bytes()).hexdigest() for p in matches}
        if len(md5s) > 1:
            raise SystemExit(
                f'ERROR: hay {len(matches)} archivos zR9 para {periodo} con '
                f'contenido DIFERENTE — resolver manualmente antes de continuar:\n'
                + '\n'.join(f'  {p}' for p in matches)
            )
        log.info(f'{len(matches)} archivos duplicados byte-idénticos para {periodo}; usando {elegido}')
    return elegido


def backup_periodo(destino: dict, periodo: str) -> Path:
    backup_dir = REPO_ROOT / 'data' / 'TMP' / 'backups' / 'exportacion_subitems'
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = backup_dir / f'exportacion_subitems_{periodo}_{ts}.tsv.gz'

    # COPY ... TO STDOUT + gzip local (más portable que `TO PROGRAM`, que
    # requeriría permisos de superusuario en el server).
    cmd = psql_cmd(destino) + ['-c',
        f"COPY (SELECT * FROM exportacion_subitems WHERE mes_archivo = '{periodo}') "
        f"TO STDOUT WITH (FORMAT csv, DELIMITER E'\\t', HEADER true)"]

    log.info(f'Respaldando partición {periodo} -> {out_path}')
    with open(out_path, 'wb') as gz_target:
        proc_psql = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc_gzip = subprocess.Popen(['gzip'], stdin=proc_psql.stdout, stdout=gz_target)
        proc_psql.stdout.close()
        proc_gzip.communicate()
        ret = proc_psql.wait()
        if ret != 0 or proc_gzip.returncode != 0:
            raise SystemExit(f'ERROR: backup falló (psql={ret}, gzip={proc_gzip.returncode})')

    filas = sum(1 for _ in __import__('gzip').open(out_path, 'rt')) - 1  # -1 header
    log.info(f'Backup OK: {out_path} ({filas} filas, sin contar header)')
    return out_path


def generar_sql_periodo(periodo: str, zr9_path: Path) -> Path:
    tmp_dir = REPO_ROOT / 'data' / 'TMP' / 'recarga_subitems'
    tmp_dir.mkdir(parents=True, exist_ok=True)
    sql_base = tmp_dir / f'subitems_{periodo}_insert.sql'
    sql_final = tmp_dir / f'subitems_{periodo}_transaccion.sql'

    log.info(f'Regenerando SQL desde {zr9_path} con parser corregido...')
    result = subprocess.run(
        [sys.executable, str(GENERADOR), str(zr9_path), '-m', periodo, '-o', str(sql_base)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit('ERROR: generar_exportacion_subitems.py falló')
    log.info(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else 'OK')

    body = sql_base.read_text(encoding='utf-8')

    wrapped = (
        "-- Recarga transaccional de exportacion_subitems para un único período.\n"
        "-- Generado por recargar_subitems_periodo.py — NO commitear (data/TMP).\n"
        "\\set ON_ERROR_STOP on\n\n"
        "BEGIN;\n\n"
        f"-- 1. Eliminar exclusivamente el período {periodo} (reemplazo, no acumulación)\n"
        f"DELETE FROM exportacion_subitems WHERE mes_archivo = '{periodo}';\n\n"
        "-- 2. Recargar desde staging con el parser corregido (sin truncado)\n"
        + body +
        "\nCOMMIT;\n"
    )
    sql_final.write_text(wrapped, encoding='utf-8')
    return sql_final


def ejecutar_sql(destino: dict, sql_path: Path):
    cmd = psql_cmd(destino) + ['-v', 'ON_ERROR_STOP=1', '-f']
    if destino['usa_psql']:
        cmd = cmd + [str(sql_path)]
        log.info(f'Ejecutando: {" ".join(cmd)}')
        result = subprocess.run(cmd)
    else:
        # docker exec no puede leer un archivo del host directamente por -f;
        # se pasa el contenido por stdin.
        cmd = psql_cmd(destino) + ['-v', 'ON_ERROR_STOP=1']
        log.info(f'Ejecutando via stdin en contenedor {destino["container"]}')
        with open(sql_path, 'rb') as f:
            result = subprocess.run(cmd, stdin=f)
    if result.returncode != 0:
        raise SystemExit(
            f'ERROR: la carga falló (exit={result.returncode}). '
            'La transacción NO se comiteó (rollback automático al cerrar la sesión). '
            f'Backup disponible para restaurar si hiciera falta.'
        )
    log.info('Carga OK — transacción comiteada.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--periodo', required=True, help='YYYYMM, ej: 202607')
    ap.add_argument('--prod', action='store_true', help='Autoriza apuntar a un destino no-staging')
    ap.add_argument('--dry-run', action='store_true', help='Solo genera el SQL, no ejecuta ni respalda')
    ap.add_argument('--skip-backup', action='store_true', help='NO recomendado; salta el respaldo')
    args = ap.parse_args()

    periodo = args.periodo
    if len(periodo) != 6 or not periodo.isdigit():
        raise SystemExit(f'ERROR: --periodo debe ser YYYYMM, recibido: {periodo}')

    destino = resolver_destino()
    imprimir_destino(destino, periodo)

    if not es_destino_staging(destino) and not args.prod:
        raise SystemExit(
            'ABORTADO: el destino no resuelve inequívocamente a staging local '
            f'(PGHOST={destino["host"]!r}). Si esto es intencional y es producción, '
            're-ejecutar con --prod (se pedirá confirmación explícita).'
        )

    if args.prod:
        print()
        print('⚠️  MODO --prod: este destino se tratará como PRODUCCIÓN.')
        resp = input(f'Escribí "RECARGAR {periodo} PROD" para confirmar: ')
        if resp.strip() != f'RECARGAR {periodo} PROD':
            raise SystemExit('ABORTADO: confirmación no coincide.')

    zr9_path = encontrar_zr9(periodo)
    log.info(f'zR9 fuente: {zr9_path}')

    sql_path = generar_sql_periodo(periodo, zr9_path)
    log.info(f'SQL transaccional generado: {sql_path}')

    if args.dry_run:
        log.info('--dry-run: no se respalda ni se ejecuta nada. Revisar el SQL generado manualmente.')
        return

    if not args.skip_backup:
        backup_periodo(destino, periodo)
    else:
        log.warning('--skip-backup: SIN respaldo previo a la recarga.')

    ejecutar_sql(destino, sql_path)


if __name__ == '__main__':
    main()
