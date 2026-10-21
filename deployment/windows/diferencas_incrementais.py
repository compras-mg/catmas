"""CATMAS incremental: immutable Git snapshots, append-only differences, CAS push.

Only standard-library dependencies. Invoked by rotina_integrada, never extracts.
The remote checkpoint describes included intervals; the local confirmed marker
is written only after checking the artifacts actually served by Pages.
"""
from __future__ import annotations
import contextlib
import datetime as dt
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
import unicodedata
import urllib.request
import uuid

VERSION = 'catmas-diff-1'
CHECKPOINT = 'base-diffs-v1/processamento.json'
FIELDS = ('spec', 'material_nome', 'situacao', 'material_codigo', 'servico_id',
          'grupo', 'classe', 'natureza', 'agricultura_familiar', 'sustentavel',
          'ok_registro_precos', 'especificacao_longa', 'linhas_fornecimento',
          'elementos_codigos')
BOOTSTRAP = '3d4423269651d452527f4a878cb489412792899a'
LEGACY_FIELDS = set(FIELDS) - {'servico_id', 'linhas_fornecimento', 'elementos_codigos'}


class DifferenceError(RuntimeError):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('wb') as f:
        f.write(encode(obj)); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def kind(a, b):
    if isinstance(a, str) and isinstance(b, str):
        if unicodedata.normalize('NFC', a) == unicodedata.normalize('NFC', b):
            return 'representacao_unicode'
        strip = lambda s: ''.join(c for c in unicodedata.normalize('NFD', s)
                                  if not unicodedata.combining(c))
        if strip(a) == strip(b):
            return 'somente_diacriticos'
    return 'outra_diferenca'


def read_items(path):
    with contextlib.closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise DifferenceError('Base de comparacao com integridade invalida.')
        schema = [list(r) for r in db.execute('PRAGMA table_info(items)')]
        columns = [r[1] for r in schema]
        if not {'item_id', 'codigo', 'tipo'}.issubset(columns):
            raise DifferenceError('Identidade do item indisponivel no esquema.')
        selected = ['item_id', 'codigo', 'tipo'] + [f for f in FIELDS if f in columns]
        items = {}
        for values in db.execute('SELECT ' + ','.join('"' + c + '"' for c in selected) + ' FROM items'):
            row = dict(zip(selected, values)); ident = row['item_id']
            if isinstance(ident, bool) or not isinstance(ident, int) or ident < 1 or ident in items:
                raise DifferenceError('ID de item invalido ou duplicado.')
            if not isinstance(row['codigo'], str) or not re.fullmatch(r'\d{9}', row['codigo']) or row['tipo'] not in ('MATERIAL', 'SERVICO'):
                raise DifferenceError('Codigo/tipo de item invalido.')
            items[ident] = row
        return items, schema


def compare(before, after, source, meta_before, meta_after):
    a, sa = read_items(before); b, sb = read_items(after)
    ca, cb = {r[1] for r in sa}, {r[1] for r in sb}
    common_fields = [f for f in FIELDS if f in ca & cb]
    rows = []; mismatches = []; changed_items = set()
    for ident in sorted(a.keys() & b.keys()):
        old, new = a[ident], b[ident]
        if (old['codigo'], old['tipo']) != (new['codigo'], new['tipo']):
            mismatches.append({'item_id': ident, 'before': [old['codigo'], old['tipo']],
                               'after': [new['codigo'], new['tipo']]})
            continue
        for field in common_fields:
            if old[field] == new[field] and type(old[field]) is type(new[field]):
                continue
            # Existing identifiers use the original JSON separators and SHA256.
            key = json.dumps([source['before'], source['after'], ident, field]).encode()
            row = [hashlib.sha256(key).hexdigest(), new['codigo'], field,
                   old[field], new[field], kind(old[field], new[field])]
            rows.append((ident, row)); changed_items.add(ident)
    summary = {'source': source, 'engine': VERSION, 'rows': len(rows),
               'changed_items': len(changed_items), 'items_before': len(a), 'items_after': len(b),
               'appeared': sorted(b.keys() - a.keys()), 'disappeared': sorted(a.keys() - b.keys()),
               'identity_mismatches': mismatches, 'fields_compared': common_fields,
               'fields_missing_before': sorted(set(FIELDS) & (cb - ca)),
               'fields_missing_after': sorted(set(FIELDS) & (ca - cb)),
               'schema_before': sa, 'schema_after': sb, 'schema_changed': sa != sb,
               'conversion_before': {k: meta_before.get(k) for k in ('converter_commit', 'converter_sha256', 'consulta_sha256')},
               'conversion_after': {k: meta_after.get(k) for k in ('converter_commit', 'converter_sha256', 'consulta_sha256')},
               'limitations': 'Valores publicados; nulos/vazios preservados. Campos ausentes nao comparados. Sem inferencia de autoria, motivo ou evento.'}
    return rows, summary


