"""Extract a reviewed product catalog from Excel; never import balances or notes.

Usage: python -m backend.import_workbook workbook.xlsx --output catalog.csv --report review.json
Formulas are read through saved values only; Excel code and external links are never executed.
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile

import openpyxl
try:
    from .catalog_csv import analyze_csv, normalized, decimal_cell, LIMITS
except ImportError:
    from catalog_csv import analyze_csv, normalized, decimal_cell, LIMITS

HEADERS = [
 ('id','Código'),('nome','Descrição'),('secao','Seção'),('unidade','Unidade'),
 ('custo','Custo'),('estoque_minimo','Estoque mínimo'),('estoque_maximo','Estoque máximo'),
 ('referencia','Referência'),('marca','Marca'),('destinacao','Destinação'),('periodo_consumo','Período de consumo'),
]
ALIASES={
 'id':('codigo','codigoerp','codigoerpprincipal','sku'),
 'nome':('descricao','descricaoproduto','descricaodoproduto','nome','produto'),
 'secao':('secao','categoria'), 'unidade':('unidade','unidadedemedida','fatorconversao'),
 'custo':('custo','custounitario','custogalao'), 'estoque_minimo':('estoqueminimo','min'),
 'estoque_maximo':('estoquemaximo','max','estoquemaximoemgalao'),
 'referencia':('referencia','referenciagalvanoteck'), 'marca':('marca',),
 'destinacao':('destinacaodeuso','destinacao'), 'periodo_consumo':('periodo','periodoconsumo','periododeconsumo'),
}
PERIODS={'DIARIO':'Diário','SEMANAL':'Semanal','QUINZENAL':'Quinzenal','MENSAL':'Mensal','BIMESTRAL':'Bimestral','TRIMESTRAL':'Trimestral','SEMESTRAL':'Semestral','SEIS MESES':'Semestral','ANUAL':'Anual','SAZONAL':'Sazonal'}
UNITS={'UND':'UN','UNID':'UN','UNIDADE':'UN','UN':'UN','KG':'KG','G':'G','L':'L','ML':'ML','CX':'CX','PC':'PC','PCT':'PCT','M':'M','ROLO':'ROLO','PAR':'PAR'}


def validate_excel(data):
    if not isinstance(data,bytes) or len(data)>10*1024*1024:
        raise ValueError('Envie um arquivo Excel de até 10 MB.')
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            info=archive.infolist()
            if len(info)>5000 or sum(item.file_size for item in info)>50*1024*1024:
                raise ValueError('A estrutura expandida do Excel excede o limite de segurança.')
            if 'xl/workbook.xml' not in archive.namelist():
                raise ValueError('Arquivo Excel inválido.')
    except BadZipFile as error:
        raise ValueError('Use um arquivo Excel .xlsx válido.') from error


def code_text(cell):
    value=cell.value
    if isinstance(value,bool) or isinstance(value,(dt.datetime,dt.date,dt.time)):
        return None
    if isinstance(value,(int,float)):
        if not float(value).is_integer():
            return None
        value=str(int(value))
        fmt=cell.number_format or ''
        if re.fullmatch(r'0{2,20}',fmt):
            value=value.zfill(len(fmt))
    elif isinstance(value,str):
        value=value.strip()
    else:
        return None
    return value if re.fullmatch(r'[A-Za-z0-9_-]{1,20}',value) else None


def csv_text(items):
    out=io.StringIO(newline='')
    writer=csv.writer(out,delimiter=';',lineterminator='\n')
    writer.writerow([title for _,title in HEADERS])
    for item in sorted(items,key=lambda p:p['id']):
        writer.writerow([item.get(key,'') for key,_ in HEADERS])
    return out.getvalue()


def extract_catalog(data):
    validate_excel(data)
    try:
        workbook=openpyxl.load_workbook(io.BytesIO(data),read_only=True,data_only=True,keep_links=False)
    except Exception as error:
        raise ValueError('Não foi possível ler o Excel. Verifique se o arquivo .xlsx está íntegro.') from error
    records=collections.defaultdict(list)
    report={'source_sha256':hashlib.sha256(data).hexdigest(),'sheets':[],'conflicts':[], 'field_warnings':[], 'historical_rows_ignored':0}
    try:
        for sheet in workbook:
            iterator=sheet.iter_rows(max_col=100)
            mapping=None;header_row=None
            for index,row in enumerate(iterator,1):
                if index>15:break
                names=[normalized(str(cell.value or '')) for cell in row]
                columns={key:next((i for i,name in enumerate(names) if name in aliases),None) for key,aliases in ALIASES.items()}
                if columns['id'] is not None and columns['nome'] is not None:
                    mapping=columns;header_row=index;break
            stats={'sheet':sheet.title,'state':sheet.sheet_state,'rows':0,'header_row':header_row}
            report['sheets'].append(stats)
            if mapping is None:continue
            for row_number,row in enumerate(iterator,header_row+1):
                if row_number>20000:
                    raise ValueError('A aba excede o limite de 20 mil linhas.')
                def cell(field):
                    index=mapping.get(field)
                    return row[index] if index is not None and index<len(row) else None
                c,n=cell('id'),cell('nome')
                if c is None or n is None:continue
                code=code_text(c)
                if code is None:
                    if c.value is not None and n.value is not None:report['historical_rows_ignored']+=1
                    continue
                if not isinstance(n.value,str) or not n.value.strip():continue
                item={'id':code,'nome':n.value.strip()}
                if len(item['nome'])>LIMITS['nome']:
                    report['field_warnings'].append({'sheet':sheet.title,'row':row_number,'id':code,'field':'nome','message':'Descrição acima do limite; linha excluída.'})
                    continue
                for field in ALIASES:
                    if field in ('id','nome'):continue
                    entry=cell(field)
                    value=entry.value if entry is not None else None
                    if value is None or str(value).strip()=='':continue
                    try:
                        if field in ('custo','estoque_minimo','estoque_maximo'):
                            item[field]=decimal_cell(str(value),field)
                        elif field=='unidade':
                            unit=UNITS.get(str(value).strip().upper())
                            if unit:item[field]=unit
                        elif field=='periodo_consumo':
                            period=PERIODS.get(normalized(str(value)).upper())
                            # normalized removes spaces and accents.
                            if not period:period=next((label for raw,label in PERIODS.items() if normalized(raw)==normalized(str(value))),None)
                            if period:item[field]=period
                        else:
                            string=str(value).strip()
                            if isinstance(value,float) and value.is_integer():string=str(int(value))
                            if len(string)>LIMITS[field]:raise ValueError('Campo excede o limite; valor não importado.')
                            item[field]=string
                    except ValueError as error:
                        report['field_warnings'].append({'sheet':sheet.title,'row':row_number,'id':code,'field':field,'message':str(error)})
                if not item.get('secao') and sheet.sheet_state=='visible':item['secao']=sheet.title.strip()
                records[code].append({'sheet':sheet.title,'row':row_number,'visible':sheet.sheet_state=='visible','product':item})
                stats['rows']+=1
        result=[]
        for code,entries in records.items():
            visible=[entry for entry in entries if entry['visible']]
            candidates=visible or entries
            names={normalized(entry['product']['nome']) for entry in candidates}
            if len(names)>1:
                report['conflicts'].append({'id':code,'variants':[{'sheet':entry['sheet'],'row':entry['row'],'nome':entry['product']['nome']} for entry in candidates]})
                continue
            chosen=dict(candidates[0]['product'])
            # Visible catalog sheets take precedence over hidden lookup sheets.
            # Only fill absent fields; descriptions, notes and historical balances are never inferred.
            for entry in candidates[1:]+[entry for entry in entries if entry not in candidates]:
                for field,value in entry['product'].items():
                    if field not in chosen:chosen[field]=value
            if chosen.get('estoque_maximo',0) and chosen.get('estoque_minimo',0)>chosen['estoque_maximo']:
                report['field_warnings'].append({'id':code,'field':'estoque_minimo/estoque_maximo','message':'Mínimo maior que máximo: ambos omitidos para revisão.'})
                chosen.pop('estoque_minimo',None);chosen.pop('estoque_maximo',None)
            result.append(chosen)
        source=csv_text(result)
        validation=analyze_csv(source)
        if validation['errors']:
            raise ValueError('O catálogo extraído apresentou erros: '+str(validation['errors'][:5]))
        report['unique_codes']=len(records)
        report['products']=len(result)
        report['conflicting_codes']=len(report['conflicts'])
        report['policy']='Abas visíveis têm prioridade; abas ocultas complementam produtos ausentes. Códigos com descrições conflitantes não são importados. Estoques, pedidos, contatos e observações livres não são importados.'
        return source,report
    finally:
        workbook.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    source,report=extract_catalog(args.source.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(source,encoding='utf-8')
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{report["products"]} produtos válidos; {report["conflicting_codes"]} códigos separados para revisão.')


if __name__=='__main__':main()
