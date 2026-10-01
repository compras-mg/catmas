"""Preparação local CATMAS. Não faz push nem publica GitHub Pages."""
import argparse
import collections
import csv
import datetime
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = '''ehmaterialouservico_id materialouservico_classe_codigogrupoformatado
materialouservico_classe_codigonomeformatado codigo especificacaocompleta descricaoitem
situacao_id materialouservico_naturezadespesa_nome linhasfornecimentoformatadas
elementositemdespesaformatados materialouservico_codigoformatado materialouservico_nome
ehagriculturafamiliar sustentavel espokregprecos complementacaoespecificacao versao
datacriacao dataultimaatualizacao id materialouservico_id'''.split()

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def prepare(source, destination, encoding='utf-8-sig', delimiter=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('A pasta de saída já existe; escolha uma pasta nova.')
    if not source.is_file():
        raise ValueError('CSV não encontrado: ' + str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {'status': 'validando', 'source_sha256': digest(source),
              'fixture': str(source), 'errors': [], 'warnings': {}, 'rows': 0,
              'publication': False, 'converter_commit': 'f8c392eac1944c690d42c17b9aec60812a78065d'}
    counts = collections.Counter()
    ids, codes = set(), set()
    with tempfile.TemporaryDirectory(prefix='catmas-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        (stage / 'data-raw').mkdir()
        (stage / 'site').mkdir()
        shutil.copyfile(source, stage / 'data-raw/main.csv')
        if digest(stage / 'data-raw/main.csv') != report['source_sha256']:
            raise ValueError('CSV mudou durante a cópia; execute novamente após concluir a extração.')
        csv.field_size_limit(16 * 1024 * 1024)
        with open(stage / 'data-raw/main.csv', encoding=encoding, newline='') as stream:
            sample = stream.read(65536)
            stream.seek(0)
            sep = delimiter or csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
            reader = csv.reader(stream, delimiter=sep)
            original = next(reader)
            headers = [x.strip().lower() for x in original]
            if len(headers) != len(set(headers)):
                raise ValueError('Colunas duplicadas após normalização de nomes.')
            missing = sorted(set(REQUIRED) - set(headers))
            if missing:
                raise ValueError('Colunas obrigatórias ausentes: ' + ', '.join(missing))
            report.update({'columns': original, 'encoding': encoding, 'delimiter': sep})
            connection = sqlite3.connect(stage / 'data-raw/data.db')
            quoted = ','.join('"' + x.replace('"', '""') + '" TEXT' for x in headers)
            connection.execute('CREATE TABLE items (' + quoted + ')')
            insert = 'INSERT INTO items VALUES (' + ','.join('?' for _ in headers) + ')'
            for line, values in enumerate(reader, 2):
                report['rows'] += 1
                if len(values) != len(headers):
                    report['errors'].append('Linha %d: número incorreto de campos' % line)
                    continue
                row = dict(zip(headers, values))
                for key, width in [('codigo', 9), ('materialouservico_codigoformatado', 8)]:
                    value = row[key].strip()
                    if value and not re.fullmatch(r'[0-9]{1,%d}' % width, value):
                        report['errors'].append('Linha %d: %s inválido' % (line, key))
                for key in ['id', 'materialouservico_id', 'versao']:
                    value = row[key].strip()
                    if (key == 'id' and not value) or (value and not re.fullmatch(r'[0-9]+', value)):
                        report['errors'].append('Linha %d: %s inválido' % (line, key))
                for key in ['datacriacao', 'dataultimaatualizacao']:
                    value = row[key].strip()
                    if value:
                        try:
                            if not re.match(r'^\d{4}-\d{2}-\d{2}(?:$|[T ])', value):
                                raise ValueError()
                            datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except ValueError:
                            report['errors'].append('Linha %d: %s deve ser data ISO válida' % (line, key))
                    else:
                        counts[key + '_vazia'] += 1
                code = row['codigo'].strip()
                if not code:
                    counts['excluidos_sem_codigo'] += 1
                else:
                    normalized = code.zfill(9)
                    if normalized in codes:
                        report['errors'].append('Linha %d: código duplicado' % line)
                    codes.add(normalized)
                    item_id = row['id'].strip().lstrip('0') or '0'
                    if item_id in ids:
                        report['errors'].append('Linha %d: id duplicado' % line)
                    ids.add(item_id)
                    for key in ['ehmaterialouservico_id', 'materialouservico_classe_codigogrupoformatado',
                                'materialouservico_classe_codigonomeformatado']:
                        if not row[key].strip():
                            report['errors'].append('Linha %d: %s vazio' % (line, key))
                for key in ['linhasfornecimentoformatadas', 'elementositemdespesaformatados', 'descricaoitem']:
                    if not row[key].strip():
                        counts[key + '_vazio'] += 1
                for key in ['ehagriculturafamiliar', 'sustentavel', 'espokregprecos']:
                    if row[key].strip() and row[key].strip().lower() not in ('true', 'false'):
                        report['errors'].append('Linha %d: %s deve ser true/false' % (line, key))
                if row['situacao_id'].strip().upper() not in ('ATIVO', 'SUSPENSO_PARA_COMPRA', 'SUSPENSO PARA COMPRA', 'INATIVO'):
                    counts['situacoes_agregadas_como_inativo'] += 1
                cleaned = [value.strip() or None for value in values]
                connection.execute(insert, cleaned)
            connection.commit()
            connection.close()
        if not report['rows'] or report['rows'] == counts['excluidos_sem_codigo']:
            report['errors'].append('Nenhum item publicável')
        report['warnings'] = dict(counts)
        if report['errors']:
            report['status'] = 'bloqueado'
            destination.mkdir()
            (destination / 'relatorio.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            return report
        subprocess.run([sys.executable, str(ROOT / 'scripts/transform.py')], cwd=stage, check=True)
        db = stage / 'site/data.db'
        with sqlite3.connect(db) as connection:
            if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Banco falhou na verificação de integridade')
            total = connection.execute('SELECT COUNT(*) FROM items').fetchone()[0]
            fts = connection.execute('SELECT COUNT(*) FROM items_fts').fetchone()[0]
            expected = report['rows'] - counts['excluidos_sem_codigo']
            if total != expected or fts != total:
                raise ValueError('Contagens de itens/índice inconsistentes')
            connection.execute("INSERT INTO items_fts(items_fts) VALUES('integrity-check')")
            connection.execute('SELECT codigo, data_criacao, data_ultima_atualizacao, especificacao_longa FROM items LIMIT 1').fetchall()
        # Compressão reproduzível; conferir o conteúdo que o navegador receberá.
        with open(db, 'rb') as stream, open(stage / 'site/data.db.gz', 'wb') as output:
            with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as compressed:
                shutil.copyfileobj(stream, compressed)
        with gzip.open(stage / 'site/data.db.gz', 'rb') as stream:
            if hashlib.sha256(stream.read()).hexdigest() != digest(db):
                raise ValueError('Compressão não reproduz o banco validado')
        report.update({'status': 'preparado', 'published_items': total,
                       'artifacts_sha256': {str(p.relative_to(stage)): digest(p) for p in stage.rglob('*') if p.is_file()}})
        (stage / 'relatorio.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        shutil.copytree(stage, destination)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv')
    parser.add_argument('--saida', required=True, help='Pasta nova para os resultados')
    parser.add_argument('--encoding', default='utf-8-sig')
    parser.add_argument('--delimiter', choices=[',', ';', '\t', '|'])
    args = parser.parse_args()
    try:
        report = prepare(args.csv, args.saida, args.encoding, args.delimiter)
        print(report['status'] + ': ' + str(Path(args.saida).resolve() / 'relatorio.json'))
        return 0 if report['status'] == 'preparado' else 2
    except (ValueError, OSError, csv.Error, sqlite3.Error, subprocess.CalledProcessError) as error:
        print('Falha: ' + str(error), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
