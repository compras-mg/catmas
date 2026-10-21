import copy
import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('di', ROOT/'deployment/windows/diferencas_incrementais.py')
di = importlib.util.module_from_spec(spec); spec.loader.exec_module(di)


def database(path, rows, extra=True):
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE items(item_id INTEGER,codigo TEXT,tipo TEXT,spec TEXT,situacao TEXT,servico_id INTEGER'+(',material_nome TEXT' if extra else '')+')')
        for row in rows:
            c.execute('INSERT INTO items VALUES('+','.join('?' for _ in row)+')',row)


class UnitTests(unittest.TestCase):
    def test_values_identity_schema(self):
        with tempfile.TemporaryDirectory() as t:
            a,b=Path(t)/'a.db',Path(t)/'b.db'
            database(a,[(15,'000000248','MATERIAL','CAPSULA','Ativo',9881,None),
                        (16,'000000249','MATERIAL','X','Ativo',8,''),
                        (17,'000000250','MATERIAL','X','Ativo',8,''),
                        (18,'000000251','MATERIAL','X','Ativo',8,'')])
            database(b,[(15,'000000248','MATERIAL','CÁPSULA','Inativo',9882,''),
                        (16,'000000249','SERVICO','Y','Ativo',8,''),
                        (17,'000000999','MATERIAL','Y','Ativo',8,''),
                        (19,'000000252','MATERIAL','X','Ativo',8,'')])
            source={'before':'a'*40,'after':'b'*40,'published_before':'2026-10-20T12:00:00Z','published_after':'2026-10-21T12:00:00Z'}
            rows,s=di.compare(a,b,source,{'converter_commit':'a'},{'converter_commit':'b'})
            self.assertEqual(len(rows),4)
            self.assertEqual(rows[0][1][5],'somente_diacriticos')
            self.assertEqual(s['appeared'],[19]);self.assertEqual(s['disappeared'],[18])
            self.assertEqual(len(s['identity_mismatches']),2)
            self.assertIn([None,''],[[r[1][3],r[1][4]] for r in rows])
            shards=[{'schema':1,'sources':[],'items':{}} for _ in range(8)]
            di.append(shards,source,rows); old=copy.deepcopy(shards)
            di.append(shards,source,rows);self.assertEqual(old,shards)
            c=Path(t)/'c.db';database(c,[(15,'000000248','MATERIAL','CÁPSULA','Inativo',9882)],False)
            _,s=di.compare(b,c,source,{},{});self.assertTrue(s['schema_changed'])
            self.assertEqual(s['fields_missing_after'],['material_nome'])
            empty,s=di.compare(b,b,source,{},{});self.assertFalse(empty)

    def test_verification_no_confirmation_on_failure(self):
        m={'content_differences':{'sha256':{'base-diffs-v1/0.json':hashlib.sha256(b'good').hexdigest()}}}
        with patch.object(di.urllib.request,'urlopen',return_value=io.BytesIO(b'bad')):
            with self.assertRaises(di.DifferenceError):di.verify_content(m,'https://example.test/',timeout=0)
        with patch.object(di.urllib.request,'urlopen',return_value=io.BytesIO(b'good')):
            di.verify_content(m,'https://example.test/',timeout=0)

    def test_scheduled_routine_calls_comparison_and_confirms_last(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);folder=root/'lote';folder.mkdir()
            p=types.ModuleType('publicar_catmas');p.PublishError=RuntimeError;p.URL='https://example.test/'
            e=types.ModuleType('extrair_catmas');e.save_json=di.save
            h=types.ModuleType('build_history_integrado')
            dc=types.ModuleType('diferencas_consumidores')
            modules={'publicar_catmas':p,'extrair_catmas':e,'build_history_integrado':h,
                     'diferencas_incrementais':di,'diferencas_consumidores':dc}
            s=importlib.util.spec_from_file_location('routine_test',ROOT/'deployment/windows/rotina_integrada.py')
            r=importlib.util.module_from_spec(s)
            with patch.dict(sys.modules,modules):s.loader.exec_module(r)
            r.STATE=root;r.DIFF_STATE=root/'diff'
            metadata={'cycle_id':'new','content_differences':{'sha256':{}}}
            receipt={'commit':'a'*40,'metadata':metadata,'requested_cycle':'new','last_processed':'b'*40}
            with patch.object(r,'publish',return_value=receipt) as publish, patch.object(r,'verify',side_effect=RuntimeError('Pages delayed')):
                with self.assertRaises(RuntimeError):r.finish(object(),folder,metadata)
                publish.assert_called_once()
            self.assertFalse((root/'sucesso.json').exists());self.assertFalse((root/'diff/confirmado.json').exists())
            with patch.object(r,'publish',return_value=receipt),patch.object(r,'verify'),patch.object(di,'verify_content',side_effect=RuntimeError('hash mismatch')):
                with self.assertRaises(RuntimeError):r.finish(object(),folder,metadata)
            self.assertFalse((root/'diff/confirmado.json').exists())
            with patch.object(r,'publish',return_value=receipt),patch.object(r,'verify'),patch.object(di,'verify_content'):
                r.finish(object(),folder,metadata)
            self.assertEqual(json.loads((root/'diff/confirmado.json').read_text())['requested_cycle'],'new')


