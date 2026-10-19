"""Install reviewed product metadata once, without overwriting an operating database."""
import hashlib
import json
from pathlib import Path

try:
    from .catalog_csv import analyze_csv,import_rows
except ImportError:
    from catalog_csv import analyze_csv,import_rows

CATALOG = Path(__file__).with_name('data')/'catalogo_uso_consumo.csv'


def apply_catalog(connection, path=CATALOG):
    content=Path(path).read_bytes()
    digest=hashlib.sha256(content).hexdigest()
    connection.execute('CREATE TABLE IF NOT EXISTS catalog_releases (digest TEXT PRIMARY KEY,source TEXT NOT NULL,resultado TEXT NOT NULL,aplicado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    connection.commit()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute('SELECT 1 FROM catalog_releases WHERE digest=?',(digest,)).fetchone():
            return {'aplicado':False}
        analysis=analyze_csv(content.decode('utf-8-sig'))
        if analysis['errors']:
            raise ValueError('O catálogo revisado contém erros; nenhuma alteração foi aplicada.')
        counts=import_rows(connection,analysis['rows'],update_existing=False,origin=Path(path).name)
        connection.execute('INSERT INTO catalog_releases(digest,source,resultado) VALUES(?,?,?)',
                           (digest,Path(path).name,json.dumps(counts,ensure_ascii=False)))
    return {'aplicado':True,**counts}
