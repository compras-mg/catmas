# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""CATMAS: publicar buscador e historico como um unico lote validado."""
import argparse, base64, contextlib, datetime as dt, gzip, hashlib, importlib.util
import json, logging, os, shutil, sqlite3, subprocess, sys, tempfile, time, urllib.request, uuid, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import publicar_catmas as p
import extrair_catmas as e
import build_history_integrado as h
import diferencas_incrementais as di
import diferencas_consumidores as dc

BASE = Path(__file__).resolve().parent
HIST = Path(os.environ.get('USERPROFILE', str(Path.home()))) / 'Documents/CATMAS-Historico-Python-v1'
STATE = BASE / 'publicacao-integrada'
DIFF_STATE = STATE / 'diferencas'
FILES = {'data.db.gz', 'history.db.gz', 'atualizacao.json', 'index.html', 'history.html'}
INDEX_SHA = '659f65bdab03ae8124f81a43a69b623e96a1baad'
HISTORY_SHA = '2a341cf047f5d4e55c581c4bcecfb068b347535a'
MARKER = 'CATMAS_CICLO_INTEGRADO_V1'

def history_module():
    path = HIST / 'historico_catmas.py'
    if not path.is_file(): raise p.PublishError('Extrator do historico nao encontrado na pasta instalada.')
    spec = importlib.util.spec_from_file_location('historico_local', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def uv():
    exe = shutil.which('uv.exe') or shutil.which('uv')
    if not exe: raise p.PublishError('uv nao encontrado.')
    return str(Path(exe).resolve())

def extract(scheduled):
    for script, args in [(BASE/'extrair_catmas.py', []), (HIST/'historico_catmas.py', ['extract'])]:
        command = [uv(), 'run', '--offline', '--script', str(script), *args]
        if scheduled: command.append('--scheduled')
        logging.info('Executar %s; interromper o ciclo se falhar.', script.name)
        if subprocess.run(command, cwd=script.parent).returncode:
            raise p.PublishError('Extracao falhou; nenhum banco foi enviado.')

def align_catalog(folder, cycle):
    """O estado atual vem do buscador do mesmo ciclo; eventos continuam originais."""
    with contextlib.closing(sqlite3.connect(folder/'history.db')) as db, db:
        db.execute('ATTACH DATABASE ? AS catalog', (str(folder/'data.db'),))
        mapping = {'code':'codigo', 'item_type':'tipo', 'material_service_id':'servico_id',
          'material_service_code':'material_codigo', 'material_service_name':'material_nome',
          'current_version':'versao', 'current_status_label':'situacao', 'created_at':'data_criacao',
          'updated_at':'data_ultima_atualizacao', 'current_specification':'spec'}
        # Nao inventar equivalencia entre situacao numerica e rotulo do catalogo.
        # Ler o catalogo uma vez e atualizar pela chave primaria do historico.
        # O catalogo publicado nao tem indice em item_id: subconsultas correlatas
        # fariam uma varredura completa para cada item.
        cursor=db.execute('SELECT '+','.join(mapping.values())+',item_id FROM catalog.items')
        statement='UPDATE items SET current_status_code=NULL,'+','.join(key+'=?' for key in mapping)+' WHERE item_id=?'
        count=0
        while True:
            rows=cursor.fetchmany(1000)
            if not rows: break
            db.executemany(statement,rows)
            count+=len(rows)
            if count%25000==0: logging.info('Alinhamento do historico: %d itens atuais.',count)
        logging.info('Alinhamento concluido: %d itens atuais; validar correspondencia.',count)
        missing = db.execute('SELECT COUNT(*) FROM catalog.items c LEFT JOIN items i ON i.item_id=c.item_id WHERE i.item_id IS NULL').fetchone()[0]
        mismatch = db.execute('SELECT COUNT(*) FROM catalog.items c JOIN items i ON i.item_id=c.item_id WHERE i.code IS NOT c.codigo OR i.current_version IS NOT c.versao OR i.current_specification IS NOT c.spec').fetchone()[0]
        if missing or mismatch: raise p.PublishError('Os bancos nao correspondem nos itens atuais.')
        db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('cycle_id', cycle))
        result = h.validate(db)
    h.write_gzip(folder/'history.db', folder/'history.db.gz')
    with gzip.open(folder/'history.db.gz','rb') as f:
        digest = hashlib.sha256()
        for block in iter(lambda:f.read(1024*1024),b''): digest.update(block)
    if digest.hexdigest()!=e.sha256(folder/'history.db'): raise p.PublishError('Compactacao do historico divergente.')
    if (folder/'history.db.gz').stat().st_size>=100_000_000: raise p.PublishError('Historico compactado excede limite de envio.')
    return result

