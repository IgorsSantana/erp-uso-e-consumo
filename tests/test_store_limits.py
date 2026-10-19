"""Stock thresholds belong to a product/store pair, across all operational flows."""
import csv
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backend.app import create_app
from backend.db import SCHEMA


class StoreLimitTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory(prefix='erp-limits-')
        self.addCleanup(directory.cleanup)
        self.database=Path(directory.name)/'erp.sqlite3'
        self.config={'TESTING':True,'DATABASE':str(self.database),'SECRET_KEY':'limits-test-only-key'}
        self.app=create_app(self.config)
        self.client=self.app.test_client()
        login=self.client.post('/api/setup',json={'nome':'Gestão','username':'admin_limites','password':'SenhaLimites2026!'})
        self.csrf=login.json['csrf_token']
        self.product='P001'
        result=self.write('/api/produtos',{'id':self.product,'nome':'Produto teste','custo':2,'estoque_minimo':99,'estoque_maximo':150})
        self.assertEqual(result.status_code,201)

    def write(self,path,body,method='POST',client=None,csrf=None):
        return (client or self.client).open(path,method=method,json=body,headers={'X-CSRF-Token':csrf or self.csrf})

    def limits(self,items):
        return self.write(f'/api/produtos/{self.product}/limites',{'lojas':items},'PUT')

    def values(self):
        return {row['loja_id']:row for row in self.client.get('/api/estoque').json if row['produto_id']==self.product}

    def set_pair(self):
        response=self.limits([{'loja_id':1,'estoque_minimo':2,'estoque_maximo':10},{'loja_id':3,'estoque_minimo':8,'estoque_maximo':20}])
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))

    def test_each_store_has_independent_limits_and_alerts(self):
        self.set_pair()
        for sid in (1,3):
            self.assertEqual(self.write('/api/movimentacoes',{'tipo':'Entrada','produto_id':self.product,'loja_id':sid,'quantidade':5,'motivo':'Recebimento'}).status_code,201)
        stock=self.values()
        self.assertEqual((stock[1]['estoque_minimo'],stock[1]['estoque_maximo']),(2,10))
        self.assertEqual((stock[3]['estoque_minimo'],stock[3]['estoque_maximo']),(8,20))
        alerts=self.client.get('/api/dashboard').json['alertas']
        self.assertEqual([(row['produto_id'],row['loja_id']) for row in alerts],[(self.product,3)])
        self.assertEqual(self.limits([{'loja_id':1,'estoque_minimo':1,'estoque_maximo':7}]).status_code,200)
        self.assertEqual((self.values()[3]['estoque_minimo'],self.values()[3]['estoque_maximo']),(8,20))
        settings=self.client.get(f'/api/produtos/{self.product}/limites').json
        self.assertEqual(next(row for row in settings['lojas'] if row['loja_id']==1)['estoque_minimo'],1)
        products=self.client.get('/api/produtos').json
        self.assertNotIn('estoque_minimo',products[0])

    def test_new_store_does_not_inherit_a_global_or_other_store_limit(self):
        self.set_pair()
        response=self.write('/api/lojas',{'nome':'Nova loja','sigla':'NOVA'})
        sid=response.json['id']
        stock=self.values()
        self.assertEqual((stock[sid]['estoque_minimo'],stock[sid]['estoque_maximo'],stock[sid]['limites_configurados']),(0,0,0))
        self.write(f'/api/produtos/{self.product}',{'estoque_minimo':200,'estoque_maximo':300},'PUT')
        self.assertEqual(self.values()[1]['estoque_minimo'],2)
        self.assertEqual(self.values()[sid]['estoque_minimo'],0)
        create_app(self.config)
        self.assertEqual(self.values()[sid]['limites_configurados'],0)

    def test_invalid_batch_never_partially_updates_other_stores(self):
        self.set_pair()
        for bad in ({'loja_id':3,'estoque_minimo':-1,'estoque_maximo':10},
                    {'loja_id':3,'estoque_minimo':'NaN','estoque_maximo':10},
                    {'loja_id':3,'estoque_minimo':11,'estoque_maximo':10},
                    {'loja_id':3,'estoque_minimo':1.0001,'estoque_maximo':10},
                    {'loja_id':999999,'estoque_minimo':1,'estoque_maximo':10}):
            with self.subTest(bad=bad):
                response=self.limits([{'loja_id':1,'estoque_minimo':1,'estoque_maximo':5},bad])
                self.assertIn(response.status_code,(400,404))
                self.assertEqual(self.values()[1]['estoque_minimo'],2)
                self.assertEqual(self.values()[3]['estoque_minimo'],8)
        self.assertEqual(self.limits([{'loja_id':1},{'loja_id':1}]).status_code,400)

    def test_clearing_one_store_preserves_stock_history_and_other_stores(self):
        self.set_pair()
        self.write('/api/movimentacoes',{'tipo':'Entrada','produto_id':self.product,'loja_id':1,'quantidade':4,'motivo':'Saldo real'})
        before=self.client.get('/api/movimentacoes').json
        self.assertEqual(self.limits([{'loja_id':1,'configurado':False}]).status_code,200)
        self.assertEqual(self.values()[1]['quantidade'],4)
        self.assertEqual(self.values()[1]['limites_configurados'],0)
        self.assertEqual(self.values()[3]['estoque_minimo'],8)
        self.assertEqual(self.client.get('/api/movimentacoes').json,before)

    def test_stock_csv_reports_the_store_specific_limits(self):
        self.set_pair()
        response=self.client.get('/api/relatorios/estoque.csv')
        data=list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig')),delimiter=';'))
        origin=next(row for row in data if row['loja_id']=='1')
        destination=next(row for row in data if row['loja_id']=='3')
        self.assertEqual((float(origin['estoque_minimo']),float(origin['estoque_maximo'])),(2,10))
        self.assertEqual((float(destination['estoque_minimo']),float(destination['estoque_maximo'])),(8,20))

    def test_csv_import_targets_one_store_and_preserves_other_stores(self):
        self.set_pair()
        source='Código;Descrição;Estoque mínimo;Estoque máximo\nP001;Produto teste;3;12'
        preview=self.write('/api/produtos/importar',{'csv_text':source})
        self.assertTrue(preview.json['possui_limites'])
        self.assertEqual(self.write('/api/produtos/importar',{'csv_text':source,'aplicar':True}).status_code,400)
        preserved=self.write('/api/produtos/importar',{'csv_text':source,'aplicar':True,'loja_limites_id':1})
        self.assertEqual(preserved.status_code,200)
        self.assertEqual(self.values()[1]['estoque_minimo'],2)
        updated=self.write('/api/produtos/importar',{'csv_text':source,'aplicar':True,'loja_limites_id':1,'atualizar_existentes':True})
        self.assertEqual(updated.status_code,200,updated.get_data(as_text=True))
        self.assertEqual(updated.json['limites_atualizados'],1)
        self.assertEqual((self.values()[1]['estoque_minimo'],self.values()[1]['estoque_maximo']),(3,12))
        self.assertEqual((self.values()[3]['estoque_minimo'],self.values()[3]['estoque_maximo']),(8,20))

    def test_csv_can_skip_limits_without_creating_global_thresholds(self):
        source='Código;Descrição;Estoque mínimo;Estoque máximo\nNEW;Novo produto;3;12'
        response=self.write('/api/produtos/importar',{'csv_text':source,'aplicar':True,'ignorar_limites':True})
        self.assertEqual(response.status_code,200)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT estoque_minimo,estoque_maximo FROM produtos WHERE id='NEW'").fetchone(),(0,0))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM estoque_limites WHERE produto_id='NEW'").fetchone()[0],0)

    def test_operational_access_cannot_change_limits_and_csrf_is_enforced(self):
        self.assertEqual(self.client.put(f'/api/produtos/{self.product}/limites',json={'lojas':[{'loja_id':1}]}).status_code,403)
        self.write('/api/usuarios',{'nome':'Operador','username':'operador_limites','password':'SenhaOperador2026!','nivel_acesso':'Operacional'})
        operator=self.app.test_client()
        login=operator.post('/api/login',json={'username':'operador_limites','password':'SenhaOperador2026!'})
        self.assertEqual(operator.get(f'/api/produtos/{self.product}/limites').status_code,200)
        denied=self.write(f'/api/produtos/{self.product}/limites',{'lojas':[{'loja_id':1}]},'PUT',operator,login.json['csrf_token'])
        self.assertEqual(denied.status_code,403)
        self.assertEqual(self.values()[1]['limites_configurados'],0)