def append(shards, source, rows):
    """Retain every old source index and record; reject conflicting retry data."""
    for shard in shards:
        if shard.get('schema') != 1 or not isinstance(shard.get('sources'), list) or not isinstance(shard.get('items'), dict):
            raise DifferenceError('Contrato dos arquivos existentes invalido.')
    positions = []
    for shard in shards:
        matches = [i for i, s in enumerate(shard['sources']) if (s['before'], s['after']) == (source['before'], source['after'])]
        if len(matches) > 1:
            raise DifferenceError('Fonte duplicada na base existente.')
        if matches:
            pos = matches[0]
            if shard['sources'][pos] != source:
                raise DifferenceError('Fonte existente com datas divergentes.')
        else:
            pos = len(shard['sources']); shard['sources'].append(dict(source))
        positions.append(pos)
    known = {}
    for bucket, shard in enumerate(shards):
        for ident, records in shard['items'].items():
            if int(ident) % 8 != bucket:
                raise DifferenceError('Item no arquivo incorreto.')
            for row in records:
                if len(row) != 7 or row[0] in known or not 0 <= row[6] < len(shard['sources']):
                    raise DifferenceError('Registro existente invalido ou duplicado.')
                known[row[0]] = (ident, row)
    for ident, record in rows:
        bucket = ident % 8; row = record + [positions[bucket]]
        if row[0] in known:
            if known[row[0]] != (str(ident), row):
                raise DifferenceError('Reexecucao com valores divergentes.')
            continue
        shards[bucket]['items'].setdefault(str(ident), []).append(row)
        known[row[0]] = (str(ident), row)


class Repository:
    def __init__(self, gh, root, git_url, branch):
        self.gh, self.root, self.git_url, self.branch = gh, Path(root), git_url, branch
        self.root.mkdir(parents=True, exist_ok=True)
        if not (self.root / '.git').exists():
            self.run(['init', '--quiet'])
            self.run(['remote', 'add', 'origin', git_url])
            self.run(['config', 'remote.origin.promisor', 'true'])
            self.run(['config', 'remote.origin.partialclonefilter', 'blob:none'])

    def run(self, args, payload=None):
        return self.gh.git_run(args, self.root, payload)

    def fetch(self):
        self.run(['fetch', '--quiet', '--filter=blob:none', '--no-tags', 'origin', 'refs/heads/' + self.branch])
        return self.run(['rev-parse', 'FETCH_HEAD']).decode().strip()

    def exists(self, commit, path):
        # ls-tree is successful with no match for an absent file.
        return bool(self.run(['ls-tree', commit, '--', path]).strip())

    def data(self, commit, path):
        return self.run(['show', commit + ':' + path])

    def json(self, commit, path):
        return json.loads(self.data(commit, path))

    def stamp(self, commit):
        return self.run(['show', '-s', '--format=%cI', commit]).decode().strip()

    def commit(self, parent, files, message):
        self.run(['read-tree', parent])
        for path, content in files.items():
            if isinstance(content, Path):
                blob = self.run(['hash-object', '-w', str(content.resolve())]).decode().strip()
            else:
                blob = self.run(['hash-object', '-w', '--stdin'], content).decode().strip()
            self.run(['update-index', '--add', '--cacheinfo', '100644', blob, path])
        tree = self.run(['write-tree']).decode().strip()
        return self.run(['commit-tree', tree, '-p', parent], (message + '\n').encode()).decode().strip()

    def push(self, commit):
        self.run(['push', '--porcelain', self.git_url, commit + ':refs/heads/' + self.branch])

    def snapshots(self, anchor, head):
        self.run(['merge-base', '--is-ancestor', anchor, head])
        commits = self.run(['log', '--first-parent', '--reverse', '--format=%H', anchor + '..' + head,
                            '--', 'data.db.gz', 'atualizacao.json']).decode().splitlines()
        # Metadata-only finalization commits of our two-commit publication are
        # not new snapshots; cycle id/hash identity deduplicates those commits.
        prior = self.json(anchor, 'atualizacao.json')
        identity = lambda m: (m.get('cycle_id'), m.get('data_sha256'), m.get('updated_at'))
        seen = {identity(prior)}; snapshots = []
        for commit in commits:
            m = self.json(commit, 'atualizacao.json')
            key = identity(m)
            if key in seen:
                continue
            seen.add(key); snapshots.append((commit, m))
        return snapshots


