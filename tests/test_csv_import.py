"""Transactional spreadsheet import: real routes with disposable data."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from backend.app import create_app
from backend.catalog_csv import analyze_csv,fetch_google_csv,GoogleRedirect


class SpreadsheetTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='erp-csv-')
        self.addCleanup(temp.cleanup)
        self.database=str(Path(temp.name)/'erp.sqlite3')
        self.app=create_app({'TESTING':True,'DATABASE':self.database,'SECRET_KEY':'csv-test-only-key'})
        self.client=self.app.test_client()
        result=self.client.post('/api/setup',json={'nome':'Importador','username':'importador','password':'SenhaSeguraCSV2026!'})
        self.assertEqual(result.status_code,201)
        self.csrf=result.json['csrf_token']

    def post(self,data):
        return self.client.post('/api/produtos/importar',json=data,headers={'X-CSRF-Token':self.csrf})

    def test_preview_detects_portuguese_columns_and_preserves_zero_prefixes(self):
        source='Código;Descrição;Seção;Unidade;Custo\n000123;Detergente;Limpeza;L;12,34\n'
        preview=self.post({'csv_text':source})
        self.assertEqual(preview.status_code,200)
        self.assertEqual(preview.json['rows'][0]['id'],'000123')
        self.assertEqual(preview.json['rows'][0]['custo'],12.34)
        self.assertEqual(self.client.get('/api/produtos').json,[])
        response=self.post({'csv_text':source,'aplicar':True})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['criados'],1)
        self.assertEqual(self.client.get('/api/produtos').json[0]['nome'],'Detergente')
        self.assertTrue(all(row['quantidade']==0 for row in self.client.get('/api/estoque').json))
        self.assertEqual(self.client.get('/api/movimentacoes').json,[])

    def test_reimport_preserves_existing_by_default_and_can_update_only_supplied_fields(self):
        initial='Código,Descrição,Custo,Marca\n001,Produto inicial,9.50,Marca inicial'
        self.assertEqual(self.post({'csv_text':initial,'aplicar':True}).json['criados'],1)
        source='Código,Descrição,Custo\n001,Descrição atualizada,'
        preserved=self.post({'csv_text':source,'aplicar':True})
        self.assertEqual(preserved.json['preservados'],1)
        product=self.client.get('/api/produtos').json[0]
        self.assertEqual(product['nome'],'Produto inicial')
        updated=self.post({'csv_text':source,'aplicar':True,'atualizar_existentes':True})
        self.assertEqual(updated.json['atualizados'],1)
        product=self.client.get('/api/produtos').json[0]
        self.assertEqual(product['nome'],'Descrição atualizada')
        self.assertEqual(product['custo'],9.5)
        self.assertEqual(product['marca'],'Marca inicial')

    def test_invalid_or_conflicting_rows_block_entire_import(self):
        for source in ('Código;Descrição;Custo\n001;Valido;1\n002;Invalido;NaN',
                       'Código;Descrição\n001;A\n001;B'):
            with self.subTest(source=source):
                preview=self.post({'csv_text':source})
                self.assertTrue(preview.json['errors'])
                self.assertEqual(self.post({'csv_text':source,'aplicar':True}).status_code,400)
                self.assertEqual(self.client.get('/api/produtos').json,[])

    def test_identical_duplicate_rows_are_imported_only_once(self):
        result=self.post({'csv_text':'Código;Descrição\n001;Produto\n001;Produto','aplicar':True})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json['criados'],1)
        self.assertEqual(len(self.client.get('/api/produtos').json),1)

    def test_mapping_and_title_rows_round_trip(self):
        source='Lista de materiais\nCódigo;Descrição;Unidade\n001;Produto;UN'
        first=analyze_csv(source)
        second=analyze_csv(source,first['mapping'],first['header_row'])
        self.assertEqual(first['rows'],second['rows'])
        unknown='Interno;Material comercial;Familia\n012;Produto;Papelaria'
        missing=self.post({'csv_text':unknown})
        self.assertTrue(missing.json['missing'])
        mapped=self.post({'csv_text':unknown,'mapping':{'id':0,'nome':1,'secao':2},'aplicar':True})
        self.assertEqual(mapped.status_code,200)
        self.assertEqual(self.client.get('/api/produtos').json[0]['secao'],'Papelaria')

    def test_stock_columns_are_ignored(self):
        source='Código;Descrição;Estoque\n001;Produto;999'
        preview=self.post({'csv_text':source})
        self.assertTrue(preview.json['warnings'])
        self.assertEqual(self.post({'csv_text':source,'aplicar':True}).status_code,200)
        self.assertEqual(sum(row['quantidade'] for row in self.client.get('/api/estoque').json),0)

    def test_import_failure_rolls_back_earlier_products_and_new_sections(self):
        self.post({'csv_text':'Código;Descrição;Estoque máximo\n001;Existente;5','aplicar':True})
        source='Código;Descrição;Seção;Estoque mínimo\n002;Novo;Nova seção;1\n001;Existente;Limpeza;10'
        response=self.post({'csv_text':source,'aplicar':True,'atualizar_existentes':True})
        self.assertEqual(response.status_code,400)
        self.assertEqual([row['id'] for row in self.client.get('/api/produtos').json],['001'])
        self.assertNotIn('Nova seção',[row['nome'] for row in self.client.get('/api/secoes').json])

    def test_import_requires_manager_auth_and_csrf(self):
        anonymous=self.app.test_client()
        payload={'csv_text':'Código;Descrição\n001;Produto','aplicar':True}
        self.assertIn(anonymous.post('/api/produtos/importar',json=payload).status_code,(401,403))
        self.assertEqual(self.client.post('/api/produtos/importar',json=payload).status_code,403)
        user=self.client.post('/api/usuarios',json={'nome':'Operador','username':'operador','password':'SenhaOperador2026!','nivel_acesso':'Operacional'},headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(user.status_code,201)
        login=anonymous.post('/api/login',json={'username':'operador','password':'SenhaOperador2026!'})
        self.assertEqual(anonymous.post('/api/produtos/importar',json=payload,headers={'X-CSRF-Token':login.json['csrf_token']}).status_code,403)

    def test_google_reader_only_uses_google_sheets_and_reports_network_errors(self):
        for url in ['http://docs.google.com/spreadsheets/d/test/edit','https://127.0.0.1/','https://docs.google.com.evil.test/spreadsheets/d/test/edit']:
            with self.subTest(url=url),self.assertRaises(ValueError):
                fetch_google_csv(url)
        with patch('backend.catalog_csv.build_opener') as factory:
            factory.return_value.open.side_effect=URLError('blocked')
            with self.assertRaisesRegex(ValueError,'permissão de rede'):
                fetch_google_csv('https://docs.google.com/spreadsheets/d/test/edit#gid=123')
        with self.assertRaises(ValueError):
            GoogleRedirect().redirect_request(None,None,302,'',{},'https://127.0.0.1/private')

    def test_csv_handles_quotes_brazilian_currency_and_rejects_html(self):
        analysis=analyze_csv('Código,Descrição,Custo\n001,"Produto, com vírgula","R$ 1.234,56"')
        self.assertEqual(analysis['rows'][0]['custo'],1234.56)
        self.assertEqual(analysis['rows'][0]['nome'],'Produto, com vírgula')
        with self.assertRaises(ValueError):
            analyze_csv('<!doctype html><html>Login</html>')


if __name__=='__main__':
    unittest.main()
