"""Read product spreadsheets without executing formulas or changing inventory."""
import csv
import io
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

MAX_BYTES = 1_500_000
MAX_ROWS = 5000
FIELDS = {
    'id': ('codigo','codigoerp','codigoerpprincipal','sku','codigodoproduto','cod'),
    'nome': ('nome','descricao','descricaodoproduto','nomeproduto','nomedoproduto','produto','material'),
    'secao': ('secao','categoria','grupo','departamento'),
    'unidade': ('unidade','unidadedemedida','und','um','un'),
    'custo': ('custo','custounitario','precocusto','precodecusto','valorunitario'),
    'estoque_minimo': ('estoqueminimo','minimo','estoquemin'),
    'estoque_maximo': ('estoquemaximo','maximo','estoquemax'),
    'referencia': ('referencia','ref'),
    'marca': ('marca',),
    'destinacao': ('destinacao','destinacaodeuso','uso'),
    'periodo_consumo': ('periodoconsumo','periododeconsumo','periodicidade'),
}
LIMITS = {'id':20,'nome':150,'secao':100,'unidade':12,'referencia':100,'marca':100,'destinacao':200,'periodo_consumo':30}


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().lower())


def decimal_cell(raw, field):
    value=raw.strip().replace('R$','').replace('\u00a0','').replace(' ','')
    if ',' in value:
        value=value.replace('.','').replace(',','.')
    places=2 if field=='custo' else 3
    try:
        number=Decimal(value)
        if not number.is_finite() or number<0 or number>1_000_000_000:
            raise ValueError()
        fixed=number.quantize(Decimal(10)**-places,rounding=ROUND_HALF_UP)
        if fixed!=number:
            raise ValueError()
        return float(fixed)
    except (InvalidOperation,ValueError):
        raise ValueError(f'{field}: valor inválido; use até {places} casas decimais.')