def snapshot(repo, commit, cache):
    """Keep compressed source copies by SHA256, never fill new data from old."""
    meta = repo.json(commit, 'atualizacao.json')
    expected = meta.get('data_sha256')
    if not re.fullmatch('[a-f0-9]{64}', expected or ''):
        raise DifferenceError('Publicacao sem hash verificavel do catalogo.')
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    packed = cache / (expected + '.db.gz'); db = cache / (expected + '.db')
    if not packed.exists() or digest(packed) != expected:
        data = repo.data(commit, 'data.db.gz')
        if hashlib.sha256(data).hexdigest() != expected:
            raise DifferenceError('Hash da base remota divergente.')
        tmp = packed.with_suffix('.part'); tmp.write_bytes(data); os.replace(tmp, packed)
    # Reconstruct SQLite every time, avoiding trust in a stale uncompressed file.
    tmp = db.with_suffix('.part')
    with gzip.open(packed, 'rb') as src, tmp.open('wb') as dst:
        shutil.copyfileobj(src, dst)
    os.replace(tmp, db)
    return db, meta


def load_state(repo, head):
    shards = [repo.json(head, 'base-diffs-v1/' + str(i) + '.json') for i in range(8)]
    if repo.exists(head, CHECKPOINT):
        state = repo.json(head, CHECKPOINT)
        if state.get('schema') != 1:
            raise DifferenceError('Marcador de processamento desconhecido.')
    else:
        # Never rebuild narrow intervals inside the broad historical recovery.
        # Bootstrap only from the validated upper endpoint, not an arbitrary head.
        endpoints = {s['after'] for sh in shards for s in sh['sources']}
        if endpoints != {'8870e44eb965cf534a2246f9bcaf7c0befeaef86', BOOTSTRAP}:
            raise DifferenceError('Cobertura historica mudou; conferir marco inicial.')
        state = {'schema': 1, 'last_processed': BOOTSTRAP, 'engine': VERSION,
                 'legacy_coverage_end': BOOTSTRAP, 'new_fields_from_next_interval': sorted(set(FIELDS)-LEGACY_FIELDS)}
    return shards, state


def build_intervals(repo, head, root):
    shards, state = load_state(repo, head)
    anchor = state['last_processed']; artifacts = {}; intervals = []
    for commit, metadata in repo.snapshots(anchor, head):
        before, ma = snapshot(repo, anchor, Path(root) / 'bases-anteriores')
        after, mb = snapshot(repo, commit, Path(root) / 'bases-anteriores')
        source = {'before': anchor, 'after': commit,
                  'published_before': repo.stamp(anchor), 'published_after': repo.stamp(commit)}
        rows, summary = compare(before, after, source, ma, mb)
        for path in {before, after}:
            path.unlink(missing_ok=True)
        append(shards, source, rows)
        filename = 'base-diffs-v1/intervalos/' + anchor + '-' + commit + '.json'
        artifacts[filename] = encode(summary)
        # Retain a local ledger even if publication later fails.
        save(Path(root) / 'intervalos' / (anchor + '-' + commit + '.json'), summary)
        intervals.append({'before': anchor, 'after': commit, 'rows': len(rows)})
        logging.info('Diferencas %s -> %s: %d campos; %d itens.', anchor[:10], commit[:10], len(rows), summary['changed_items'])
        anchor = commit
    state.update(last_processed=anchor, engine=VERSION)
    for i, shard in enumerate(shards):
        artifacts['base-diffs-v1/' + str(i) + '.json'] = encode(shard)
    artifacts[CHECKPOINT] = encode(state)
    return artifacts, state, intervals