def prepare(scheduled=False):
    mod = history_module()
    folder = STATE / ('lote-'+uuid.uuid4().hex); folder.mkdir()
    with e.output_lock(p.DEFAULT_OUTPUT), mod.output_lock(HIST/'saida/processo'):
        catalog = p.check_extraction(); report = mod.read_success()
        # Preparacao manual usa apenas extracoes proximas; nenhum lote antigo silencioso.
        a=dt.datetime.fromisoformat(catalog['inicio']); b=dt.datetime.fromisoformat(report['inicio'])
        if abs((a-b).total_seconds())>3600:
            raise p.PublishError('Extracoes distantes mais de uma hora. Use EXTRAIR-E-PUBLICAR-CONJUNTO.cmd.')
        result = p.build_database(p.DEFAULT_OUTPUT, folder)
        if result['rows']!=catalog['registros']: raise p.PublishError('Contagem do buscador divergente.')
        archive = folder/'csv-historico.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
            for file in report['arquivos']:
                z.write(Path(report['pasta'])/file['arquivo'], file['arquivo'])
    cycle = uuid.uuid4().hex
    import csv
    csv.field_size_limit(30_000_000)
    logging.info('Converter historico: carregar eventos, solicitacoes e versoes dos CSVs validados.')
    h.build(archive, folder/'history.db', folder/'history.db.gz', folder/'data.db')
    logging.info('Banco historico convertido; alinhar estado atual com o buscador deste ciclo.')
    history = align_catalog(folder, cycle)
    if history['events']!=report['arquivos'][0]['registros']: raise p.PublishError('Eventos do historico divergentes do lote CSV.')
    finished=max(dt.datetime.fromisoformat(catalog['fim']),dt.datetime.fromisoformat(report['fim'])).isoformat()
    meta={'schema_version':2, 'cycle_id':cycle, 'updated_at':finished,
      'source_sha256':catalog['sha256'], 'data_sha256':result['data_sha256'], 'items':result['items'],
      'converter_commit':p.CONVERTER, 'converter_sha256':e.sha256(BASE/'conversor_original.py'),
      'consulta_sha256':catalog['consulta_sha256'], 'history_sha256':e.sha256(folder/'history.db.gz'),
      'history_source_sha256':e.sha256(archive), 'history_counts':history,
      'catalog_extracted_at':catalog['fim'], 'history_extracted_at':report['fim'],
      'history_converter_commit':'8190b5ed1334fb2203aeef4fd823d70356f26944'}
    e.save_json(folder/'atualizacao.json', meta)
    e.save_json(STATE/'pendente.json', {'folder':str(folder.resolve()),'metadata':meta})
    logging.info('Par preparado: %s; %d itens; %d eventos.',cycle,result['items'],history['events'])
    # Apenas os bancos compactados e metadados poderao entrar no commit.
    return folder, meta

def pending():
    record = p.read_json(STATE/'pendente.json'); folder=Path(record['folder']).resolve()
    if folder.parent!=STATE.resolve(): raise p.PublishError('Pasta pendente invalida.')
    meta=p.read_json(folder/'atualizacao.json')
    if meta!=record['metadata']: raise p.PublishError('Metadados preparados foram alterados.')
    for file,key in [('data.db.gz','data_sha256'),('history.db.gz','history_sha256')]:
        if e.sha256(folder/file)!=meta[key]: raise p.PublishError('Banco preparado foi alterado.')
    return folder,meta

