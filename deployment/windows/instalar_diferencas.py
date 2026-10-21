# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Install into the verified existing task; never create or alter a schedule."""
import argparse
import datetime as dt
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ORIGINAL = '3cc411d51eca2a3dc847459a9ab1e38e10469e0dfbfe8850f77c162bfc0e3d5f'
FILES = ('diferencas_incrementais.py', 'diferencas_consumidores.py', 'rotina_integrada.py')


def normalized(path):
    return hashlib.sha256(path.read_text(encoding='utf-8-sig').replace('\r\n', '\n').rstrip().encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destino', type=Path, default=Path(os.environ.get('USERPROFILE', str(Path.home()))) / 'Documents/CATMAS-Extracao-Python-v3')
    args = parser.parse_args(); target = args.destino.resolve(); source = Path(__file__).resolve().parent
    if os.name != 'nt' or sys.version_info < (3, 11):
        raise RuntimeError('Execute no Windows da tarefa, com Python 3.11 ou superior via uv.')
    tool = str(Path(os.environ['SystemRoot']) / 'System32/schtasks.exe')
    result = subprocess.run([tool, '/Query', '/TN', 'CATMAS-Extracao-Python-1230', '/XML'], capture_output=True)
    if result.returncode:
        raise RuntimeError('Tarefa existente nao encontrada; nenhuma tarefa sera criada.')
    raw = result.stdout
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-16-le' if b'\x00' in raw[:100] else 'utf-8-sig')
    xml = ET.fromstring(raw.decode(encoding)); ns = '{http://schemas.microsoft.com/windows/2004/02/mit/task}'
    actions = xml.findall('.//' + ns + 'Exec')
    if len(actions) != 1:
        raise RuntimeError('Tarefa com acoes inesperadas.')
    action = actions[0]
    command, arguments, directory = [action.findtext(ns + name) for name in ('Command', 'Arguments', 'WorkingDirectory')]
    expected = subprocess.list2cmdline(['run', '--offline', '--script', str(target/'rotina_integrada.py'), 'all', '--scheduled'])
    if not command or Path(command).name.lower() != 'uv.exe' or arguments != expected or Path(directory or '').resolve() != target:
        raise RuntimeError('A tarefa nao aponta para a rotina/pasta esperada; nada alterado.')
    for name in FILES:
        compile((source/name).read_text(encoding='utf-8'), name, 'exec')
    if normalized(target/'rotina_integrada.py') not in (ORIGINAL, normalized(source/'rotina_integrada.py')):
        raise RuntimeError('A rotina instalada mudou desde o arquivo analisado. Envie a versao atual antes de instalar.')
    sys.path.insert(0, str(target))
    import extrair_catmas as e
    state = target/'publicacao'; state.mkdir(exist_ok=True)
    with e.output_lock(state/'processo'):
        backup = target/'backups-diferencas'/dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(parents=True)
        (backup/'tarefa.xml').write_bytes(raw)
        existed = set()
        for name in FILES:
            if (target/name).exists():
                existed.add(name); shutil.copy2(target/name, backup/name)
        try:
            for name in FILES:
                tmp = target/(name+'.novo'); shutil.copy2(source/name, tmp); os.replace(tmp, target/name)
            result = subprocess.run([sys.executable, '-B', '-c', 'import rotina_integrada; assert callable(rotina_integrada.di.publish)'], cwd=target, capture_output=True)
            if result.returncode:
                raise RuntimeError('Conferencia dos modulos falhou; arquivos anteriores serao restaurados.')
        except Exception:
            for name in FILES:
                if name in existed: shutil.copy2(backup/name, target/name)
                else: (target/name).unlink(missing_ok=True)
            raise
    print('INSTALADO na rotina da tarefa CATMAS-Extracao-Python-1230; horarios e acao preservados.')
    print('Backup:', backup)
    print('PENDENTE: executar rotina_integrada.py retry e conferir a publicacao real.')
    print('Se nao houver lote preparado, executar rotina_integrada.py all --scheduled.')


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('INSTALACAO NAO CONCLUIDA:', str(exc)); sys.exit(1)