class LocalGit:
    def git_run(self,args,cwd,payload=None):
        p=subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.test',*args],
                         cwd=cwd,input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if p.returncode:raise RuntimeError('git '+args[0]+' failed')
        return p.stdout


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.gh=LocalGit();self.remote=self.root/'remote.git';self.remote.mkdir()
        self.gh.git_run(['init','--bare','--quiet'],self.remote)
        self.seed=self.root/'seed';self.seed.mkdir();self.gh.git_run(['init','--quiet'],self.seed)
        self.gh.git_run(['checkout','-b','gh-pages'],self.seed)
        self.p=types.SimpleNamespace(GIT_URL=str(self.remote),BRANCH='gh-pages')
        self.make_folder('baseline','CAPSULA',0)
        for name in ('data.db.gz','history.db.gz','atualizacao.json'):
            (self.seed/name).write_bytes((self.root/'baseline'/name).read_bytes())
        for name in ('index.html','history.html'):(self.seed/name).write_text('MARK')
        self.seed_commit('baseline');self.anchor=self.head()
        self.original_bootstrap=di.BOOTSTRAP;di.BOOTSTRAP=self.anchor
        sources=[{'before':'a'*40,'after':'8870e44eb965cf534a2246f9bcaf7c0befeaef86','published_before':'2026-09-22T12:00:00Z','published_after':'2026-10-07T01:19:51Z'},
                 {'before':'8870e44eb965cf534a2246f9bcaf7c0befeaef86','after':self.anchor,'published_before':'2026-10-07T01:19:51Z','published_after':'2026-10-20T12:00:00Z'}]
        (self.seed/'base-diffs-v1').mkdir()
        self.old={'schema':1,'sources':sources,'items':{'15':[['legacy','000000248','spec','OLD','CAPSULA','outra_diferenca',1]]}}
        for i in range(8):di.save(self.seed/f'base-diffs-v1/{i}.json',self.old if i==7 else dict(schema=1,sources=sources,items={}))
        self.seed_commit('legacy recovery')
        self.state=self.root/'state'

    def tearDown(self):
        di.BOOTSTRAP=self.original_bootstrap;self.tmp.cleanup()

    def head(self):return self.gh.git_run(['rev-parse','refs/heads/gh-pages'],self.remote).decode().strip()

    def seed_commit(self,msg):
        self.gh.git_run(['add','.'],self.seed);self.gh.git_run(['commit','--quiet','-m',msg],self.seed)
        self.gh.git_run(['push','--quiet',str(self.remote),'HEAD:refs/heads/gh-pages'],self.seed)

    def make_folder(self,name,text,hour):
        f=self.root/name;f.mkdir()
        database(f/'data.db',[(15,'000000248','MATERIAL',text,'Ativo',9881,'LAMPADA')])
        (f/'data.db.gz').write_bytes(gzip.compress((f/'data.db').read_bytes(),mtime=0))
        (f/'history.db.gz').write_bytes(b'history')
        m={'cycle_id':name,'data_sha256':di.digest(f/'data.db.gz'),'history_sha256':di.digest(f/'history.db.gz'),
           'updated_at':f'2026-10-21T{hour:02}:00:00+00:00','items':1,'converter_commit':'test'}
        di.save(f/'atualizacao.json',m);return f,m

    def publish(self,f,m):return di.publish(self.gh,self.state,f,m,self.p,lambda a,b:(a,b),'MARK',lambda a,b:None)

    def bucket(self):
        return json.loads(self.gh.git_run(['show',self.head()+':base-diffs-v1/7.json'],self.remote))

    def test_accent_retry_and_zero(self):
        f,m=self.make_folder('new','CÁPSULA',1);r=self.publish(f,m)
        b=self.bucket();self.assertEqual(b['sources'][:2],self.old['sources']);self.assertEqual(b['items']['15'][0],self.old['items']['15'][0])
        self.assertEqual(len(b['items']['15']),2)
        self.assertFalse((self.state/'confirmado.json').exists())
        again=self.publish(f,m);self.assertTrue(again['reused']);self.assertEqual(self.bucket(),b)
        di.confirm(self.state,f,again);self.assertTrue((self.state/'confirmado.json').exists())
        f,m=self.make_folder('same','CÁPSULA',2);r=self.publish(f,m)
        self.assertEqual(r['intervals'][-1]['rows'],0);self.assertEqual(len(self.bucket()['sources']),4)
        self.assertEqual(len(self.bucket()['items']['15']),2)

    def test_fail_before_and_after_push(self):
        f,m=self.make_folder('new','CÁPSULA',1);head=self.head()
        with patch.object(di.Repository,'push',side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):self.publish(f,m)
        self.assertEqual(head,self.head());self.assertFalse((self.state/'confirmado.json').exists())
        original=di.Repository.push
        def accepted_then_lost(repo,commit):original(repo,commit);raise RuntimeError('lost response')
        with patch.object(di.Repository,'push',accepted_then_lost):r=self.publish(f,m)
        self.assertTrue(r['reused']);self.assertEqual(len(self.bucket()['items']['15']),2)

    def test_recover_pending_and_concurrent(self):
        f,m=self.make_folder('pending','CÁPSULA',1)
        for name in ('data.db.gz','history.db.gz','atualizacao.json'):(self.seed/name).write_bytes((f/name).read_bytes())
        self.seed_commit('old publisher without differences')
        f,m=self.make_folder('new','CAPSULA 50W',2)
        original=di.Repository.push;conflicted=[]
        def concurrent(repo,commit):
            if not conflicted:
                conflicted.append(True);(self.seed/'unrelated.txt').write_text('preserve')
                self.seed_commit('concurrent interface update')
            return original(repo,commit)
        with patch.object(di.Repository,'push',concurrent):r=self.publish(f,m)
        self.assertEqual(len(r['intervals']),2);self.assertEqual(len(self.bucket()['items']['15']),3)
        self.assertEqual(self.gh.git_run(['show',self.head()+':unrelated.txt'],self.remote),b'preserve')
        sources=self.bucket()['sources'];self.assertEqual(sources[-2]['after'],sources[-1]['before'])

    def test_superseded_pending_is_not_republished(self):
        old,om=self.make_folder('old','OLD',1);new,nm=self.make_folder('new','CÁPSULA',2)
        self.publish(new,nm);head=self.head();result=self.publish(old,om)
        self.assertTrue(result['requested_cycle_superseded']);self.assertEqual(head,self.head())
        self.assertEqual(len(self.bucket()['items']['15']),2)


if __name__=='__main__':unittest.main()