def patch_pages(index, history):
    if MARKER not in index:
        old='  const PUBLICATION_UPDATED_AT = publication?.updated_at;'
        if index.count(old)!=1: raise p.PublishError('Trecho de metadados do buscador mudou.')
        index=index.replace(old, '''  // CATMAS_CICLO_INTEGRADO_V1
  if (!publication?.cycle_id || !/^[a-f0-9]{64}$/.test(publication.history_sha256)) {
    throw new Error("Não foi possível confirmar o ciclo conjunto. Recarregue a página.");
  }
  const PUBLICATION_UPDATED_AT = publication?.updated_at;''')
        index=index.replace('const HISTORY_PAGE_VERSION = "20260730-2";', 'const HISTORY_PAGE_VERSION = publication.cycle_id;')
        old='&v=${HISTORY_PAGE_VERSION}&origem=historico'
        if index.count(old)!=2: raise p.PublishError('Links do historico mudaram.')
        index=index.replace(old, '&v=${HISTORY_PAGE_VERSION}&ciclo=${publication.cycle_id}&origem=historico')
    if MARKER not in history:
        old='  const HISTORY_DATABASE_VERSION = "20260729-1";'
        if history.count(old)!=1: raise p.PublishError('Versao do historico mudou.')
        history=history.replace(old, '''  // CATMAS_CICLO_INTEGRADO_V1
  let publication;
  async function loadPublication() {
    const response = await fetch("atualizacao.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Não foi possível confirmar a atualização conjunta.");
    const value = await response.json();
    if (!/^[a-f0-9]{32}$/.test(value.cycle_id || "") || !/^[a-f0-9]{64}$/.test(value.history_sha256 || ""))
      throw new Error("Metadados do histórico inválidos. Recarregue a página.");
    const expected = new URLSearchParams(location.search).get("ciclo");
    if (expected && expected !== value.cycle_id)
      throw new Error("O catálogo foi atualizado. Volte ao buscador e recarregue para consultar o mesmo ciclo.");
    publication = value;
  }''')
        old='    const response = await fetch(url);'
        if history.count(old)!=1: raise p.PublishError('Carregamento do historico mudou.')
        history=history.replace(old,'    const response = await fetch(url, { cache: "no-store" });')
        old='    const gzipBytes = new Uint8Array(await response.arrayBuffer());'
        history=history.replace(old,old+'''
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", gzipBytes));
    const received = Array.from(digest, byte => byte.toString(16).padStart(2, "0")).join("");
    if (received !== publication.history_sha256)
      throw new Error("A base do histórico ainda não corresponde ao ciclo publicado. Recarregue em alguns instantes.");''')
        old='      const bytes = await loadCompressedDbBytes(`history.db.gz?v=${HISTORY_DATABASE_VERSION}`);'
        if history.count(old)!=1: raise p.PublishError('URL do banco historico mudou.')
        history=history.replace(old, '''      await loadPublication();
      const bytes = await loadCompressedDbBytes(`history.db.gz?v=${publication.history_sha256}`);''')
    if index.count(MARKER)!=1 or history.count(MARKER)!=1:
        raise p.PublishError('Marcadores das paginas divergentes.')
    return index,history

def remote_file(gh, path, head):
    obj=gh.api('repos/'+p.REPO+'/contents/'+path+'?ref='+head)
    return base64.b64decode(obj['content']).decode('utf-8'),obj['sha']

def validate_remote(meta, current):
    if dt.datetime.fromisoformat(current['updated_at'].replace('Z','+00:00'))>dt.datetime.fromisoformat(meta['updated_at']):
        raise p.PublishError('Existe um lote mais recente no site. Reenvio antigo bloqueado.')
    if meta['items']<int(current['items'])*.9: raise p.PublishError('Queda superior a 10% nos itens; conferir antes de publicar.')
    previous=current.get('history_counts',{})
    if previous.get('events') and meta['history_counts']['events']<int(previous['events'])*.9:
        raise p.PublishError('Queda superior a 10% nos eventos; conferir antes de publicar.')

def publish(gh, folder, meta):
    return di.publish(gh, DIFF_STATE, folder, meta, p, patch_pages, MARKER, validate_remote, dc.patch)

