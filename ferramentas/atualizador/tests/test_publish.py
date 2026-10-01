import base64
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atualizar import REQUIRED, prepare
from publicar import PublicationError, publish, verify, git_blob_sha, GitHub

class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.head = 'old'
        self.race = False
        self.source = {'branch': 'gh-pages', 'path': '/'}
        self.entries = [{'path': 'index.html', 'sha': 'html'},
                        {'path': 'data.db.gz', 'sha': 'previous'},
                        {'path': 'history.db.gz', 'sha': 'history'}]
        self.build_status = 'built'
        self.build_commit = None

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if path == '/pages':
            return {'source': self.source, 'build_type': 'legacy', 'html_url': 'https://compras-mg.github.io/catmas/'}
        if method == 'GET' and path == '/git/ref/heads/gh-pages':
            if self.race and any(p == '/git/commits' and m == 'POST' for m, p, _ in self.calls):
                self.head = 'concurrent'
            return {'object': {'sha': self.head}}
        if path == '/git/commits/old':
            return {'tree': {'sha': 'oldtree'}}
        if path == '/git/trees/oldtree':
            return {'tree': self.entries}
        if path == '/git/blobs/html':
            return {'encoding': 'base64', 'content': base64.b64encode(b'data_criacao especificacao_longa data.db.gz').decode()}
        if path == '/git/blobs' and method == 'POST':
            return {'sha': git_blob_sha(base64.b64decode(payload['content']))}
        if path == '/git/trees' and method == 'POST':
            return {'sha': 'newtree'}
        if path == '/git/commits' and method == 'POST':
            return {'sha': 'new'}
        if path == '/git/refs/heads/gh-pages' and method == 'PATCH':
            self.head = payload['sha']
            return {'object': {'sha': self.head}}
        if path == '/pages/builds/latest':
            return {'commit': self.build_commit or self.head, 'status': self.build_status}
        raise AssertionError((method, path))

class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'out'
        source = self.root / 'input.csv'
        row = dict.fromkeys(REQUIRED, '')
        row.update(codigo='12', id='1', ehmaterialouservico_id='MATERIAL', descricaoitem='Café',
                   datacriacao='2024-01-02', materialouservico_codigoformatado='42',
                   materialouservico_classe_codigogrupoformatado='01 - Alimentos',
                   materialouservico_classe_codigonomeformatado='0101 - Café')
        with source.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, REQUIRED)
            writer.writeheader()
            writer.writerow(row)
        self.report = prepare(source, self.folder)
        self.expected = self.report['artifacts_sha256']['site/data.db.gz']
        self.client = FakeGitHub()

    def verifier(self, client, folder, state, **kwargs):
        return verify(client, folder, state, timeout=0, hash_reader=lambda url: self.expected)

    def test_prepare_to_published(self):
        state = publish(self.client, self.folder, verifier=self.verifier)
        self.assertEqual(state['status'], 'publicado')
        writes = [(m, p, v) for m, p, v in self.client.calls if m != 'GET']
        self.assertEqual([p for _, p, _ in writes], ['/git/blobs', '/git/trees', '/git/commits', '/git/refs/heads/gh-pages'])
        tree = writes[1][2]
        self.assertEqual(tree['base_tree'], 'oldtree')
        self.assertEqual({v['path'] for v in tree['tree']}, {'data.db.gz', 'atualizacao.json'})
        self.assertEqual(writes[2][2]['parents'], ['old'])
        self.assertFalse(writes[3][2]['force'])
        saved = json.loads((self.folder / 'publicacao.json').read_text())
        self.assertEqual(saved['previous_commit'], 'old')
        self.assertEqual(saved['data_sha256'], self.expected)

    def test_wrong_pages_source_prevents_writes(self):
        self.client.source = {'branch': 'main', 'path': '/'}
        with self.assertRaises(PublicationError):
            publish(self.client, self.folder)
        self.assertTrue(all(m == 'GET' for m, _, _ in self.client.calls))

    def test_tampered_data_prevents_network(self):
        with (self.folder / 'site/data.db.gz').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaises(PublicationError):
            publish(self.client, self.folder)
        self.assertEqual(self.client.calls, [])

    def test_concurrent_update_prevents_ref_write(self):
        self.client.race = True
        with self.assertRaisesRegex(PublicationError, 'mudou'):
            publish(self.client, self.folder)
        self.assertFalse(any(m == 'PATCH' for m, _, _ in self.client.calls))

    def test_no_change_skips_commit(self):
        for entry in self.client.entries:
            if entry['path'] == 'data.db.gz':
                entry['sha'] = git_blob_sha((self.folder / 'site/data.db.gz').read_bytes())
        state = publish(self.client, self.folder, verifier=self.verifier)
        self.assertEqual(state['commit'], 'old')
        self.assertEqual(state['status'], 'publicado')
        self.assertTrue(all(m == 'GET' for m, _, _ in self.client.calls))

    def test_wrong_live_hash_is_pending(self):
        def verifier(client, folder, state, **kwargs):
            return verify(client, folder, state, timeout=0, hash_reader=lambda _: 'stale')
        state = publish(self.client, self.folder, verifier=verifier)
        self.assertEqual(state['status'], 'enviado_verificacao_pendente')

    def test_old_build_cannot_confirm_new_commit(self):
        self.client.build_commit = 'old'
        state = publish(self.client, self.folder, verifier=self.verifier)
        self.assertEqual(state['status'], 'enviado_verificacao_pendente')

    def test_build_failure_records_sent_commit(self):
        self.client.build_status = 'errored'
        with self.assertRaisesRegex(PublicationError, 'falhou'):
            publish(self.client, self.folder, verifier=self.verifier)
        state = json.loads((self.folder / 'publicacao.json').read_text())
        self.assertEqual(state['status'], 'falha_pages')
        self.assertEqual(state['commit'], 'new')

    def test_api_error_does_not_expose_credentials(self):
        import urllib.error
        client = GitHub('secret-test')
        with patch.object(client.opener, 'open', side_effect=urllib.error.HTTPError('url', 403, 'secret-test', {}, None)):
            with self.assertRaises(PublicationError) as caught:
                client.request('GET', '/pages')
        self.assertNotIn('secret-test', str(caught.exception))

    def test_resume_verification_never_writes_git(self):
        state = publish(self.client, self.folder, verifier=self.verifier)
        self.client.calls.clear()
        verify(self.client, self.folder, state, timeout=0, hash_reader=lambda _: self.expected)
        self.assertTrue(all(m == 'GET' for m, _, _ in self.client.calls))

if __name__ == '__main__':
    unittest.main()
