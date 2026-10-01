import csv
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from atualizar import REQUIRED, prepare

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'fixture.csv'
        self.out = self.base / 'result'
        self.row = dict.fromkeys(REQUIRED, '')
        self.row.update(codigo='000000123', id='001', materialouservico_id='2',
                        ehmaterialouservico_id='MATERIAL', descricaoitem='Café torrado',
                        materialouservico_classe_codigogrupoformatado='01 - Alimentos',
                        materialouservico_classe_codigonomeformatado='0101 - Café',
                        materialouservico_codigoformatado='00000042', situacao_id='ATIVO',
                        datacriacao='2024-04-05T12:00:00Z', versao='3',
                        complementacaoespecificacao='Possui especificação longa anexada')

    def write(self, rows=None, headers=None, delimiter=','):
        with self.source.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=headers or REQUIRED, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows or [self.row])

    def test_end_to_end(self):
        self.write()
        original = self.source.read_bytes()
        report = prepare(self.source, self.out)
        self.assertEqual(report['status'], 'preparado')
        self.assertEqual(self.source.read_bytes(), original)
        with sqlite3.connect(self.out / 'site/data.db') as db:
            self.assertEqual(db.execute('SELECT codigo,material_codigo,data_criacao,data_ultima_atualizacao,especificacao_longa,versao FROM items').fetchone(),
                ('000000123', '00000042', '2024-04-05T12:00:00Z', '2024-04-05T12:00:00Z', 'true', 3))
            self.assertEqual(db.execute("SELECT rowid FROM items_fts WHERE items_fts MATCH 'cafe'").fetchall(), [(1,)])
            self.assertEqual(db.execute('SELECT grupo FROM hierarchy').fetchone()[0], '01 - Alimentos')
        with gzip.open(self.out / 'site/data.db.gz', 'rb') as stream:
            self.assertEqual(stream.read(), (self.out / 'site/data.db').read_bytes())
        self.assertFalse(json.loads((self.out / 'relatorio.json').read_text())['publication'])

    def test_invalid_fields_block_artifacts(self):
        for key, value in [('codigo', '1e5'), ('id', '1.0'), ('datacriacao', '05/04/2024'),
                           ('sustentavel', 'sim'), ('materialouservico_codigoformatado', '123456789')]:
            with self.subTest(key=key):
                row = dict(self.row, **{key: value})
                self.write([row])
                out = self.base / key
                self.assertEqual(prepare(self.source, out)['status'], 'bloqueado')
                self.assertFalse((out / 'site/data.db.gz').exists())

    def test_duplicates_block(self):
        self.write([self.row, self.row])
        self.assertEqual(prepare(self.source, self.out)['status'], 'bloqueado')

    def test_missing_schema(self):
        row = dict(self.row)
        del row['datacriacao']
        self.write([row], list(row))
        with self.assertRaisesRegex(ValueError, 'datacriacao'):
            prepare(self.source, self.out)

    def test_exclusion_keeps_fts_rowids_aligned(self):
        self.write([dict(self.row, codigo='', id='3'), self.row])
        report = prepare(self.source, self.out)
        self.assertEqual(report['published_items'], 1)
        self.assertEqual(report['warnings']['excluidos_sem_codigo'], 1)

    def test_no_overwrite(self):
        self.write()
        self.out.mkdir()
        with self.assertRaisesRegex(ValueError, 'já existe'):
            prepare(self.source, self.out)

    def test_semicolon_camelcase(self):
        row = dict(self.row)
        row['dataCriacao'] = row.pop('datacriacao')
        row['dataUltimaAtualizacao'] = row.pop('dataultimaatualizacao')
        self.write([row], list(row), ';')
        self.assertEqual(prepare(self.source, self.out)['status'], 'preparado')

    def test_all_missing_codes_block(self):
        self.write([dict(self.row, codigo='')])
        self.assertEqual(prepare(self.source, self.out)['status'], 'bloqueado')

    def test_missing_hierarchy_blocks_before_converter(self):
        self.write([dict(self.row, materialouservico_classe_codigogrupoformatado='')])
        self.assertEqual(prepare(self.source, self.out)['status'], 'bloqueado')

if __name__ == '__main__':
    unittest.main()