def finish(gh, folder, meta):
    receipt=publish(gh,folder,meta)
    served=receipt['metadata']
    e.save_json(STATE/'ultimo-envio.json',receipt)
    verify(served)
    di.verify_content(served,p.URL)
    confirmed=di.confirm(DIFF_STATE,folder,receipt)
    e.save_json(STATE/'sucesso.json',confirmed)
    logging.info('SUCESSO: ciclo servido %s; comparacoes conferidas ate %s; ciclo solicitado %s.',
                 served['cycle_id'],receipt['last_processed'],meta['cycle_id'])
    return receipt

def resume_pending(gh):
    path=STATE/'pendente.json'
    if not path.exists(): return
    folder,meta=pending()
    success=STATE/'sucesso.json'
    if success.exists():
        record=p.read_json(success)
        # Old successful cycles may predate the comparison integration.
        if record.get('requested_cycle',record.get('metadata',{}).get('cycle_id'))==meta['cycle_id']:
            return
    logging.info('Retomar lote pendente antes de iniciar outra extracao: %s.',meta['cycle_id'])
    finish(gh,folder,meta)

def verify(meta, timeout=600):
    limit=time.monotonic()+timeout
    while True:
        try:
            req=urllib.request.Request(p.URL+'atualizacao.json?v='+uuid.uuid4().hex,headers={'Cache-Control':'no-cache'})
            with urllib.request.urlopen(req,timeout=25) as f: current=json.load(f)
            if all(current.get(k)==meta[k] for k in ('cycle_id','data_sha256','history_sha256')):
                for file,key in [('data.db.gz','data_sha256'),('history.db.gz','history_sha256')]:
                    digest=hashlib.sha256()
                    req=urllib.request.Request(p.URL+file+'?v='+meta[key],headers={'Cache-Control':'no-cache'})
                    with urllib.request.urlopen(req,timeout=60) as f:
                        for block in iter(lambda:f.read(1024*1024),b''): digest.update(block)
                    if digest.hexdigest()!=meta[key]: raise p.PublishError('Banco servido ainda divergente.')
                for page in ('index.html','history.html'):
                    with urllib.request.urlopen(p.URL+page+'?v='+meta['cycle_id'],timeout=25) as f: body=f.read().decode('utf-8')
                    if MARKER not in body: raise p.PublishError('Pagina nova ainda nao disponivel.')
                return
        except Exception as ex: logging.info('Aguardando Pages (%s); nao reenviar dados.',type(ex).__name__)
        if time.monotonic()>=limit: raise p.PublishError('Envio feito; Pages ainda nao confirmado. Use REENVIAR-CONJUNTO.cmd.')
        time.sleep(30)