class StoreLimitMigrationTests(unittest.TestCase):
    def test_legacy_values_are_copied_once_without_creating_stock(self):
        with tempfile.TemporaryDirectory(prefix='erp-limit-migration-') as directory:
            path=Path(directory)/'erp.sqlite3'
            with sqlite3.connect(path) as db:
                db.executescript(SCHEMA)
                db.execute('PRAGMA user_version=1')
                db.execute("INSERT INTO lojas VALUES(1,'Origem','OR')")
                db.execute("INSERT INTO lojas VALUES(3,'Destino','DE')")
                db.execute("INSERT INTO produtos(id,nome,estoque_minimo,estoque_maximo) VALUES('LEG','Legado',2,9)")
                db.commit()
            config={'TESTING':True,'DATABASE':str(path),'SECRET_KEY':'migration-test-key'}
            create_app(config)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT loja_id,estoque_minimo,estoque_maximo FROM estoque_limites ORDER BY loja_id').fetchall(),[(1,2,9),(3,2,9)])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM estoque').fetchone()[0],0)
                db.execute("UPDATE estoque_limites SET estoque_minimo=4 WHERE loja_id=3")
                db.execute('DELETE FROM estoque_limites WHERE loja_id=1')
                db.execute("INSERT INTO lojas VALUES(4,'Nova','NO')")
                db.commit()
            create_app(config)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT loja_id,estoque_minimo FROM estoque_limites ORDER BY loja_id').fetchall(),[(3,4)])


if __name__=='__main__':unittest.main()