def analyze_csv(source, mapping=None, header_row=None):
    if not isinstance(source,str) or not source.strip():
        raise ValueError('Selecione um arquivo CSV com os produtos.')
    if len(source.encode('utf-8'))>MAX_BYTES:
        raise ValueError('A planilha excede o limite de 1,5 MB.')
    source=source.lstrip('\ufeff')
    if source.lstrip().lower().startswith(('<!doctype','<html','<?xml')):
        raise ValueError('O conteúdo recebido não é CSV. Confira o compartilhamento da planilha.')
    candidates=[]
    for delimiter in (',',';','\t'):
        try:
            parsed=list(csv.reader(io.StringIO(source),delimiter=delimiter,strict=True))
        except csv.Error:
            continue
        if not parsed:
            continue
        score=max((sum(normalized(cell) in aliases for aliases in FIELDS.values() for cell in row) for row in parsed[:15]),default=0)
        width=max((len(row) for row in parsed[:15]),default=0)
        candidates.append((score,width,parsed))
    if not candidates:
        raise ValueError('Não foi possível ler o CSV. Use vírgula, ponto e vírgula ou tabulação.')
    matrix=max(candidates,key=lambda value:(value[0],value[1]))[2]
    if len(matrix)>MAX_ROWS+20:
        raise ValueError(f'Importe no máximo {MAX_ROWS} produtos por arquivo.')
    header_index=0
    if header_row is not None:
        if isinstance(header_row,bool) or not isinstance(header_row,int) or not 1<=header_row<=min(15,len(matrix)):
            raise ValueError('Linha de cabeçalho inválida.')
        header_index=header_row-1
    else:
        for index,row in enumerate(matrix[:15]):
            keys={normalized(value) for value in row}
            if keys.intersection(FIELDS['id']) and keys.intersection(FIELDS['nome']):
                header_index=index
                break
    headers=[value.strip() or f'Coluna {index+1}' for index,value in enumerate(matrix[header_index])]
    selected={}
    if mapping is None:
        for field,aliases in FIELDS.items():
            matches=[i for i,h in enumerate(headers) if normalized(h) in aliases]
            if len(matches)==1:
                selected[field]=matches[0]
    else:
        if not isinstance(mapping,dict):
            raise ValueError('Mapeamento de colunas inválido.')
        for field,index in mapping.items():
            if field not in FIELDS or index in ('',None):
                continue
            if isinstance(index,bool) or not isinstance(index,(int,str)) or not str(index).isdigit() or not 0<=int(index)<len(headers):
                raise ValueError('Mapeamento de colunas inválido.')
            selected[field]=int(index)
        if len(set(selected.values()))!=len(selected):
            raise ValueError('Uma coluna não pode ser usada para campos diferentes.')
    missing=[field for field in ('id','nome') if field not in selected]
    result={'headers':headers,'mapping':selected,'header_row':header_index+1,'rows':[], 'errors':[], 'warnings':[], 'ignored':0,'total':0,'missing':missing}
    if missing:
        result['errors'].append({'linha':header_index+1,'mensagem':'Selecione as colunas de código e nome/descrição para continuar.'})
        return result
    seen={}
    for line_index,row in enumerate(matrix[header_index+1:],header_index+2):
        if not any(cell.strip() for cell in row):
            continue
        result['total']+=1
        if result['total']>MAX_ROWS:
            raise ValueError(f'Importe no máximo {MAX_ROWS} produtos por arquivo.')
        item={}
        try:
            for field,index in selected.items():
                value=row[index].strip() if index<len(row) else ''
                if not value:
                    if field in ('id','nome'):
                        raise ValueError('Código e nome/descrição são obrigatórios.')
                    continue
                if field in ('custo','estoque_minimo','estoque_maximo'):
                    item[field]=decimal_cell(value,field)
                else:
                    value=unicodedata.normalize('NFC',value)
                    if len(value)>LIMITS[field]:
                        raise ValueError(f'{field}: máximo de {LIMITS[field]} caracteres.')
                    item[field]=value
            if not re.fullmatch(r'[A-Za-z0-9_-]+',item['id']):
                raise ValueError('Código inválido; use letras, números, hífen ou sublinhado.')
            if item.get('estoque_maximo',0) and item.get('estoque_minimo',0)>item['estoque_maximo']:
                raise ValueError('O estoque mínimo deve ser menor ou igual ao máximo.')
            if item['id'] in seen:
                if item!=seen[item['id']]:
                    raise ValueError(f'Código {item["id"]} repetido com informações diferentes. Corrija a duplicidade.')
                result['ignored']+=1
                continue
            seen[item['id']]=item
            result['rows'].append(item)
        except ValueError as error:
            result['errors'].append({'linha':line_index,'mensagem':str(error)})
    if not result['total']:
        result['errors'].append({'linha':header_index+1,'mensagem':'A planilha não contém produtos.'})
    unmapped=[h for i,h in enumerate(headers) if i not in selected.values()]
    if unmapped:
        result['warnings'].append('Colunas não importadas: '+', '.join(unmapped)+'. Saldos físicos não são alterados pela importação de produtos.')
    return result