def schedule():
    import ativar_publicacao_1230 as a
    e.credentials(scheduled=True); history_module().credentials(scheduled=True)
    report=p.read_json(STATE/'sucesso.json')
    if report.get('status')!='sucesso': raise p.PublishError('Primeiro confirmar uma publicacao conjunta manual.')
    gh=p.GitHub();gh.ready();verify(report['metadata'],timeout=1)
    tool=str(Path(os.environ['SystemRoot'])/'System32/schtasks.exe')
    # Nunca deixar duas tarefas de historico/buscador concorrentes.
    test=subprocess.run([tool,'/Query','/TN','CATMAS-Historico-Python-0600-1230','/XML'],capture_output=True)
    if test.returncode==0: raise p.PublishError('Existe tarefa separada de historico; conferir antes de substituir o agendamento.')
    result=subprocess.run([tool,'/Query','/TN',a.TASK_NAME,'/XML'],capture_output=True)
    if result.returncode: raise p.PublishError('Tarefa do buscador nao encontrada.')
    root=a.decode_xml(result.stdout); signature=a.signature(root)
    if len(signature)!=2 or any(x[1]!='weekdays' for x in signature): raise p.PublishError('Horarios/dias diferentes do esperado.')
    q=lambda name:root.find('.//'+a.TAG+name)
    old=subprocess.list2cmdline(['run','--offline','--script',str(BASE/'publicar_catmas.py'),'all','--scheduled'])
    new=subprocess.list2cmdline(['run','--offline','--script',str(BASE/'rotina_integrada.py'),'all','--scheduled'])
    if len(root.findall('.//'+a.TAG+'Exec'))!=1 or q('Arguments') is None or q('Arguments').text not in (old,new):
        raise p.PublishError('Acao da tarefa inesperada. Nenhuma tarefa alterada.')
    if q('Command') is None or os.path.normcase(q('Command').text)!=os.path.normcase(uv()) or q('WorkingDirectory').text!=str(BASE) or q('LogonType').text!='InteractiveToken':
        raise p.PublishError('Executavel, usuario ou pasta da tarefa inesperados.')
    backup=BASE/'logs'/('tarefa-antes-integracao-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.xml')
    backup.write_bytes(result.stdout)
    q('Arguments').text=new
    q('Description').text='CATMAS buscador e historico: extrair, validar e publicar juntos; 06h e 12h30 dias uteis Brasilia.'
    path=STATE/'tarefa-integrada.xml';ET.ElementTree(root).write(path,encoding='utf-16',xml_declaration=True)
    result=subprocess.run([tool,'/Create','/TN',a.TASK_NAME,'/XML',str(path),'/F'],capture_output=True)
    if result.returncode: raise p.PublishError('Windows recusou atualizar tarefa; codigo '+str(result.returncode))
    result=subprocess.run([tool,'/Query','/TN',a.TASK_NAME,'/XML'],capture_output=True)
    if result.returncode: raise p.PublishError('Consulta da tarefa apos alteracao falhou.')
    after=a.decode_xml(result.stdout)
    if any(after.find('.//'+a.TAG+key) is None or after.find('.//'+a.TAG+key).text!=q(key).text for key in ('UserId','LogonType','RunLevel','Command','WorkingDirectory','Arguments')) or a.signature(after)!=signature:
        raise p.PublishError('Tarefa alterada, mas conferencia falhou; consultar Agendador antes de repetir.')
    logging.info('SUCESSO: tarefa conjunta ativa; 06h e 12h30 dias uteis. Backup: %s.',backup)

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['all','prepare','convert','retry','schedule']);parser.add_argument('--scheduled',action='store_true')
    args=parser.parse_args(argv);STATE.mkdir(exist_ok=True)
    log=BASE/'logs'/('integrado-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.log')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s',handlers=[logging.FileHandler(log,encoding='utf-8'),logging.StreamHandler(sys.stdout)],force=True)
    try:
        if args.scheduled and dt.datetime.now(e.BRASILIA).weekday()>4: logging.info('Fim de semana; ignorado.');return 0
        # Mesma trava que o publicador antigo: impede envio simultaneo pelo agendamento existente.
        p.STATE.mkdir(exist_ok=True)
        with e.output_lock(p.STATE/'processo'):
            if args.mode=='schedule': schedule();return 0
            gh=None
            if args.mode not in ('prepare','convert'): gh=p.GitHub();gh.ready()
            if args.mode=='all': resume_pending(gh)
            if args.mode in ('prepare','convert') and (STATE/'pendente.json').exists():
                previous=p.read_json(STATE/'pendente.json')['metadata']['cycle_id']
                success=p.read_json(STATE/'sucesso.json') if (STATE/'sucesso.json').exists() else {}
                if success.get('requested_cycle',success.get('metadata',{}).get('cycle_id'))!=previous:
                    raise p.PublishError('Ha lote pendente. Execute retry antes de preparar outro.')
            if args.mode in ('all','prepare'): extract(args.scheduled)
            folder,meta=pending() if args.mode=='retry' else prepare(args.scheduled)
            if args.mode in ('prepare','convert'): logging.info('SUCESSO: par preparado; nada publicado; agendamento intacto.');return 0
            finish(gh,folder,meta)
        return 0
    except (p.PublishError,e.ExtractionError,h.HistoryValueError,di.DifferenceError) as ex: logging.error('FALHA: %s',ex);return 1
    except KeyboardInterrupt: logging.error('Interrompido. Conferir estado com REENVIAR-CONJUNTO.cmd.');return 130
    except Exception as ex:
        import traceback
        frames=traceback.extract_tb(ex.__traceback__)
        trace=' > '.join(Path(f.filename).name+':'+str(f.lineno)+' ('+f.name+')' for f in frames)
        logging.error('FALHA: %s; etapas %s; valores e mensagem bruta omitidos.',type(ex).__name__,trace);return 1
    finally: print('Log:',log)

if __name__=='__main__': sys.exit(main())
