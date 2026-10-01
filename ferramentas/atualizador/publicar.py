"""Valida o CSV, atualiza compras-mg/catmas e verifica GitHub Pages."""
import argparse
import base64
import csv
import datetime
import getpass
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from atualizar import prepare, digest, ROOT

REPO = 'compras-mg/catmas'
BRANCH = 'gh-pages'
API = 'https://api.github.com/repos/' + REPO

class PublicationError(RuntimeError):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise PublicationError('Redirecionamento da API recusado; nenhuma credencial foi reenviada.')

class GitHub:
    def __init__(self, token):
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(API + path, data=body, method=method,
            headers={'Authorization': 'Bearer ' + self.token,
                     'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28',
                     'Content-Type': 'application/json', 'User-Agent': 'catmas-atualizador'})
        try:
            with self.opener.open(request, timeout=60) as response:
                data = response.read()
                return json.loads(data) if data else {}
        except urllib.error.HTTPError as error:
            # Não incluir headers, token, payload ou conteúdo do erro no log.
            raise PublicationError('GitHub HTTP %d em %s %s. Confira acesso/permissões e configuração.' %
                                   (error.code, method, path)) from None
        except urllib.error.URLError:
            raise PublicationError('Falha de conexão com GitHub em %s %s.' % (method, path)) from None

def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()

def save(folder, state):
    path = Path(folder) / 'publicacao.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)

def preflight(client):
    pages = client.request('GET', '/pages')
    source = pages.get('source', {})
    if pages.get('build_type', 'legacy') != 'legacy' or source != {'branch': BRANCH, 'path': '/'}:
        raise PublicationError('GitHub Pages precisa publicar a raiz de gh-pages pelo modo de branch. '
                               'Configuração diferente detectada; nenhuma alteração feita.')
    url = pages.get('html_url', '')
    if urllib.parse.urlparse(url).scheme != 'https':
        raise PublicationError('URL HTTPS do Pages ausente ou inválida.')
    head = client.request('GET', '/git/ref/heads/' + BRANCH)['object']['sha']
    commit = client.request('GET', '/git/commits/' + head)
    tree = client.request('GET', '/git/trees/' + commit['tree']['sha'])
    entries = {entry['path']: entry for entry in tree['tree']}
    if tree.get('truncated') or 'index.html' not in entries:
        raise PublicationError('Árvore publicada incompleta ou sem index.html.')
    blob = client.request('GET', '/git/blobs/' + entries['index.html']['sha'])
    if blob.get('encoding') != 'base64':
        raise PublicationError('Codificação inesperada do frontend.')
    html = base64.b64decode(blob['content']).decode('utf-8')
    if not all(field in html for field in ('data_criacao', 'especificacao_longa', 'data.db.gz')):
        raise PublicationError('Frontend publicado não tem o contrato esperado de datas/especificação longa.')
    return pages, head, commit['tree']['sha'], entries

def live_hash(url):
    # URL pública, sem header de autenticação. Hash do arquivo servido aos usuários.
    request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache',
                                                'User-Agent': 'catmas-atualizador'})
    with urllib.request.urlopen(request, timeout=60) as response:
        h = hashlib.sha256()
        total = 0
        for block in iter(lambda: response.read(1024 * 1024), b''):
            total += len(block)
            if total > 100 * 1024 * 1024:
                raise PublicationError('Arquivo publicado acima do limite de verificação.')
            h.update(block)
        return h.hexdigest()

