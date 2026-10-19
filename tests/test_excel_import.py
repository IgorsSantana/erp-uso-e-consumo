"""Excel extraction, bundled catalog startup and actual upload/import routes."""
import datetime as dt
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import openpyxl
from backend.app import create_app
from backend.bundled_catalog import CATALOG,apply_catalog
from backend.catalog_csv import analyze_csv
from backend.import_workbook import extract_catalog


def workbook_bytes():
    workbook=openpyxl.Workbook()
    sheet=workbook.active
    sheet.title='DADOS ESTOQUE'
    sheet.append(['CÓDIGO','SEÇÃO','DESCRIÇÃO','ESTOQUE'])
    sheet.append([123,'Limpeza','Nome antigo',999])
    sheet.append([456,'Consumo Geral','Produto apenas na base',888])
    sheet.sheet_state='hidden'
    visible=workbook.create_sheet('LIMPEZA')
    visible.append(['CÓDIGO','DESCRIÇÃO PRODUTO','MARCA','CUSTO GALÃO','ESTOQUE','FORNECEDOR'])
    visible.append([123,'Produto atualizado','Marca teste',15.25,500,'Contato que não deve ser importado'])
    visible['A2'].number_format='000000'
    # Keep a matching lookup SKU for this zero-prefixed product.
    sheet['A2']='000123'
    visible.append([789,'Descrição A',None,None,2])
    visible.append([789,'Descrição B',None,None,3])
    visible.append([dt.datetime(2026,7,10),'Registro histórico',None,None,10])
    visible.append([None,'Instrução na planilha: apagar registros'])
    visible.append([321,'Produto com fórmula',None,'=1+1',90])
    stream=io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


class ExcelExtractionTests(unittest.TestCase):
    def test_visible_sheet_priority_and_hidden_fallback_without_stock_or_notes(self):
        source,report=extract_catalog(workbook_bytes())
        analysis=analyze_csv(source)
        self.assertFalse(analysis['errors'])
        items={item['id']:item for item in analysis['rows']}
        self.assertEqual(items['000123']['nome'],'Produto atualizado')
        self.assertEqual(items['000123']['custo'],15.25)
        self.assertEqual(items['456']['nome'],'Produto apenas na base')
        self.assertEqual(items['000123']['secao'],'LIMPEZA')
        self.assertNotIn('estoque',items['000123'])
        self.assertNotIn('Contato que não deve ser importado',source)
        self.assertNotIn('apagar registros',source)
        self.assertEqual(report['historical_rows_ignored'],1)
        self.assertEqual(report['products'],3)

    def test_conflicting_codes_are_quarantined_and_formulas_are_not_evaluated(self):
        source,report=extract_catalog(workbook_bytes())
        items={item['id']:item for item in analyze_csv(source)['rows']}
        self.assertNotIn('789',items)
        self.assertEqual(report['conflicts'][0]['id'],'789')
        self.assertNotIn('custo',items['321'])
        self.assertNotIn('=1+1',source)

    def test_invalid_excel_is_rejected(self):
        for data in [b'not excel',b'',b'X'*(10*1024*1024+1)]:
            with self.subTest(size=len(data)),self.assertRaises(ValueError):
                extract_catalog(data)

    def test_reviewed_catalog_contains_466_unique_codes_and_omits_three_conflicts(self):
        analysis=analyze_csv(CATALOG.read_text(encoding='utf-8'))
        self.assertFalse(analysis['errors'])
        self.assertEqual(len(analysis['rows']),466)
        ids={item['id'] for item in analysis['rows']}
        self.assertEqual(len(ids),466)
        self.assertTrue({'341499','360618','377707'}.isdisjoint(ids))


class ExcelRouteAndSeedTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='erp-excel-')
        self.addCleanup(temp.cleanup)
        self.db=Path(temp.name)/'erp.sqlite3'
        self.config={'TESTING':True,'DATABASE':str(self.db),'SECRET_KEY':'excel-test-only-key'}
        self.app=create_app(self.config)
        self.client=self.app.test_client()
        login=self.client.post('/api/setup',json={'nome':'Admin Excel','username':'excel_admin','password':'SenhaExcel2026!'})
        self.csrf=login.json['csrf_token']

    def test_excel_upload_preview_does_not_write_until_confirmed(self):
        response=self.client.post('/api/produtos/ler-excel',data={'arquivo':(io.BytesIO(workbook_bytes()),'produtos.xlsx')},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        self.assertEqual(response.json['report']['products'],3)
        self.assertEqual(self.client.get('/api/produtos').json,[])
        imported=self.client.post('/api/produtos/importar',json={'csv_text':response.json['csv_text'],'aplicar':True},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(imported.status_code,200)
        self.assertEqual(imported.json['criados'],3)
        self.assertEqual(self.client.get('/api/movimentacoes').json,[])
        self.assertEqual(sum(row['quantidade'] for row in self.client.get('/api/estoque').json),0)

    def test_excel_upload_requires_csrf_and_valid_file(self):
        self.assertEqual(self.client.post('/api/produtos/ler-excel',data={'arquivo':(io.BytesIO(workbook_bytes()),'produtos.xlsx')}).status_code,403)
        invalid=self.client.post('/api/produtos/ler-excel',data={'arquivo':(io.BytesIO(b'not excel'),'produtos.xlsx')},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(invalid.status_code,400)

    def test_startup_imports_reviewed_catalog_once_preserves_changes_and_stock(self):
        created=self.client.post('/api/produtos',json={'id':'15','nome':'Nome mantido','custo':99},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(created.status_code,201)
        moved=self.client.post('/api/movimentacoes',json={'tipo':'Entrada','produto_id':'15','loja_id':1,'quantidade':7,'motivo':'Estoque real'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(moved.status_code,201)
        create_app({**self.config,'SEED_CATALOG':True})
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM produtos').fetchone()[0],466)
            self.assertEqual(db.execute("SELECT nome,custo FROM produtos WHERE id='15'").fetchone(),('Nome mantido',99))
            self.assertEqual(db.execute("SELECT quantidade FROM estoque WHERE produto_id='15' AND loja_id=1").fetchone()[0],7)
            db.execute("DELETE FROM produtos WHERE id='18'")
            db.commit()
        create_app({**self.config,'SEED_CATALOG':True})
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM produtos').fetchone()[0],465)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM catalog_releases').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0],1)

    def test_seed_failure_rolls_back_all_catalog_rows_and_release_marker(self):
        with self.app.app_context():
            from backend.db import get_db
            db=get_db()
            db.execute("CREATE TRIGGER fail_catalog_audit BEFORE INSERT ON auditoria BEGIN SELECT RAISE(ABORT,'rollback'); END")
            db.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                apply_catalog(db)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM produtos').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM catalog_releases').fetchone()[0],0)


if __name__=='__main__':unittest.main()