def publish(gh, root, folder, meta, publisher, patch_pages, marker, validate_remote, consumer_patch=None):
    """Single branch ref update makes both commits visible together.

    Snapshot commit has the exact new bases; final commit appends comparisons
    referencing that snapshot SHA. This avoids an impossible self-referencing
    commit hash without exposing an incomplete intermediate branch head.
    """
    root, folder = Path(root), Path(folder)
    repo = Repository(gh, root / 'git', publisher.GIT_URL, publisher.BRANCH)
    receipt_path = folder / 'diferencas-recibo.json'
    for attempt in range(4):
        head = repo.fetch(); current = repo.json(head, 'atualizacao.json')
        shards, checkpoint = load_state(repo, head)
        pending_remote = repo.snapshots(checkpoint['last_processed'], head)
        matches = [(c, m) for c, m in pending_remote if m.get('cycle_id') == meta['cycle_id']]
        already = current.get('cycle_id') == meta['cycle_id'] or bool(matches)
        # A cycle already processed and superseded must never be republished.
        if not already and repo.exists(head, CHECKPOINT):
            all_cycles = repo.snapshots(checkpoint['legacy_coverage_end'], head)
            matches = [(c, m) for c, m in all_cycles if m.get('cycle_id') == meta['cycle_id']]
            already = bool(matches)
        superseded = (not already and dt.datetime.fromisoformat(current['updated_at'].replace('Z', '+00:00')) >
                      dt.datetime.fromisoformat(meta['updated_at'].replace('Z', '+00:00')))
        if superseded:
            logging.info('Lote pendente ultrapassado por publicacao mais recente; preservar lote local e recuperar intervalos remotos.')
            target = head; served = current
        elif already:
            found = matches[0][1] if matches else current
            if any(found.get(k) != meta[k] for k in ('data_sha256', 'history_sha256')):
                raise DifferenceError('Mesmo ciclo remoto com hashes divergentes.')
            target = head; served = current
        else:
            validate_remote(meta, current)
            pages = [repo.data(head, path).decode('utf-8') for path in ('index.html', 'history.html')]
            if any(marker not in page for page in pages):
                raise DifferenceError('Paginas sem marcador da rotina integrada; revisar antes de publicar.')
            index, history = patch_pages(*pages)
            files = {'data.db.gz': folder / 'data.db.gz', 'history.db.gz': folder / 'history.db.gz',
                     'atualizacao.json': encode(meta), 'index.html': index.encode(), 'history.html': history.encode()}
            target = repo.commit(head, files, 'CATMAS bases do ciclo ' + meta['cycle_id'])
            served = dict(meta)
        artifacts, state, intervals = build_intervals(repo, target, root)
        client_files = {}
        if consumer_patch is not None:
            names = ('base-comparison-v1.js', 'history.html', 'rastreador/worker.js', 'rastreador/content.js')
            originals = {name: repo.data(target, name).decode('utf-8') for name in names}
            patched = consumer_patch(originals)
            client_files = {name: body.encode('utf-8') for name, body in patched.items() if body != originals[name]}
        if (already or superseded) and not intervals and not client_files and repo.exists(head, CHECKPOINT):
            hashes = current.get('content_differences', {}).get('sha256')
            if not hashes:
                raise DifferenceError('Ciclo processado sem manifesto de verificacao.')
            receipt = {'commit': head, 'requested_cycle': meta['cycle_id'], 'metadata': current,
                       'last_processed': state['last_processed'], 'intervals': [], 'reused': True,
                       'requested_cycle_superseded': superseded}
            save(receipt_path, receipt)
            return receipt
        hashes = {path: hashlib.sha256(content).hexdigest() for path, content in artifacts.items()}
        if consumer_patch is not None:
            hashes.update({name: hashlib.sha256(body.encode('utf-8')).hexdigest() for name, body in patched.items()})
        artifacts.update(client_files)
        served['content_differences'] = {'schema': 1, 'engine': VERSION, 'last_processed': state['last_processed'],
                                        'sha256': hashes, 'new_intervals': intervals}
        artifacts['atualizacao.json'] = encode(served)
        final = repo.commit(target, artifacts, 'CATMAS comparar e preservar diferencas; ciclo ' + served['cycle_id'])
        receipt = {'commit': final, 'requested_cycle': meta['cycle_id'], 'metadata': served,
                   'last_processed': state['last_processed'], 'intervals': intervals,
                   'requested_cycle_superseded': superseded}
        save(receipt_path, receipt)
        try:
            repo.push(final)
        except Exception:
            # A push may have succeeded despite loss of the response. Re-read
            # remote state on every retry; never force, never reuse stale shards.
            new_head = repo.fetch()
            if new_head == head:
                raise
            logging.info('Publicacao remota avancou; reler e recuperar intervalos pendentes.')
            continue
        confirmed_head = repo.fetch()
        if confirmed_head != final:
            logging.info('Outro ciclo avancou apos envio; reconciliar com o novo estado.')
            continue
        return receipt
    raise DifferenceError('Publicacao concorrente persistente; lote preservado para retry.')


def verify_content(metadata, url, timeout=600):
    expected = metadata['content_differences']['sha256']
    deadline = time.monotonic() + timeout
    while True:
        try:
            for path, checksum in expected.items():
                req = urllib.request.Request(url + path + '?v=' + checksum, headers={'Cache-Control': 'no-cache'})
                h = hashlib.sha256()
                with urllib.request.urlopen(req, timeout=60) as f:
                    for block in iter(lambda: f.read(1024 * 1024), b''):
                        h.update(block)
                if h.hexdigest() != checksum:
                    raise DifferenceError('Comparacao servida ainda divergente.')
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise DifferenceError('Envio preservado; comparacoes no Pages ainda nao confirmadas. Use retry.') from None
            logging.info('Aguardando os arquivos de comparacao no Pages.')
            time.sleep(15)


def confirm(root, folder, receipt):
    """Call ONLY after verify(meta) and verify_content(meta) both succeeded."""
    record = dict(receipt, status='sucesso', folder=str(Path(folder).resolve()),
                  confirmed_at=dt.datetime.now(dt.timezone.utc).isoformat())
    save(Path(root) / 'confirmado.json', record)
    save(Path(root) / 'execucoes' / (receipt['requested_cycle'] + '.json'), record)
    return record