def verify(client, folder, state, timeout=600, interval=10, hash_reader=live_hash,
           clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    url = state['page_url'].rstrip('/') + '/data.db.gz?catmas=' + state['commit']
    state['status'] = 'aguardando_pages'
    save(folder, state)
    while True:
        head = client.request('GET', '/git/ref/heads/' + BRANCH)['object']['sha']
        if head != state['commit']:
            state['status'] = 'substituida_por_outra_atualizacao'
            save(folder, state)
            raise PublicationError('Outra atualização avançou gh-pages; esta execução não será marcada como publicada.')
        try:
            build = client.request('GET', '/pages/builds/latest')
            if build.get('commit') == state['commit'] and build.get('status') == 'errored':
                state['status'] = 'falha_pages'
                save(folder, state)
                raise PublicationError('GitHub Pages falhou ao publicar o commit. O envio já ocorreu; consulte publicacao.json.')
            if build.get('commit') == state['commit'] and build.get('status') == 'built':
                if hash_reader(url) == state['data_sha256']:
                    if client.request('GET', '/git/ref/heads/' + BRANCH)['object']['sha'] != state['commit']:
                        state['status'] = 'substituida_por_outra_atualizacao'
                        save(folder, state)
                        raise PublicationError('Outra atualização avançou gh-pages durante a verificação.')
                    state.update(status='publicado', verified_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
                    save(folder, state)
                    return state
        except (urllib.error.URLError, TimeoutError, OSError):
            pass  # leitura pública transitória; não repetir nenhuma escrita
        if clock() >= deadline:
            state['status'] = 'enviado_verificacao_pendente'
            save(folder, state)
            return state
        sleep(interval)

def publish(client, folder, timeout=600, verifier=verify):
    folder = Path(folder)
    report = json.loads((folder / 'relatorio.json').read_text(encoding='utf-8'))
    if report.get('status') != 'preparado' or report.get('errors'):
        raise PublicationError('Preparação não aprovada; publicação interrompida.')
    data_path = folder / 'site/data.db.gz'
    expected = report['artifacts_sha256']['site/data.db.gz']
    if digest(data_path) != expected:
        raise PublicationError('Arquivo alterado após validação; publicação interrompida.')
    if data_path.stat().st_size >= 100 * 1024 * 1024:
        raise PublicationError('Banco compactado atinge o limite de 100 MiB do GitHub.')
    pages, head, tree, entries = preflight(client)
    data = data_path.read_bytes()
    state = {'status': 'preparando_envio', 'repository': REPO, 'branch': BRANCH,
             'previous_commit': head, 'data_sha256': expected,
             'source_sha256': report['source_sha256'], 'page_url': pages['html_url']}
    save(folder, state)
    blob_sha = git_blob_sha(data)
    if entries.get('data.db.gz', {}).get('sha') == blob_sha:
        state.update(commit=head, status='sem_alteracao')
        save(folder, state)
        return verifier(client, folder, state, timeout=timeout)
    # Uma árvore baseada na atual preserva frontend, domínio e histórico.
    blob = client.request('POST', '/git/blobs', {'content': base64.b64encode(data).decode('ascii'), 'encoding': 'base64'})
    if blob['sha'] != blob_sha:
        raise PublicationError('GitHub recebeu um blob diferente do banco validado.')
    metadata = json.dumps({'source_sha256': report['source_sha256'], 'data_sha256': expected,
                           'items': report['published_items'], 'converter_commit': report['converter_commit']}, indent=2)
    new_tree = client.request('POST', '/git/trees', {'base_tree': tree, 'tree': [
        {'path': 'data.db.gz', 'mode': '100644', 'type': 'blob', 'sha': blob_sha},
        {'path': 'atualizacao.json', 'mode': '100644', 'type': 'blob', 'content': metadata}]})
    commit = client.request('POST', '/git/commits', {
        'message': 'Atualiza base CATMAS (%d itens; CSV %s)' % (report['published_items'], report['source_sha256'][:12]),
        'tree': new_tree['sha'], 'parents': [head]})
    state.update(commit=commit['sha'], status='commit_preparado')
    save(folder, state)
    if client.request('GET', '/git/ref/heads/' + BRANCH)['object']['sha'] != head:
        raise PublicationError('gh-pages mudou durante a preparação; execute novamente com o CSV. Nenhuma branch alterada.')
    # Não usar force: se houver concorrência depois da checagem, o fast-forward falha.
    state['status'] = 'envio_em_andamento'
    save(folder, state)
    client.request('PATCH', '/git/refs/heads/' + BRANCH, {'sha': commit['sha'], 'force': False})
    state['status'] = 'enviado'
    save(folder, state)
    return verifier(client, folder, state, timeout=timeout)

def token():
    value = os.environ.get('CATMAS_GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not value and shutil.which('gh'):
        result = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            value = result.stdout.strip()
    if not value:
        value = getpass.getpass('Token GitHub (entrada oculta; não será salvo): ').strip()
    if not value:
        raise PublicationError('Autenticação GitHub ausente.')
    return value

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', nargs='?')
    parser.add_argument('--saida')
    parser.add_argument('--encoding', default='utf-8-sig')
    parser.add_argument('--delimiter', choices=[',', ';', '\t', '|'])
    parser.add_argument('--verificar', metavar='PASTA', help='Verifica um envio anterior, sem novo commit')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    try:
        if args.timeout < 0:
            raise PublicationError('Timeout deve ser zero ou positivo.')
        if args.verificar:
            folder = Path(args.verificar)
            state = json.loads((folder / 'publicacao.json').read_text(encoding='utf-8'))
            if state.get('repository') != REPO or state.get('branch') != BRANCH or not state.get('commit'):
                raise PublicationError('Registro não corresponde a um envio CATMAS válido.')
            client = GitHub(token())
            pages, _, _, _ = preflight(client)
            state['page_url'] = pages['html_url']
            result = verify(client, folder, state, timeout=args.timeout)
        else:
            source = args.csv or input('Caminho completo do CSV do KNIME: ').strip().strip('"')
            folder = Path(args.saida) if args.saida else ROOT / 'resultados' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            print('Validando CSV e preparando base...')
            report = prepare(source, folder, args.encoding, args.delimiter)
            if report['status'] != 'preparado':
                print('Publicação bloqueada. Confira ' + str(folder / 'relatorio.json'))
                return 2
            print('Base validada. Atualizando GitHub e aguardando publicação...')
            result = publish(GitHub(token()), folder, timeout=args.timeout)
        print(result['status'] + ': ' + result['page_url'])
        print('Registro: ' + str(folder.resolve() / 'publicacao.json'))
        if result['status'] != 'publicado':
            print('Envio realizado; publicação ainda não confirmada. Use --verificar com a pasta acima.')
            return 3
        return 0
    except (PublicationError, ValueError, OSError, EOFError, KeyboardInterrupt,
            csv.Error, sqlite3.Error, subprocess.CalledProcessError) as error:
        print('Atualização interrompida: ' + str(error), file=sys.stderr)
        print('Se existir publicacao.json, confira o estado do envio antes de executar novamente.', file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
