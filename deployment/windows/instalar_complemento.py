"""Atualiza o conversor local; nao publica, extrai ou altera agendamentos."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

ORIGINAL_SHA256 = '761bfabf1cba2de1d77d06807ba40736a48fcf0929e234a2444d4ac2a1de9aaf'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', required=True, type=Path, help='Pasta da rotina CATMAS no Windows')
    parser.add_argument('--revision', required=True, help='Commit que contem este conversor')
    args = parser.parse_args()
    if not re.fullmatch('[a-f0-9]{40}', args.revision):
        raise SystemExit('Informe o SHA completo do commit revisado.')
    target = args.target.resolve()
    converter = target / 'conversor_original.py'
    publisher = target / 'publicar_catmas.py'
    source = Path(__file__).resolve().parents[2] / 'scripts/transform.py'
    new_converter = source.read_bytes()
    compile(new_converter, str(source), 'exec')
    old_converter = converter.read_bytes()
    old_publisher = publisher.read_bytes()
    if hashlib.sha256(old_converter).hexdigest() != ORIGINAL_SHA256:
        raise SystemExit('Conversor instalado diferente da versao verificada. Nada alterado.')
    text = old_publisher.decode('utf-8')
    old_line = "CONVERTER = 'f8c392eac1944c690d42c17b9aec60812a78065d'"
    if text.count(old_line) != 1 or 'import conversor_original as converter' not in text:
        raise SystemExit('Publicador instalado diferente do esperado. Nada alterado.')
    validation = "SELECT data_criacao,data_ultima_atualizacao,versao,especificacao_longa,ok_registro_precos FROM items LIMIT 1"
    if text.count(validation) != 1:
        raise SystemExit('Validacao do publicador diferente do esperado. Nada alterado.')
    text = text.replace(old_line, "CONVERTER = '" + args.revision + "'")
    text = text.replace(validation, validation.replace(' FROM items', ',complementacao_especificacao FROM items'))
    new_publisher = text.encode('utf-8')
    compile(new_publisher, str(publisher), 'exec')
    # Mesma trava da rotina integrada: nao disputar com uma carga em andamento.
    spec = importlib.util.spec_from_file_location('extrair_local', target / 'extrair_catmas.py')
    extraction = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(target))
    sys.modules[spec.name] = extraction
    spec.loader.exec_module(extraction)
    with extraction.output_lock(target / 'publicacao/processo'):
        state = target / 'publicacao-integrada'
        pending = state / 'pendente.json'
        if pending.exists():
            p = json.loads(pending.read_text(encoding='utf-8'))
            success = state / 'sucesso.json'
            done = json.loads(success.read_text(encoding='utf-8')) if success.exists() else {}
            cycle = p.get('metadata', {}).get('cycle_id')
            completed = done.get('requested_cycle', done.get('metadata', {}).get('cycle_id'))
            if not cycle or cycle != completed:
                raise SystemExit('Existe publicacao pendente. Conclua-a antes de instalar.')
        backup = target / ('backup-complemento-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        backup.mkdir()
        shutil.copy2(converter, backup / converter.name)
        shutil.copy2(publisher, backup / publisher.name)
        try:
            for dest, data in [(converter, new_converter), (publisher, new_publisher)]:
                temp = dest.with_name(dest.name + '.complemento.tmp')
                temp.write_bytes(data)
                os.replace(temp, dest)
        except Exception:
            shutil.copy2(backup / converter.name, converter)
            shutil.copy2(backup / publisher.name, publisher)
            raise
    print('Conversor atualizado. Backup:', backup)
    print('Nenhuma publicacao feita. Gere e valide um novo lote antes de publicar.')


if __name__ == '__main__':
    main()
