"""Reviewed catalog corrections must leave operating data and later edits intact."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backend.app import create_app
from backend.catalog_adjustments import apply_adjustments,read_adjustments
from backend.db import get_db


class CatalogAdjustmentTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory(prefix='erp-catalog-fix-')
        self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        self.app=create_app({'TESTING':True,'DATABASE':str(self.root/'erp.sqlite3'),'SECRET_KEY':'catalog-fix-test-key'})
        self.client=self.app.test_client()
        login=self.client.post('/api/setup',json={'nome':'Admin teste','username':'catalog_admin','password':'SenhaCatalogo2026!'})
        self.headers={'X-CSRF-Token':login.json['csrf_token']}
        response=self.client.post('/api/produtos',json={'id':'TEST','nome':'Nome legado','unidade':'UN','custo':12,'marca':'Marca mantida'},headers=self.headers)
        self.assertEqual(response.status_code,201)

    def patch(self,changes,version='catalog_adjustment_test_v1'):
        path=self.root/'patch.json'
        path.write_text(json.dumps({'version':version,'source_sha256':'a'*64,'changes':changes}),encoding='utf-8')
        return path

    def apply(self,changes):
        path=self.patch(changes)
        with self.app.app_context():
            return apply_adjustments(get_db(),path)

    def product(self):
        return next(row for row in self.client.get('/api/produtos').json if row['id']=='TEST')

    def test_updates_only_reviewed_fields_and_preserves_limits(self):
        self.client.put('/api/produtos/TEST/limites',json={'lojas':[{'loja_id':1,'estoque_minimo':2,'estoque_maximo':8},{'loja_id':3,'estoque_minimo':5,'estoque_maximo':15}]},headers=self.headers)
        before=self.client.get('/api/produtos/TEST/limites').json['lojas']
        result=self.apply([{'id':'TEST','campos':{'nome':{'antes':'Nome legado','depois':'Nome da planilha'},'custo':{'antes':12,'depois':19.5},'secao':{'antes':None,'depois':'Seção da planilha'}}}])
        self.assertTrue(result['aplicado'])
        self.assertEqual(result['atualizados'],1)
        self.assertEqual(result['campos_atualizados'],3)
        self.assertEqual(self.product()['nome'],'Nome da planilha')
        self.assertEqual(self.product()['custo'],19.5)
        self.assertEqual(self.product()['marca'],'Marca mantida')
        self.assertEqual(self.client.get('/api/produtos/TEST/limites').json['lojas'],before)
        self.assertEqual(self.client.get('/api/movimentacoes').json,[])

    def test_replay_does_not_overwrite_later_user_changes(self):
        changes=[{'id':'TEST','campos':{'nome':{'antes':'Nome legado','depois':'Nome da planilha'}}}]
        self.apply(changes)
        self.client.put('/api/produtos/TEST',json={'nome':'Edição posterior do usuário'},headers=self.headers)
        result=self.apply(changes)
        self.assertFalse(result['aplicado'])
        self.assertEqual(self.product()['nome'],'Edição posterior do usuário')
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM catalog_adjustments').fetchone()[0],1)

    def test_preexisting_customizations_are_preserved_and_reported(self):
        self.client.put('/api/produtos/TEST',json={'nome':'Nome personalizado','ativo':False},headers=self.headers)
        result=self.apply([{'id':'TEST','campos':{'nome':{'antes':'Nome legado','depois':'Nome da planilha'},'custo':{'antes':12,'depois':13}}}])
        self.assertEqual(result['personalizacoes_preservadas'],[{'id':'TEST','campo':'nome'}])
        self.assertEqual(self.product()['nome'],'Nome personalizado')
        self.assertEqual(self.product()['custo'],13)
        self.assertFalse(self.product()['ativo'])

    def test_units_are_not_reinterpreted_when_stock_or_history_exists(self):
        for kind in ['Entrada','Saida']:
            self.assertEqual(self.client.post('/api/movimentacoes',json={'tipo':kind,'produto_id':'TEST','loja_id':1,'quantidade':2,'motivo':'Operação real'},headers=self.headers).status_code,201)
        history=self.client.get('/api/movimentacoes').json
        stock=self.client.get('/api/estoque').json
        result=self.apply([{'id':'TEST','campos':{'unidade':{'antes':'UN','depois':'KG'},'nome':{'antes':'Nome legado','depois':'Nome da planilha'}}}])
        self.assertEqual(result['unidades_para_revisao'],['TEST'])
        self.assertEqual(self.product()['unidade'],'UN')
        self.assertEqual(self.client.get('/api/estoque').json[0]['quantidade'],stock[0]['quantidade'])
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM movimentacoes WHERE produto_id='TEST'").fetchone()[0],len(history))

    def test_units_are_preserved_when_store_limits_already_use_the_old_unit(self):
        self.client.put('/api/produtos/TEST/limites',json={'lojas':[{'loja_id':1,'estoque_minimo':2,'estoque_maximo':8}]},headers=self.headers)
        result=self.apply([{'id':'TEST','campos':{'unidade':{'antes':'UN','depois':'CX'}}}])
        self.assertEqual(result['unidades_para_revisao'],['TEST'])
        self.assertEqual(self.product()['unidade'],'UN')
        settings=self.client.get('/api/produtos/TEST/limites').json['lojas']
        self.assertEqual(settings[0]['estoque_minimo'],2)
        self.assertEqual(settings[0]['estoque_maximo'],8)

    def test_missing_products_are_not_recreated(self):
        result=self.apply([{'id':'DELETED','campos':{'nome':{'antes':'Antigo','depois':'Novo'}}}])
        self.assertEqual(result['produtos_ausentes'],['DELETED'])
        self.assertEqual(result['atualizados'],0)
        self.assertNotIn('DELETED',[row['id'] for row in self.client.get('/api/produtos').json])

    def test_invalid_fields_cannot_modify_store_limits(self):
        path=self.patch([{'id':'TEST','campos':{'estoque_minimo':{'antes':0,'depois':99}}}])
        with self.assertRaises(ValueError):read_adjustments(path)
        self.assertEqual(self.product()['nome'],'Nome legado')

    def test_failure_rolls_back_product_section_and_revision_marker(self):
        path=self.patch([{'id':'TEST','campos':{'nome':{'antes':'Nome legado','depois':'Nome da planilha'},'secao':{'antes':None,'depois':'Nova seção'}}}])
        with self.app.app_context():
            db=get_db()
            db.execute("CREATE TRIGGER reject_review BEFORE INSERT ON auditoria BEGIN SELECT RAISE(ABORT,'rollback'); END")
            db.commit()
            with self.assertRaises(sqlite3.IntegrityError):apply_adjustments(db,path)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM catalog_adjustments').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM secoes WHERE nome='Nova seção'").fetchone()[0],0)
        self.assertEqual(self.product()['nome'],'Nome legado')

    def test_actual_review_is_limited_to_175_valid_product_codes(self):
        data=read_adjustments()
        self.assertEqual(len(data['changes']),175)
        self.assertTrue({'360618','341499','377707'}.isdisjoint({row['id'] for row in data['changes']}))
        self.assertEqual(sum(len(row['campos']) for row in data['changes']),410)


if __name__=='__main__':unittest.main()
