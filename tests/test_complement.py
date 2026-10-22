import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('transform', ROOT / 'scripts/transform.py')
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


class ComplementTest(unittest.TestCase):
    def test_preserves_and_searches_complement_for_both_types(self):
        columns = ['ehmaterialouservico_id', 'materialouservico_classe_codigogrupoformatado',
                   'materialouservico_classe_codigonomeformatado', 'codigo', 'especificacaocompleta',
                   'descricaoitem', 'situacao_id', 'materialouservico_naturezadespesa_nome',
                   'linhasfornecimentoformatadas', 'elementositemdespesaformatados',
                   'materialouservico_codigoformatado', 'materialouservico_nome',
                   'ehagriculturafamiliar', 'sustentavel', 'espokregprecos',
                   'complementacaoespecificacao', 'versao', 'datacriacao',
                   'dataultimaatualizacao', 'id', 'materialouservico_id']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            converter.SRC = str(root / 'raw.db')
            converter.DEST = str(root / 'data.db')
            converter.DEST_GZ = str(root / 'data.db.gz')
            raw = sqlite3.connect(converter.SRC)
            raw.execute('CREATE TABLE items (' + ','.join(c + ' TEXT' for c in columns) + ')')
            complements = ['GARANTIA CONFORME EDITAL\n<script>texto</script>',
                           'CONFORME TERMO DE REFERÊNCIA; ESPECIFICACAO LONGA ANEXADA', None, '']
            for i, complement in enumerate(complements):
                row = dict.fromkeys(columns, '')
                row.update(ehmaterialouservico_id='MATERIAL' if i % 2 == 0 else 'SERVICO',
                           codigo=str(i + 1), id=str(i + 1), especificacaocompleta='CADEIRA',
                           complementacaoespecificacao=complement, situacao_id='ATIVO')
                raw.execute('INSERT INTO items VALUES (' + ','.join('?' for _ in columns) + ')',
                            [row[k] for k in columns])
            raw.commit()
            raw.close()
            converter.main()
            with sqlite3.connect(converter.DEST) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM items').fetchone()[0], 4)
                self.assertEqual(db.execute('SELECT complementacao_especificacao FROM items ORDER BY item_id').fetchall(),
                                 [(v or '',) for v in complements])
                self.assertEqual(db.execute("SELECT codigo FROM items_fts WHERE items_fts MATCH 'edital'").fetchall(), [('000000001',)])
                self.assertEqual(db.execute("SELECT codigo FROM items_fts WHERE items_fts MATCH 'referencia'").fetchall(), [('000000002',)])
                self.assertEqual(db.execute("SELECT COUNT(*) FROM items_fts WHERE items_fts MATCH 'cadeira'").fetchone()[0], 4)
                self.assertEqual(db.execute('SELECT especificacao_longa FROM items ORDER BY item_id').fetchall(),
                                 [('false',), ('true',), ('false',), ('false',)])
                db.execute("INSERT INTO items_fts(items_fts) VALUES ('integrity-check')")


if __name__ == '__main__':
    unittest.main()