def import_rows(db, items, update_existing=False, user_id=None, origin='CSV', loja_id=None):
    """Import metadata and optionally store-specific thresholds in the caller's transaction."""
    counts={'criados':0,'atualizados':0,'preservados':0,'secoes_criadas':0}
    if loja_id is not None:
        counts['limites_atualizados']=0
        if not db.execute('SELECT 1 FROM lojas WHERE id=?',(loja_id,)).fetchone():
            raise ValueError('Loja dos limites não encontrada.')
    sections={normalized(row['nome']):row['id'] for row in db.execute('SELECT id,nome FROM secoes')}
    for item in items:
        old=db.execute('SELECT * FROM produtos WHERE id=?',(item['id'],)).fetchone()
        if old and not update_existing:
            counts['preservados']+=1
        else:
            # Global spreadsheet columns are never operational product thresholds.
            fields={key:value for key,value in item.items() if key not in ('secao','estoque_minimo','estoque_maximo')}
            section=item.get('secao')
            if section:
                key=normalized(section)
                if key not in sections:
                    sections[key]=db.execute('INSERT INTO secoes(nome) VALUES(?)',(section,)).lastrowid
                    counts['secoes_criadas']+=1
                fields['secao_id']=sections[key]
            if old:
                fields.pop('id')
                db.execute('UPDATE produtos SET '+','.join(f'{key}=?' for key in fields)+' WHERE id=?',(*fields.values(),item['id']))
                counts['atualizados']+=1
            else:
                db.execute('INSERT INTO produtos('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',tuple(fields.values()))
                counts['criados']+=1
        if loja_id is not None and any(key in item for key in ('estoque_minimo','estoque_maximo')):
            current=db.execute('SELECT * FROM estoque_limites WHERE produto_id=? AND loja_id=?',(item['id'],loja_id)).fetchone()
            if current and not update_existing:
                continue
            minimum=item.get('estoque_minimo',current['estoque_minimo'] if current else 0)
            maximum=item.get('estoque_maximo',current['estoque_maximo'] if current else 0)
            if maximum and minimum>maximum:
                raise ValueError(f'{item["id"]}: mínimo superior ao máximo da loja. Revise os limites antes de atualizar.')
            try:
                from .stock_limits import save_limit
            except ImportError:
                from stock_limits import save_limit
            save_limit(db,item['id'],loja_id,minimum,maximum)
            counts['limites_atualizados']+=1
    if counts['criados'] or counts['atualizados'] or counts.get('limites_atualizados'):
        import json
        details={**counts,**({'loja_limites_id':loja_id} if loja_id is not None else {})}
        db.execute('INSERT INTO auditoria(usuario_id,acao,entidade,entidade_id,detalhes) VALUES(?,?,?,?,?)',
                   (user_id,'importar','produtos',origin,json.dumps(details,ensure_ascii=False)))
    return counts


class GoogleRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed=urlsplit(newurl)
        host=(parsed.hostname or '').lower()
        if parsed.scheme!='https' or not (host=='docs.google.com' or host.endswith('.googleusercontent.com')):
            raise ValueError('A planilha exige autenticação ou redirecionou para um destino não permitido. Envie o CSV exportado.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch_google_csv(url):
    if not isinstance(url,str) or len(url)>2000:
        raise ValueError('Informe um link válido do Google Sheets.')
    parsed=urlsplit(url)
    match=re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?',parsed.path)
    if parsed.scheme!='https' or parsed.hostname!='docs.google.com' or parsed.username or parsed.password or parsed.port not in (None,443) or not match:
        raise ValueError('Use um link HTTPS de docs.google.com/spreadsheets/d/... .')
    query=parse_qs(parsed.query)
    fragment=parse_qs(parsed.fragment)
    gid=(query.get('gid') or fragment.get('gid') or ['0'])[0]
    if not str(gid).isdigit():
        raise ValueError('Identificador da aba inválido.')
    export=f'https://docs.google.com/spreadsheets/d/{match[1]}/export?format=csv&gid={gid}'
    try:
        opener=build_opener(GoogleRedirect())
        with opener.open(Request(export,headers={'User-Agent':'UsoConsumo-CSV/1.0'}),timeout=20) as response:
            content=response.read(MAX_BYTES+1)
        if len(content)>MAX_BYTES:
            raise ValueError('A planilha excede o limite de 1,5 MB.')
        return content.decode('utf-8-sig')
    except HTTPError as error:
        raise ValueError(f'O Google recusou o acesso à planilha (HTTP {error.code}). Confira as permissões ou envie o CSV exportado.') from error
    except URLError as error:
        raise ValueError('Não foi possível acessar o Google Sheets deste ambiente. Confira a permissão de rede para docs.google.com ou envie o CSV exportado.') from error
    except (UnicodeError,TimeoutError) as error:
        raise ValueError('Não foi possível ler a planilha. Tente enviar o CSV exportado.') from error
